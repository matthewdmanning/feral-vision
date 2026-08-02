import difflib
import html
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, NoReturn, Sequence

import albumentations as A
import hydra
import numpy as np
from omegaconf import DictConfig

from feral_vision.config.store import register_configs
from feral_vision.utils import get_logger, to_dtype

log = get_logger(__name__)

register_configs()


@dataclass(frozen=True)
class AugmentationSweep:
    """Represents the candidate values for one parameter of one configured transform.

    Parameters
    ----------
    transform : str
        Name of the configured Albumentations transform to vary.
    parameter : str
        Transform keyword argument to vary.
    values : Sequence[Any]
        Candidate values evaluated in the preview.
    is_binary : bool, default=False
        Whether exactly two values represent a binary operation.
    display_values : Sequence[Any] or None, default=None
        Human-facing labels for ``values`` when the transform requires a
        structured parameter such as a fixed ``(low, high)`` tuple.
    """

    transform: str
    parameter: str
    values: Sequence[Any]
    is_binary: bool = False
    display_values: Sequence[Any] | None = None


@dataclass(frozen=True)
class AugmentationVariant:
    """Represents one augmented image and the parameter values that produced it.

    Parameters
    ----------
    settings : Mapping[str, Any]
        Fully qualified transform parameter names and their selected values.
    image : numpy.ndarray
        Augmented image in the same OpenCV channel order as its source.
    """

    settings: Mapping[str, Any]
    image: np.ndarray


@dataclass(frozen=True)
class AugmentationPreview:
    """Represents one source-image page and its augmentation cross-product variants.

    Parameters
    ----------
    source_path : pathlib.Path
        Local image selected from the source directory.
    source_image : numpy.ndarray
        Unmodified source image in OpenCV channel order.
    row_sweep : AugmentationSweep
        Sweep whose values define preview-grid rows.
    column_sweep : AugmentationSweep
        Sweep whose values define preview-grid columns.
    variants : tuple[tuple[AugmentationVariant, ...], ...]
        Augmented outputs indexed as ``variants[row][column]``.
    """

    source_path: Path
    source_image: np.ndarray
    row_sweep: AugmentationSweep
    column_sweep: AugmentationSweep
    variants: tuple[tuple[AugmentationVariant, ...], ...]


def _suggest(name: str) -> list[str]:
    return difflib.get_close_matches(name, dir(A), n=3, cutoff=0.6)


def _instantiate_transform(op: Any) -> A.BasicTransform:
    """Use this function to construct a configured Albumentations transform by name."""
    name = op["name"] if hasattr(op, "__getitem__") else op.name
    kwargs = {k: v for k, v in op.items() if k != "name"}
    transform = getattr(A, name, None)
    if not isinstance(transform, type) or not issubclass(transform, A.BasicTransform):
        _unknown_transform(name)
    return transform(**kwargs)


def _unknown_transform(name: str) -> NoReturn:
    suggestions = _suggest(name)
    msg = f"unknown transform {name!r}"
    if suggestions:
        msg += f"; did you mean: {', '.join(suggestions)}?"
    raise ValueError(msg)


def _image_paths(root: Path) -> tuple[Path, ...]:
    """Use this function when augmenting images from a local directory tree."""
    suffixes = {".png", ".jpg", ".jpeg", ".bmp"}
    return tuple(
        sorted(path for path in root.rglob("*") if path.suffix.lower() in suffixes)
    )


def build_augmentation_previews(
    source_dir: str | Path,
    operations: Sequence[Mapping[str, Any]],
    sweeps: Sequence[AugmentationSweep],
    *,
    seed: int = 0,
) -> tuple[AugmentationPreview, ...]:
    """Use this function to visually compare two augmentation parameters across local images.

    Parameters
    ----------
    source_dir : str or pathlib.Path
        Local directory recursively searched for source images.
    operations : Sequence[Mapping[str, Any]]
        Ordered transform definitions with Albumentations class names and keyword
        arguments.
    sweeps : Sequence[AugmentationSweep]
        Exactly two independent transform parameters; the first defines grid
        rows and the second defines grid columns.
    seed : int, default=0
        Albumentations seed reused for each variant so stochastic transforms are
        reproducible across calls.

    Returns
    -------
    tuple[AugmentationPreview, ...]
        One page-ready preview per readable source image. Each page contains the
        complete row-by-column Cartesian product. Callers own rendering,
        pagination, scrolling, and any persistence of these in-memory results.

    Raises
    ------
    ValueError
        If the source directory is invalid, there are not exactly two sweeps, a
        non-binary sweep has fewer than three values, a sweep cannot be applied
        to exactly one operation, or no readable images are found.
    """
    root = Path(source_dir)
    if not root.is_dir():
        raise ValueError(f"source_dir must be an existing directory: {root}")
    if len(sweeps) != 2:
        raise ValueError("provide exactly two augmentation sweeps")

    configured_ops = [dict(operation) for operation in operations]
    sweep_indices: list[int] = []
    sweep_identities: set[tuple[str, str]] = set()
    for sweep in sweeps:
        if len(sweep.values) < 3 and not sweep.is_binary:
            raise ValueError(
                f"sweep {sweep.transform}.{sweep.parameter} requires at least three values"
            )
        if len(sweep.values) != 2 and sweep.is_binary:
            raise ValueError(
                f"binary sweep {sweep.transform}.{sweep.parameter} requires two values"
            )
        if sweep.display_values is not None and len(sweep.display_values) != len(
            sweep.values
        ):
            raise ValueError(
                f"sweep {sweep.transform}.{sweep.parameter} display values must match values"
            )
        identity = (sweep.transform, sweep.parameter)
        if identity in sweep_identities:
            raise ValueError(f"duplicate sweep {sweep.transform}.{sweep.parameter}")
        sweep_identities.add(identity)
        matches = [
            index
            for index, operation in enumerate(configured_ops)
            if operation.get("name") == sweep.transform
        ]
        if len(matches) != 1:
            raise ValueError(
                f"sweep {sweep.transform}.{sweep.parameter} must match exactly one operation"
            )
        sweep_indices.append(matches[0])

    import cv2

    row_sweep, column_sweep = sweeps
    source_paths = _image_paths(root)
    previews: list[AugmentationPreview] = []
    pipelines: list[list[tuple[dict[str, Any], A.Compose]]] = []
    for row_value in row_sweep.values:
        row_pipelines: list[tuple[dict[str, Any], A.Compose]] = []
        for column_value in column_sweep.values:
            variant_ops = [dict(operation) for operation in configured_ops]
            settings = {
                f"{row_sweep.transform}.{row_sweep.parameter}": row_value,
                f"{column_sweep.transform}.{column_sweep.parameter}": column_value,
            }
            variant_ops[sweep_indices[0]][row_sweep.parameter] = row_value
            variant_ops[sweep_indices[1]][column_sweep.parameter] = column_value
            row_pipelines.append(
                (
                    settings,
                    A.Compose(
                        [
                            _instantiate_transform(operation)
                            for operation in variant_ops
                        ],
                        seed=seed,
                    ),
                )
            )
        pipelines.append(row_pipelines)

    for source_path in source_paths:
        source_image = cv2.imread(str(source_path), cv2.IMREAD_UNCHANGED)
        if source_image is None:
            continue
        source_image = (
            to_dtype(source_image, np.uint8)
            if source_image.dtype != np.uint8
            else source_image
        )
        variants = tuple(
            tuple(
                AugmentationVariant(
                    settings=dict(settings),
                    image=pipeline(image=source_image)["image"],
                )
                for settings, pipeline in row_pipelines
            )
            for row_pipelines in pipelines
        )
        previews.append(
            AugmentationPreview(
                source_path=source_path,
                source_image=source_image,
                row_sweep=row_sweep,
                column_sweep=column_sweep,
                variants=variants,
            )
        )

    if not previews:
        raise ValueError(f"no readable images found under: {root}")
    return tuple(previews)


def _write_preview_asset(image: np.ndarray, destination: Path) -> None:
    """Use this function to persist one rendered preview cell for the local HTML viewer."""
    import cv2

    destination.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(destination), image):
        raise OSError(f"could not write augmentation preview asset: {destination}")


def _preview_document(title: str, pages: list[dict[str, Any]]) -> str:
    """Use this function to create the self-contained browser interface for local preview pages."""
    page_data = json.dumps(pages, default=str).replace("</", "<\\/")
    escaped_title = html.escape(title)
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{escaped_title}</title>
    <style>
      :root {{ color-scheme: dark; font-family: system-ui, sans-serif; }}
      body {{ margin: 0; background: #171717; color: #f5f5f5; }}
      .page-nav {{ display: flex; gap: .75rem; align-items: center; padding: .75rem 1rem; background: #242424; }}
      button {{ font: inherit; padding: .35rem .65rem; cursor: pointer; }}
      .workspace {{ display: grid; grid-template-rows: auto minmax(0, 1fr); height: calc(100vh - 58px); }}
      .controls {{ display: grid; grid-template-columns: repeat(2, minmax(19rem, 1fr)); gap: .75rem; padding: .75rem 1rem; background: #1c1c1c; border-bottom: 1px solid #4a4a4a; }}
      .control {{ min-width: 0; display: grid; gap: .5rem; padding: .7rem .8rem; background: #292929; border: 1px solid #4a4a4a; border-radius: .4rem; }}
      .control-heading {{ display: flex; align-items: baseline; justify-content: space-between; gap: .75rem; min-width: 0; }}
      .control-name {{ overflow-wrap: anywhere; font-weight: 650; }}
      .selection {{ flex: 0 0 auto; font: .8rem ui-monospace, monospace; color: #c9d8e8; white-space: nowrap; }}
      .control-line {{ display: flex; gap: .5rem; align-items: center; }}
      .slider-pair {{ display: grid; gap: .35rem; }}
      .slider-row {{ display: grid; grid-template-columns: 2.5rem minmax(8rem, 14rem) max-content; gap: .5rem; align-items: center; font-size: .82rem; }}
      .slider-row input {{ width: 100%; margin: 0; accent-color: #70b7ff; }}
      .slider-value {{ font: .8rem ui-monospace, monospace; color: #c9d8e8; white-space: nowrap; }}
      .viewer {{ min-height: 0; overflow: auto; background: #111; }}
      .grid {{ display: grid; width: max-content; align-items: stretch; gap: 1px; background: #555; }}
      .axis {{ background: #242424; z-index: 2; }}
      .corner {{ position: sticky; top: 0; left: 0; z-index: 5; padding: .65rem; width: 180px; overflow-wrap: anywhere; }}
      .column-value {{ position: sticky; top: 0; z-index: 3; padding: .65rem .5rem; text-align: center; overflow-wrap: anywhere; }}
      .row-value {{ position: sticky; left: 0; z-index: 3; display: flex; align-items: center; padding: .5rem; width: 180px; overflow-wrap: anywhere; }}
      .cell {{ background: #050505; display: grid; place-items: center; overflow: hidden; }}
      .cell.original {{ position: relative; outline: 3px solid #70b7ff; outline-offset: -3px; }}
      .original-badge {{ position: absolute; top: .45rem; right: .45rem; padding: .2rem .4rem; border-radius: .2rem; background: #1769aa; color: #fff; font-size: .75rem; font-weight: 650; }}
      .cell img {{ display: block; max-width: 100%; max-height: 100%; object-fit: contain; }}
      .source {{ color: #c9d8e8; }}
      @media (max-width: 720px) {{
        .controls {{ grid-template-columns: 1fr; }}
        .slider-row {{ grid-template-columns: 2.5rem minmax(7rem, 1fr) max-content; }}
      }}
    </style>
  </head>
  <body>
    <nav class="page-nav">
      <button id="previous" type="button">Previous image</button>
      <strong id="caption"></strong>
      <button id="next" type="button">Next image</button>
    </nav>
    <main class="workspace" aria-live="polite">
      <section id="controls" class="controls" aria-label="Augmentation controls"></section>
      <section id="viewer" class="viewer" aria-label="Augmentation grid"></section>
    </main>
    <script>
      const pages = {page_data};
      const cellWidth = 256;
      let pageIndex = 0;
      let state;

      const evenlySpaced = (start, end, count) => {{
        if (count === 1) return [start];
        return Array.from({{ length: count }}, (_, index) =>
          Math.round(start + (index * (end - start)) / (count - 1))
        );
      }};

      const referenceIndex = (values) => {{
        const zeroIndex = values.findIndex((value) => Number(value) === 0);
        return zeroIndex === -1 ? Math.floor(values.length / 2) : zeroIndex;
      }};

      const closestIndex = (indices, target) => indices.reduce(
        (closest, index) => Math.abs(index - target) < Math.abs(closest - target) ? index : closest
      );

      const axisControl = (axis) => {{
        const sweep = axis === "row" ? state.page.row : state.page.column;
        const selected = state[axis];
        const labels = sweep.displayValues;
        const minimum = sweep.binary ? 2 : 3;
        const wrapper = document.createElement("section");
        wrapper.className = "control";
        wrapper.innerHTML = `
          <div class="control-heading">
            <span class="control-name">${{sweep.transform}}.${{sweep.parameter}}</span>
            <span class="selection">${{String(labels[selected.low])}} — ${{String(labels[selected.high])}}</span>
          </div>
          <div class="control-line">
            <button type="button" data-action="decrease">−</button>
            <span>${{selected.count}} values</span>
            <button type="button" data-action="increase">+</button>
          </div>
          <div class="slider-pair">
            <label class="slider-row"><span>From</span><input data-handle="low" type="range" min="0" max="${{sweep.values.length - 1}}" value="${{selected.low}}"><output class="slider-value">${{String(labels[selected.low])}}</output></label>
            <label class="slider-row"><span>To</span><input data-handle="high" type="range" min="0" max="${{sweep.values.length - 1}}" value="${{selected.high}}"><output class="slider-value">${{String(labels[selected.high])}}</output></label>
          </div>
          `;
        wrapper.querySelector('[data-action="decrease"]').onclick = () => {{
          selected.count = Math.max(minimum, selected.count - 1); render();
        }};
        wrapper.querySelector('[data-action="increase"]').onclick = () => {{
          selected.count = Math.min(selected.high - selected.low + 1, selected.count + 1); render();
        }};
        wrapper.querySelectorAll("input").forEach((input) => {{
          input.oninput = () => {{
            const value = Number(input.value);
            if (input.dataset.handle === "low") {{
              selected.low = Math.min(value, selected.high - minimum + 1);
            }} else {{
              selected.high = Math.max(value, selected.low + minimum - 1);
            }}
            selected.count = Math.min(selected.count, selected.high - selected.low + 1);
            render();
          }};
        }});
        return wrapper;
      }};

      const render = () => {{
        const page = state.page;
        const rows = evenlySpaced(state.row.low, state.row.high, state.row.count);
        const columns = evenlySpaced(state.column.low, state.column.high, state.column.count);
        const sourceRow = closestIndex(rows, referenceIndex(page.row.values));
        const sourceColumn = closestIndex(columns, referenceIndex(page.column.values));
        const height = Math.round(cellWidth / page.aspectRatio);
        const grid = document.createElement("section");
        grid.className = "grid";
        grid.style.gridTemplateColumns = `198px repeat(${{columns.length}}, ${{cellWidth}}px)`;
        grid.append(Object.assign(document.createElement("div"), {{ className: "axis corner", textContent: `${{page.row.transform}}.${{page.row.parameter}}` }}));
        columns.forEach((column) => {{
          const label = Object.assign(document.createElement("div"), {{ className: "axis column-value", textContent: String(page.column.displayValues[column]) }});
          grid.append(label);
        }});
        rows.forEach((row) => {{
          const rowLabel = Object.assign(document.createElement("div"), {{ className: "axis row-value", textContent: String(page.row.displayValues[row]) }});
          grid.append(rowLabel);
          columns.forEach((column) => {{
            const cell = Object.assign(document.createElement("div"), {{ className: "cell" }});
            cell.style.width = `${{cellWidth}}px`;
            cell.style.height = `${{height}}px`;
            const image = document.createElement("img");
            const isOriginal = row === sourceRow && column === sourceColumn;
            image.src = isOriginal ? page.sourceAsset : page.variants[row][column];
            image.alt = isOriginal
              ? `${{page.source}}; original source image`
              : `${{page.source}}; ${{page.row.transform}}.${{page.row.parameter}}=${{page.row.displayValues[row]}}, ${{page.column.transform}}.${{page.column.parameter}}=${{page.column.displayValues[column]}}`;
            cell.append(image);
            if (isOriginal) {{
              cell.classList.add("original");
              cell.append(Object.assign(document.createElement("span"), {{
                className: "original-badge", textContent: "Original source"
              }}));
            }}
            grid.append(cell);
          }});
        }});
        document.querySelector("#controls").replaceChildren(axisControl("row"), axisControl("column"));
        document.querySelector("#viewer").replaceChildren(grid);
        document.querySelector("#caption").textContent = `${{pageIndex + 1}} / ${{pages.length}}: ${{page.source}}`;
      }};

      const selectPage = (index) => {{
        pageIndex = (index + pages.length) % pages.length;
        const page = pages[pageIndex];
        state = {{
          page,
          row: {{ low: 0, high: page.row.values.length - 1, count: Math.min(4, page.row.values.length) }},
          column: {{ low: 0, high: page.column.values.length - 1, count: Math.min(4, page.column.values.length) }},
        }};
        render();
      }};
      document.querySelector("#previous").onclick = () => selectPage(pageIndex - 1);
      document.querySelector("#next").onclick = () => selectPage(pageIndex + 1);
      selectPage(0);
    </script>
  </body>
</html>"""


def write_augmentation_preview_html(
    previews: Sequence[AugmentationPreview], output_dir: str | Path
) -> Path:
    """Use this function to create a local interactive HTML augmentation viewer for human review.

    Parameters
    ----------
    previews : Sequence[AugmentationPreview]
        Source-image pages produced by :func:`build_augmentation_previews`.
    output_dir : str or pathlib.Path
        Local destination for ``index.html`` and its rendered image assets.

    Returns
    -------
    pathlib.Path
        The generated ``index.html`` path. The page keeps both augmentation
        controls visible while its fixed-aspect-ratio grid scrolls.
    """
    if not previews:
        raise ValueError("provide at least one augmentation preview")

    destination = Path(output_dir)
    pages: list[dict[str, Any]] = []
    for page_index, preview in enumerate(previews):
        height, width = preview.source_image.shape[:2]
        asset_root = destination / "assets" / f"page-{page_index + 1}"
        source_asset = asset_root / "source.png"
        _write_preview_asset(preview.source_image, source_asset)
        variants: list[list[str]] = []
        for row_index, row in enumerate(preview.variants):
            asset_row: list[str] = []
            for column_index, variant in enumerate(row):
                asset = asset_root / f"{row_index}-{column_index}.png"
                _write_preview_asset(variant.image, asset)
                asset_row.append(asset.relative_to(destination).as_posix())
            variants.append(asset_row)
        pages.append(
            {
                "source": preview.source_path.name,
                "sourceAsset": source_asset.relative_to(destination).as_posix(),
                "aspectRatio": width / height,
                "row": {
                    "transform": preview.row_sweep.transform,
                    "parameter": preview.row_sweep.parameter,
                    "values": list(preview.row_sweep.values),
                    "displayValues": list(
                        preview.row_sweep.display_values or preview.row_sweep.values
                    ),
                    "binary": preview.row_sweep.is_binary,
                },
                "column": {
                    "transform": preview.column_sweep.transform,
                    "parameter": preview.column_sweep.parameter,
                    "values": list(preview.column_sweep.values),
                    "displayValues": list(
                        preview.column_sweep.display_values
                        or preview.column_sweep.values
                    ),
                    "binary": preview.column_sweep.is_binary,
                },
                "variants": variants,
            }
        )

    destination.mkdir(parents=True, exist_ok=True)
    index = destination / "index.html"
    index.write_text(_preview_document("Augmentation preview", pages), encoding="utf-8")
    return index


def run_augment_stage(cfg: DictConfig) -> None:
    """Apply the configured augmentation pipeline across data/raw -> data/augmented.

    Parameters
    ----------
    cfg : DictConfig
        Top-level Hydra config; must contain ``cfg.augmentation`` and optionally
        ``cfg.data.root`` (defaults to ``"data"``).

    Notes
    -----
    Images are converted to uint8 via ``to_dtype`` before the Albumentations
    pipeline (its expected input format) and written back as uint8. The stage
    is a no-op when the raw directory is absent so DVC never fails in
    environments where data has not been fetched.
    """
    ops = list(cfg.augmentation.ops) if cfg.augmentation.ops else []
    pipeline = A.Compose([_instantiate_transform(op) for op in ops])
    label = cfg.augmentation.name
    log.info("built augmentation pipeline: %s", label)

    root = Path(getattr(cfg.data, "root", "data")) if "data" in cfg else Path("data")
    raw_dir = root / "raw"
    out_dir = root / "augmented"

    if not raw_dir.exists():
        log.info("raw dir %s absent; nothing to augment", raw_dir)
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    import cv2

    for path in _image_paths(raw_dir):
        image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if image is None:
            log.warning("could not read %s; skipping", path)
            continue
        image_u8 = to_dtype(image, np.uint8) if image.dtype != np.uint8 else image
        augmented = pipeline(image=image_u8)["image"]
        dest = out_dir / f"{path.stem}_{label}{path.suffix}"
        cv2.imwrite(str(dest), augmented)
        log.info("wrote %s", dest)


def materialize_detection_variant(
    source_root: str | Path,
    destination_root: str | Path,
    operations: Sequence[Mapping[str, Any]],
    *,
    seed: int,
) -> Path:
    """Use this function to materialize one annotation-aware YOLO variant per source image."""
    import cv2

    source_root = Path(source_root)
    destination_root = Path(destination_root)
    source_images = source_root / "images"
    source_annotations = source_root / "annotations"
    if not source_images.is_dir() or not source_annotations.is_dir():
        raise ValueError("detection source must contain images/ and annotations/")

    output_images = destination_root / "images"
    output_annotations = destination_root / "annotations"
    output_images.mkdir(parents=True, exist_ok=True)
    output_annotations.mkdir(parents=True, exist_ok=True)
    pipeline = A.Compose(
        [_instantiate_transform(operation) for operation in operations],
        bbox_params=A.BboxParams(format="yolo", label_fields=["class_labels"]),
    )

    for index, image_path in enumerate(_image_paths(source_images)):
        annotation_path = source_annotations / f"{image_path.stem}.txt"
        if not annotation_path.is_file():
            raise FileNotFoundError(
                f"no annotation matching image stem {image_path.stem!r}"
            )
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            raise FileNotFoundError(f"could not read image {image_path}")
        rows = [
            line.split() for line in annotation_path.read_text().splitlines() if line
        ]
        class_labels = [int(row[0]) for row in rows]
        boxes = [[float(value) for value in row[1:5]] for row in rows]
        pipeline.set_random_seed(seed + index)
        augmented = pipeline(image=image, bboxes=boxes, class_labels=class_labels)

        relative_image = image_path.relative_to(source_images)
        destination_image = output_images / relative_image
        destination_image.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(destination_image), augmented["image"]):
            raise OSError(f"could not write augmented image {destination_image}")
        destination_annotation = output_annotations / relative_image.with_suffix(".txt")
        destination_annotation.parent.mkdir(parents=True, exist_ok=True)
        destination_annotation.write_text(
            "".join(
                f"{int(class_id)} {' '.join(f'{coordinate:.6f}' for coordinate in box)}\n"
                for class_id, box in zip(
                    augmented["class_labels"], augmented["bboxes"], strict=True
                )
            )
        )

    names_path = source_annotations / "names.yaml"
    if names_path.is_file():
        (output_annotations / "names.yaml").write_bytes(names_path.read_bytes())
    return destination_root


@hydra.main(version_base=None, config_path="../../../conf", config_name="runs/baseline")
def main(cfg: DictConfig) -> None:
    register_configs()
    run_augment_stage(cfg)


if __name__ == "__main__":
    main()
