"""Local-only browser API for inspecting Albumentations transformations."""

from __future__ import annotations

import ast
import base64
import inspect
import json
import threading
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import albumentations as A
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field


IMAGE_SUFFIXES = frozenset({".bmp", ".jpeg", ".jpg", ".png"})
PREVIEW_TRANSFORM_REFERENCE = json.loads(
    Path(__file__)
    .with_name("albumentations_preview_reference.json")
    .read_text(encoding="utf-8")
)


class TransformStep(BaseModel):
    """Represents one ordered Albumentations transform and its fixed settings."""

    name: str
    settings: dict[str, Any] = Field(default_factory=dict)


class SweepAxis(BaseModel):
    """Represents one variable field in a pipeline-shaped preview request."""

    step_index: int
    field: str
    values: list[Any]


class PreviewRequest(BaseModel):
    """Represents the two-axis portion of an extensible preview pipeline request."""

    steps: list[TransformStep]
    axes: list[SweepAxis]


@dataclass
class PreviewJob:
    """Represents the in-memory state and result of one active render request."""

    identifier: str
    status: str = "running"
    completed: int = 0
    total: int = 0
    result: dict[str, Any] | None = None
    error: str | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)


def _json_value(value: Any) -> Any:
    """Use this function to turn constructor defaults into browser-safe JSON values."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if value is inspect.Parameter.empty:
        return None
    try:
        json.dumps(value)
    except TypeError:
        return repr(value)
    return value


def _enum_options(annotation: str) -> list[Any]:
    """Use this function when a constructor annotation should become a browser dropdown."""
    if not annotation.startswith("Literal[") or not annotation.endswith("]"):
        return []
    try:
        values = ast.literal_eval("[" + annotation[8:-1] + "]")
    except (SyntaxError, ValueError):
        return []
    return (
        values
        if all(isinstance(value, (bool, float, int, str)) for value in values)
        else []
    )


def _preview_label(value: Any) -> str:
    """Use this function when a preview candidate needs a compact browser label."""
    if isinstance(value, list) and len(value) == 2 and value[0] == value[1]:
        return _preview_label(value[0])
    if isinstance(value, float):
        return f"{value:.4g}"
    return json.dumps(value, separators=(",", ":"))


def _candidate_values(value: Any) -> list[Any]:
    """Use this function when a constructor default needs safe fixed preview candidates."""
    if isinstance(value, bool):
        return [False, True]
    if (
        isinstance(value, list)
        and len(value) == 2
        and all(isinstance(item, (float, int)) for item in value)
    ):
        low, high = value
        values = [low + (high - low) * index / 8 for index in range(9)]
        if all(isinstance(item, int) for item in value):
            values = [round(item) for item in values]
        return [[item, item] for item in values]
    return [value]


def _sweep_definitions(
    transform: type[A.BasicTransform], fields: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Use this function when exposing only constructor-validated non-probability sweep choices."""
    defaults = {definition["name"]: definition["default"] for definition in fields}
    sweeps = []
    for definition in fields:
        if definition["name"] in {"p", "strict"} or definition["required"]:
            continue
        values = []
        for candidate in _candidate_values(definition["default"]):
            try:
                transform(**(defaults | {definition["name"]: candidate, "p": 1.0}))
            except (TypeError, ValueError):
                continue
            if candidate not in values:
                values.append(candidate)
        if values:
            sweeps.append(
                {
                    "field": definition["name"],
                    "labels": [_preview_label(value) for value in values],
                    "values": values,
                }
            )
    return sweeps


def augmentation_catalog() -> list[dict[str, Any]]:
    """Use this function when the local UI needs documented preview transforms and fields."""
    catalog = []
    references = {
        reference["name"]: reference
        for reference in PREVIEW_TRANSFORM_REFERENCE["transforms"]
    }
    for name in sorted(dir(A)):
        transform = getattr(A, name)
        if name.startswith("_") or not isinstance(transform, type):
            continue
        if transform is A.BasicTransform or not issubclass(transform, A.BasicTransform):
            continue
        fields = []
        for parameter in inspect.signature(transform).parameters.values():
            if parameter.name == "self" or parameter.kind in {
                inspect.Parameter.VAR_KEYWORD,
                inspect.Parameter.VAR_POSITIONAL,
            }:
                continue
            default = _json_value(parameter.default)
            scalar = isinstance(default, (bool, float, int, str)) or default is None
            fields.append(
                {
                    "name": parameter.name,
                    "required": parameter.default is inspect.Parameter.empty,
                    "default": default,
                    "kind": "scalar" if scalar else "json",
                    "type": str(parameter.annotation),
                    "choices": _enum_options(str(parameter.annotation)),
                }
            )
        fallback: dict[str, Any] = {
            "description": (
                inspect.getdoc(transform) or "Albumentations transform."
            ).splitlines()[0],
            "signature": f"{name}{inspect.signature(transform)}",
            "sweeps": _sweep_definitions(transform, fields),
        }
        reference = references.get(name, {})
        documented_sweeps: list[dict[str, Any]] = list(reference.get("sweeps", []))
        fallback["sweeps"] = documented_sweeps + [
            sweep
            for sweep in fallback["sweeps"]
            if sweep["field"] not in {item["field"] for item in documented_sweeps}
        ]
        catalog.append(
            {
                "name": name,
                "fields": fields,
                **fallback,
                **{key: value for key, value in reference.items() if key != "sweeps"},
            }
        )
    return catalog


def _validated_request(
    request: PreviewRequest, catalog: dict[str, dict[str, Any]]
) -> None:
    """Use this function before queuing work to return request errors without a render job."""
    if len(request.axes) != 2:
        raise ValueError("provide exactly two sweep axes")
    if not request.steps:
        raise ValueError("provide at least one transform step")
    seen: set[tuple[int, str]] = set()
    for axis in request.axes:
        identity = (axis.step_index, axis.field)
        if identity in seen:
            raise ValueError("each sweep axis must select a distinct transform field")
        seen.add(identity)
        if not axis.values:
            raise ValueError(f"{axis.field} requires at least one candidate value")
        if not 0 <= axis.step_index < len(request.steps):
            raise ValueError(f"axis step index {axis.step_index} does not exist")
    for index, step in enumerate(request.steps):
        definition = catalog.get(step.name)
        if definition is None:
            raise ValueError(f"unknown Albumentations transform: {step.name}")
        allowed = {item["name"] for item in definition["fields"]}
        unknown = set(step.settings) - allowed
        if unknown:
            raise ValueError(
                f"{step.name} has unknown settings: {', '.join(sorted(unknown))}"
            )
        try:
            transform = getattr(A, step.name)
            for axis in request.axes:
                if axis.step_index == index:
                    if axis.field not in allowed:
                        raise ValueError(f"{step.name} has no field {axis.field}")
                    for value in axis.values:
                        transform(**(step.settings | {axis.field: value}))
            transform(**step.settings)
        except (TypeError, ValueError) as error:
            raise ValueError(f"{step.name}: {error}") from error


def _image_data(image: np.ndarray) -> str:
    """Use this function to return a rendered OpenCV image directly to the browser."""
    import cv2

    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise ValueError("could not encode rendered preview image")
    return "data:image/png;base64," + base64.b64encode(encoded).decode("ascii")


def _readable_images(
    source_dir: Path, max_images: int
) -> list[tuple[Path, np.ndarray]]:
    """Use this function to select the first sorted readable local source images."""
    import cv2

    images = []
    for path in sorted(source_dir.rglob("*")):
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if image is not None:
            images.append((path, image))
        if len(images) == max_images:
            break
    return images


def _render_job(
    job: PreviewJob,
    request: PreviewRequest,
    source_dir: Path,
    max_images: int,
    seed: int,
) -> None:
    """Use this function in a worker thread to keep image rendering off the request loop."""
    try:
        images = _readable_images(source_dir, max_images)
        if not images:
            raise ValueError(f"no readable images found under: {source_dir}")
        row_axis, column_axis = request.axes
        with job.lock:
            job.total = len(images)
        pages = []
        for path, source in images:
            variants = []
            for row_value in row_axis.values:
                row = []
                for column_value in column_axis.values:
                    steps = []
                    for index, step in enumerate(request.steps):
                        settings = dict(step.settings)
                        if row_axis.step_index == index:
                            settings[row_axis.field] = row_value
                        if column_axis.step_index == index:
                            settings[column_axis.field] = column_value
                        if (
                            "p"
                            in inspect.signature(
                                getattr(A, step.name).__init__
                            ).parameters
                        ):
                            settings["p"] = 1.0
                        steps.append(getattr(A, step.name)(**settings))
                    row.append(
                        _image_data(A.Compose(steps, seed=seed)(image=source)["image"])
                    )
                variants.append(row)
            pages.append(
                {
                    "source": path.name,
                    "original": _image_data(source),
                    "variants": variants,
                    "originalIndex": [0, 0],
                }
            )
            with job.lock:
                job.completed += 1
        with job.lock:
            job.result = {
                "axes": [axis.model_dump() for axis in request.axes],
                "pages": pages,
            }
            job.status = "completed"
    except Exception as error:  # Albumentations can fail only once it sees image data.
        with job.lock:
            job.error = str(error)
            job.status = "failed"


def _page() -> str:
    """Use this function to serve the dependency-free local augmentation preview interface."""
    return """<!doctype html>
<title>Albumentations preview</title>
<style>
body{font:14px system-ui;margin:2rem;max-width:1200px}.axis{border:1px solid #ccc;padding:1rem;margin:.5rem 0}.fields{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:.5rem}label{display:grid;gap:.2rem}.range-window{position:relative;height:1.75rem;margin:.5rem 0}.range-window::before{background:#b8c2cc;border-radius:4px;content:'';height:6px;left:0;position:absolute;right:0;top:.65rem}.range-window input{appearance:none;background:transparent;height:1.75rem;left:0;margin:0;pointer-events:none;position:absolute;width:100%}.range-window input::-webkit-slider-runnable-track{background:transparent;height:6px}.range-window input::-webkit-slider-thumb{appearance:none;background:#1677cc;border:2px solid #fff;border-radius:50%;cursor:grab;height:16px;margin-top:-5px;pointer-events:auto;width:16px}.range-window input::-moz-range-track{background:transparent;height:6px}.range-window input::-moz-range-thumb{background:#1677cc;border:2px solid #fff;border-radius:50%;cursor:grab;height:12px;pointer-events:auto;width:12px}button{padding:.5rem;margin:.5rem 0}.count{display:flex;gap:.5rem;align-items:center}.source{max-width:360px;max-height:240px;object-fit:contain;border:2px solid #1677cc}.preview-table{border-collapse:collapse;margin-bottom:2rem}.preview-table th,.preview-table td{border:1px solid #bbb;padding:.5rem;text-align:center}.preview-table th{background:#eee;min-width:180px}.preview-table td{background:#222}.preview-table img{display:block;height:180px;object-fit:contain;width:180px}
</style>
<h1>Albumentations preview</h1>
<p>Choose each augmentation's parameter range, then select <b>Render</b> to render only that selection on this computer.</p>
<section id=controls></section><button id=render>Render</button><output id=status></output><section id=results></section>
<script>
let catalog=[],axes=[{},{}];const controls=document.querySelector('#controls'),status=document.querySelector('#status');
const transform=(name)=>catalog.find(item=>item.name===name);
const selectionIndexes=(axis)=>Array.from({length:axis.count},(_,index)=>axis.count===1?axis.low:Math.round(axis.low+(index*(axis.high-axis.low))/(axis.count-1)));
function setSelection(axis,item,sweep){Object.assign(axis,{name:item.name,description:item.description,signature:item.signature,settings:Object.fromEntries(item.fields.map(item=>[item.name,item.name==='p'?1.0:item.default])),field:sweep.field,candidates:sweep.values,labels:sweep.labels,low:0,high:sweep.values.length-1,count:Math.min(4,sweep.values.length)});}
function values(axis){return selectionIndexes(axis).map(index=>axis.candidates[index])}
function input(field,value){if(field.choices.length){let e=document.createElement('select');field.choices.forEach(choice=>e.add(new Option(String(choice),JSON.stringify(choice),false,choice===value)));return e}let e=document.createElement(field.kind==='scalar'?'input':'textarea');if(field.kind==='scalar'&&field.type.includes('bool')){e.type='checkbox';e.checked=Boolean(value)}else{e.type=field.kind==='scalar'&&field.type.includes('int')?'number':field.kind==='scalar'&&field.type.includes('float')?'number':'text';e.value=field.kind==='scalar'?(value??''):JSON.stringify(value??null)}return e}
function read(e,field){if(field.choices.length)return JSON.parse(e.value);if(e.type==='checkbox')return e.checked;if(field.kind==='scalar'){if(e.value!==''&&!Number.isNaN(Number(e.value)))return Number(e.value);return e.value}return JSON.parse(e.value)}
function axis(index){
  let selected=axes[index],box=document.createElement('section');box.className='axis';
  let search=document.createElement('input'),list=document.createElement('datalist');
  list.id=`transforms-${index}`;search.setAttribute('list',list.id);search.value=selected.name;
  catalog.forEach(item=>list.append(new Option(item.name)));
  search.onchange=()=>{let item=transform(search.value);if(item)setSelection(selected,item,item.sweeps[0]);else search.value=selected.name;draw()};
  box.append('Augmentation: ',search,list);
  let item=transform(selected.name);if(!item)return box;
  let selectedName=document.createElement('h2');selectedName.textContent=`Selected augmentation: ${selected.name}`;box.append(selectedName);
  let description=document.createElement('p');description.textContent=selected.description;box.append(description);
  let probability=document.createElement('p');probability.textContent='p is fixed at 1, so this augmentation is applied to every rendered image.';box.append(probability);
  let sweepSelect=document.createElement('select');
  item.sweeps.forEach(sweep=>sweepSelect.add(new Option(sweep.field,sweep.field,sweep.field===selected.field,sweep.field===selected.field)));
  sweepSelect.onchange=()=>{setSelection(selected,item,item.sweeps.find(sweep=>sweep.field===sweepSelect.value));draw()};
  box.append('Sweep parameter: ',sweepSelect);
  let signature=document.createElement('details'),summary=document.createElement('summary'),code=document.createElement('code');
  summary.textContent='Function signature';code.textContent=selected.signature;signature.append(summary,code);box.append(signature);
  let window=document.createElement('div'),bounds=document.createElement('output'),countLabel=document.createElement('span');
  window.className='range-window';bounds.textContent=`${selected.labels[selected.low]} — ${selected.labels[selected.high]}`;countLabel.textContent=`${selected.count} values`;
  for(const handle of ['low','high']){let slider=document.createElement('input');slider.type='range';Object.assign(slider,{min:0,max:selected.candidates.length-1,step:1,value:selected[handle]});slider.oninput=()=>{let value=Number(slider.value);if(handle==='low')selected.low=Math.min(value,selected.high);else selected.high=Math.max(value,selected.low);selected.count=Math.min(selected.count,selected.high-selected.low+1);bounds.textContent=`${selected.labels[selected.low]} — ${selected.labels[selected.high]}`;countLabel.textContent=`${selected.count} values`};window.append(slider)}
  box.append(window,bounds);
  let count=document.createElement('div');count.className='count';let minus=document.createElement('button');minus.textContent='−';minus.onclick=()=>{selected.count=Math.max(1,selected.count-1);draw()};let plus=document.createElement('button');plus.textContent='+';plus.onclick=()=>{selected.count=Math.min(selected.high-selected.low+1,selected.count+1);draw()};count.append(minus,countLabel,plus);box.append(count);
  let parameters=document.createElement('details');parameters.innerHTML='<summary>Non-sweep parameters</summary>';let fields=document.createElement('div');fields.className='fields';item.fields.filter(field=>field.name!==selected.field&&field.name!=='p').forEach(field=>{let label=document.createElement('label');label.textContent=field.name;let control=input(field,selected.settings[field.name]);control.onchange=()=>{try{selected.settings[field.name]=read(control,field);selected.error=null}catch(error){selected.error=error.message;status.textContent=error.message}};label.append(control);fields.append(label)});parameters.append(fields);box.append(parameters);return box
}
function draw(){controls.replaceChildren(axis(0),axis(1))}
async function refresh(){let response=await fetch('/api/catalog');catalog=(await response.json()).filter(item=>item.sweeps.length);axes=catalog.slice(0,2).map(item=>{let axis={};setSelection(axis,item,item.sweeps[0]);return axis});draw()}
function labelFor(axis,value){return axis.labels[axis.candidates.findIndex(candidate=>JSON.stringify(candidate)===JSON.stringify(value))]}function labelledImage(source,alt){let image=document.createElement('img');image.src=source;image.alt=alt;return image}function show(data){let result=document.querySelector('#results');result.replaceChildren();let rowAxis=data.axes[0],columnAxis=data.axes[1],rowSelection=axes[0],columnSelection=axes[1];data.pages.forEach(page=>{let heading=document.createElement('h2');heading.textContent=page.source;let original=document.createElement('figure');let source=labelledImage(page.original,`${page.source}; original source image`);source.className='source';original.append(source);let caption=document.createElement('figcaption');caption.textContent='Original source image';original.append(caption);let grid=document.createElement('div');grid.className='grid';grid.style.gridTemplateColumns=`150px repeat(${columnAxis.values.length},180px)`;let corner=document.createElement('div');corner.className='header row-header';corner.textContent=`Rows: ${rowSelection.name} · ${rowAxis.field}\nColumns: ${columnSelection.name} · ${columnAxis.field}`;grid.append(corner);columnAxis.values.forEach(value=>{let header=document.createElement('div');header.className='header';header.textContent=`${columnSelection.name}\n${columnAxis.field} = ${labelFor(columnSelection,value)}`;grid.append(header)});page.variants.forEach((row,rowIndex)=>{let header=document.createElement('div');header.className='header row-header';header.textContent=`${rowSelection.name}\n${rowAxis.field} = ${labelFor(rowSelection,rowAxis.values[rowIndex])}`;grid.append(header);row.forEach((imageSource,columnIndex)=>{let cell=document.createElement('div');cell.className='cell';cell.append(labelledImage(imageSource,`${page.source}; rendered ${rowSelection.name} ${rowAxis.field}=${labelFor(rowSelection,rowAxis.values[rowIndex])}, ${columnSelection.name} ${columnAxis.field}=${labelFor(columnSelection,columnAxis.values[columnIndex])}`));grid.append(cell)})});result.append(heading,original,grid)})}
function show(data){let result=document.querySelector('#results');result.replaceChildren();let rowAxis=data.axes[0],columnAxis=data.axes[1],rowSelection=axes[0],columnSelection=axes[1];data.pages.forEach(page=>{let heading=document.createElement('h2');heading.textContent=page.source;let original=document.createElement('figure');let source=labelledImage(page.original,`${page.source}; original source image`);source.className='source';original.append(source);let caption=document.createElement('figcaption');caption.textContent='Original source image';original.append(caption);let table=document.createElement('table'),head=table.createTHead(),groups=head.insertRow(),valuesRow=head.insertRow();table.className='preview-table';let rowGroup=document.createElement('th');rowGroup.rowSpan=2;rowGroup.textContent=`Rows\n${rowSelection.name}\n${rowAxis.field}`;groups.append(rowGroup);let columnGroup=document.createElement('th');columnGroup.colSpan=columnAxis.values.length;columnGroup.textContent=`Columns\n${columnSelection.name}\n${columnAxis.field}`;groups.append(columnGroup);columnAxis.values.forEach(value=>{let header=document.createElement('th');header.textContent=labelFor(columnSelection,value);valuesRow.append(header)});let body=table.createTBody();page.variants.forEach((row,rowIndex)=>{let tableRow=body.insertRow(),header=document.createElement('th');header.textContent=labelFor(rowSelection,rowAxis.values[rowIndex]);tableRow.append(header);row.forEach((imageSource,columnIndex)=>{let cell=tableRow.insertCell();cell.append(labelledImage(imageSource,`${page.source}; ${rowSelection.name} ${rowAxis.field} ${labelFor(rowSelection,rowAxis.values[rowIndex])}; ${columnSelection.name} ${columnAxis.field} ${labelFor(columnSelection,columnAxis.values[columnIndex])}`))})});result.append(heading,original,table)})}
document.querySelector('#render').onclick=async()=>{try{if(axes.some(axis=>axis.error))throw Error(axes.find(axis=>axis.error).error);let payload={steps:axes.map(axis=>({name:axis.name,settings:axis.settings})),axes:axes.map((axis,index)=>({step_index:index,field:axis.field,values:values(axis)}))};let response=await fetch('/api/regenerate',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(payload)}),data=await response.json();if(!response.ok)throw Error(data.detail);status.textContent='Rendering…';let poll=async()=>{let job=await (await fetch('/api/jobs/'+data.id)).json();status.textContent=`${job.status}: ${job.completed}/${job.total}`;if(job.status==='running')return setTimeout(poll,200);if(job.status==='completed')show(job.result);else status.textContent=job.error};poll()}catch(error){status.textContent=error.message}};refresh()
</script>"""


def create_augmentation_preview_app(
    source_dir: str | Path, *, max_images: int = 24, seed: int = 0
) -> FastAPI:
    """Use this function to host an on-demand local browser preview for a fixed image folder.

    Parameters
    ----------
    source_dir : str or pathlib.Path
        Directory containing source images; it is normalized once at startup.
    max_images : int, default=24
        Maximum number of sorted readable images included in each render job.
    seed : int, default=0
        Albumentations seed reused for each rendered grid cell.
    """
    root = Path(source_dir).expanduser()
    if not root.is_dir():
        raise ValueError(f"source_dir must be an existing directory: {root}")
    if max_images < 1:
        raise ValueError("max_images must be positive")
    app = FastAPI()
    catalog = {item["name"]: item for item in augmentation_catalog()}
    current: dict[str, PreviewJob | None] = {"job": None}

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        """Use this endpoint to load the localhost-only preview interface."""
        return _page()

    @app.get("/api/catalog")
    def get_catalog() -> list[dict[str, Any]]:
        """Use this endpoint to populate searchable transform selectors and form fields."""
        return list(catalog.values())

    @app.post("/api/regenerate")
    def regenerate(request: PreviewRequest) -> dict[str, str]:
        """Use this endpoint to validate settings and begin one asynchronous preview render."""
        try:
            _validated_request(request, catalog)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        job = PreviewJob(identifier=str(uuid.uuid4()))
        current["job"] = job
        threading.Thread(
            target=_render_job, args=(job, request, root, max_images, seed), daemon=True
        ).start()
        return {"id": job.identifier}

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict[str, Any]:
        """Use this endpoint to poll the sole in-memory render job for progress and results."""
        job = current["job"]
        if job is None or job.identifier != job_id:
            raise HTTPException(status_code=404, detail="preview job not found")
        with job.lock:
            return {
                "id": job.identifier,
                "status": job.status,
                "completed": job.completed,
                "total": job.total,
                "result": job.result,
                "error": job.error,
            }

    return app


def start_augmentation_preview_server(
    source_dir: str | Path, *, port: int = 8765
) -> None:
    """Use this function when a shell launcher needs to serve the app on loopback only."""
    import uvicorn

    uvicorn.run(
        create_augmentation_preview_app(source_dir), host="127.0.0.1", port=port
    )
