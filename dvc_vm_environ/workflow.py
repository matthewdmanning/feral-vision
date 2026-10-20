"""Independent DVC Dataset registration and portable handoff functions."""

import fcntl
import hashlib
import io
import json
import logging
import os
import re
import shutil
import stat
import sys
import tarfile
import tempfile
from contextlib import contextmanager, redirect_stdout
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

import yaml
from dvc.repo import Repo
from dvc_data.hashfile.build import build
from dvc_data.hashfile.db.local import LocalHashFileDB
from dvc_data.hashfile.hash import hash_file
from dvc_objects.fs.local import LocalFileSystem


class Invalid(ValueError):
    """Indicate an invalid input or an identity policy rejection."""


class Mismatch(RuntimeError):
    """Indicate a failed content or publication verification."""


class UniqueLoader(yaml.SafeLoader):
    """Reject duplicate YAML keys rather than silently replacing evidence."""


def unique_mapping(loader, node):
    """Load a mapping with one value per key.

    Raises
    ------
    Invalid
        If a key is duplicated or cannot be used as a string key.
    """
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if not isinstance(key, str) or key in result:
            raise Invalid("Metadata contains a non-string or duplicate key")
        result[key] = loader.construct_object(value_node)
    return result


UniqueLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping
)


def json_mapping(pairs):
    """Read JSON objects without accepting ambiguous duplicate keys.

    Raises
    ------
    Invalid
        If a JSON object repeats a key.
    """
    result = {}
    for key, value in pairs:
        if key in result:
            raise Invalid("JSON contains a duplicate key")
        result[key] = value
    return result


def read_json(data):
    """Decode strict JSON.

    Returns
    -------
    object
        Parsed JSON value, without non-finite numeric extensions.
    """

    def reject_constant(value):
        raise Invalid("JSON contains a non-finite number")

    return json.loads(
        data, object_pairs_hook=json_mapping, parse_constant=reject_constant
    )


def provenance(value):
    """Validate the caller's version-1 provenance references.

    Returns
    -------
    dict
        Original parsed values, preserving reference strings.
    """
    if not isinstance(value, dict) or set(value) - {
        "origin",
        "source_refs",
        "lineage_ref",
        "model_ref",
    }:
        raise Invalid("Provenance must be an object with supported fields")
    if value.get("origin") not in ("acquired", "derived", "inference"):
        raise Invalid("Provenance origin must be acquired, derived, or inference")
    refs = value.get("source_refs")
    if not isinstance(refs, list) or not refs:
        raise Invalid("source_refs must be a nonempty list")
    for ref in [*refs, *[value[k] for k in ("lineage_ref", "model_ref") if k in value]]:
        if not isinstance(ref, str) or not ref.strip():
            raise Invalid("Provenance references must be nonempty strings")
        if ref.startswith(("/", "./", "../", "file:")):
            raise Invalid(
                "Provenance must reference retained sources, not worker-local paths"
            )
    for origin, field in (("derived", "lineage_ref"), ("inference", "model_ref")):
        if value["origin"] == origin and field not in value:
            raise Invalid(f"{origin} provenance requires {field}")
    return value


def identity_key(dataset_id):
    """Map an opaque caller ID to a safe catalogue directory.

    Returns
    -------
    str
        SHA-256 of the original UTF-8 identifier.
    """
    if not isinstance(dataset_id, str) or not dataset_id.strip():
        raise Invalid("Dataset ID must be a nonempty string")
    return hashlib.sha256(dataset_id.encode("utf-8")).hexdigest()


def remote_locator(value):
    """Accept a non-secret GCS URL or an absolute filesystem remote.

    Returns
    -------
    str
        Validated locator, suitable for returning to the caller.
    """
    if not isinstance(value, str) or not value or any(c in value for c in "\r\n\0"):
        raise Invalid("A non-secret remote locator is required")
    parsed = urlsplit(value)
    if parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise Invalid(
            "Remote locator must not carry credentials, a query, or a fragment"
        )
    if parsed.scheme == "gs" and parsed.netloc and "@" not in parsed.netloc:
        return value
    if not parsed.scheme and Path(value).is_absolute():
        return value
    raise Invalid("Use gs://bucket/prefix or an absolute local remote path")


def controlled(name):
    return name in {
        ".git",
        ".dvc",
        ".dvcignore",
        ".gitignore",
        ".gitattributes",
        "dvc.yaml",
        "dvc.lock",
    } or name.endswith(".dvc")


def safe_relative(value):
    """Validate native index and archive paths before filesystem use.

    Returns
    -------
    str
        The original normalized relative path.
    """
    if (
        not isinstance(value, str)
        or not value
        or value in (".", "..")
        or "\\" in value
        or "\0" in value
    ):
        raise Invalid("Invalid relative path")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or str(path) != value
        or any(p in (".", "..") or controlled(p) for p in path.parts)
    ):
        raise Invalid("Unsafe or control-file path")
    return value


def check_dataset_files(root):
    """Require a nonempty tree of regular files without control files or links.

    Returns
    -------
    list[Path]
        Every regular dataset file, with traversal independent of ignore rules.
    """
    if root.is_symlink() or not root.is_dir():
        raise Invalid("Dataset must be a real directory")
    files = []
    for current, dirs, names in os.walk(root, followlinks=False):
        for name in dirs + names:
            path = Path(current) / name
            safe_relative(path.relative_to(root).as_posix())
            mode = path.lstat().st_mode
            if not stat.S_ISREG(mode) and not stat.S_ISDIR(mode):
                raise Invalid("Dataset contains a symlink or special file")
            if stat.S_ISREG(mode):
                files.append(path)
    if not files:
        raise Invalid("Dataset must contain at least one regular file")
    return files


def record(data, *, catalogue=False):
    """Validate a supported single-output DVC record before DVC loads it.

    Returns
    -------
    dict
        Parsed, restricted DVC record.
    """
    value = yaml.load(data, Loader=UniqueLoader)
    allowed = {"outs"} if catalogue else {"outs", "meta"}
    if not isinstance(value, dict) or set(value) != allowed:
        raise Invalid("Unexpected DVC record fields")
    outs = value["outs"]
    if not isinstance(outs, list) or len(outs) != 1 or not isinstance(outs[0], dict):
        raise Invalid("Record must have exactly one output")
    out = outs[0]
    expected = {"path", "md5", "hash", "size"}
    if not catalogue:
        expected.add("nfiles")
    if (
        set(out) != expected
        or out["path"] != ("catalogue.tar" if catalogue else "dataset")
        or out["hash"] != "md5"
    ):
        raise Invalid("Unsupported output path, algorithm, or fields")
    pattern = r"[0-9a-f]{32}" + ("" if catalogue else r"\.dir")
    if not isinstance(out["md5"], str) or not re.fullmatch(pattern, out["md5"]):
        raise Invalid("Invalid native DVC digest")
    for field in expected & {"size", "nfiles"}:
        if type(out[field]) is not int or out[field] < (1 if field == "nfiles" else 0):
            raise Invalid("Invalid DVC size or file count")
    if not catalogue:
        meta = value["meta"]
        if (
            not isinstance(meta, dict)
            or set(meta) != {"version", "id", "provenance"}
            or type(meta["version"]) is not int
            or meta["version"] != 1
        ):
            raise Invalid("Unsupported registration metadata version or fields")
        identity_key(meta["id"])
        provenance(meta["provenance"])
    return value


def validate_index(data, selected):
    """Check native index bytes and individual membership paths.

    Returns
    -------
    list[dict]
        Validated native DVC entries.
    """
    out = selected["outs"][0]
    # DVC hashes the exact serialized index bytes; do not reconstruct its serializer.
    with tempfile.TemporaryDirectory(prefix="index-") as temp:
        path = Path(temp) / "index"
        path.write_bytes(data)
        _, info = hash_file(str(path), LocalFileSystem(), "md5")
    if info.value + ".dir" != out["md5"]:
        raise Mismatch("Retained index digest does not match the selected record")
    entries = read_json(data)
    if not isinstance(entries, list) or len(entries) != out["nfiles"]:
        raise Invalid("Invalid native index membership count")
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"md5", "relpath"}:
            raise Invalid("Unsupported native index entry")
        name = safe_relative(entry["relpath"])
        if (
            name in seen
            or not isinstance(entry["md5"], str)
            or not re.fullmatch(r"[0-9a-f]{32}", entry["md5"])
        ):
            raise Invalid("Duplicate index path or invalid file digest")
        seen.add(name)
    for name in seen:
        if any(str(p) in seen for p in PurePosixPath(name).parents if str(p) != "."):
            raise Invalid("Index has conflicting file and directory paths")
    return entries


@contextmanager
def isolated_repo(root, remote):
    """Create an independent no-SCM repository with copy-only cache links.

    Yields
    ------
    Repo
        Repository configured without inheriting project or user DVC settings.
    """
    root.mkdir(parents=True, exist_ok=True)
    # Explicitly suppress system/global configuration, including inherited remotes.
    config = {
        "core": {"no_scm": True, "analytics": False, "remote": "storage"},
        "cache": {"type": ["copy"], "dir": str(root / ".dvc" / "cache")},
        "remote": {"storage": {"url": remote}},
    }
    overrides = {
        "DVC_SYSTEM_CONFIG_DIR": str(root / ".isolated-system"),
        "DVC_GLOBAL_CONFIG_DIR": str(root / ".isolated-global"),
        "DVC_SITE_CACHE_DIR": str(root / ".site-cache"),
    }
    previous = {key: os.environ.get(key) for key in overrides}
    try:
        os.environ.update(overrides)
        created = Repo.init(str(root), no_scm=True)
        created.close()
        with Repo(str(root), config=config) as repo:
            yield repo
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def publish(repo, target):
    """Push the catalogue archive and prove its remote availability.

    Raises
    ------
    Mismatch
        If the archive object is absent locally or remotely after publication.
    """
    digest = record(target.read_bytes(), catalogue=True)["outs"][0]["md5"]
    if not repo.cache.local.exists(digest):
        raise Mismatch("Publication has missing local cache objects")
    repo.push(targets=[str(target)], remote="storage", jobs=2)
    if repo.status(targets=[str(target)], cloud=True, remote="storage", jobs=2):
        raise Mismatch(
            "Publication remote status is incomplete; descriptor was not updated"
        )
    if not repo.cloud.get_remote_odb("storage", "status").exists(digest):
        raise Mismatch("Publication remote is missing a selected object")


def native_verify(root, selected):
    """Hash every dataset file using a fresh DVC tree and hash state.

    Raises
    ------
    Mismatch
        If names, bytes, or recorded aggregate properties differ.
    """
    check_dataset_files(root)
    with tempfile.TemporaryDirectory(prefix="hash-") as temp:
        fs = LocalFileSystem()
        odb = LocalHashFileDB(fs, temp)
        _, meta, tree = build(odb, str(root), fs, "md5", dry_run=True)
    out = selected["outs"][0]
    if (
        tree.hash_info.value != out["md5"]
        or meta.size != out["size"]
        or meta.nfiles != out["nfiles"]
    ):
        raise Mismatch(
            "Dataset filenames or contents do not match the selected DVC record"
        )


def handoff_result(root, selected):
    """Build a portable handoff result after successful verification.

    Returns
    -------
    dict
        Caller identity, DVC hash, and absolute handoff paths.
    """
    return {
        "id": selected["meta"]["id"],
        "dataset_hash": selected["outs"][0]["md5"],
        "dataset": str(root / "dataset"),
        "record": str(root / "dataset.dvc"),
        "index": str(root / "dataset.dir"),
    }


def verify(staged):
    """Verify retained metadata and freshly hashed portable Dataset contents.

    Returns
    -------
    dict
        Verified identity and handoff paths.
    """
    root = Path(staged).absolute()
    if root.is_symlink() or not root.is_dir():
        raise Invalid("Staged handoff must be a real directory")
    for name in ("dataset.dvc", "dataset.dir"):
        path = root / name
        if path.is_symlink() or not path.is_file():
            raise Invalid("Handoff record and index must be regular files")
    selected = record((root / "dataset.dvc").read_bytes())
    validate_index((root / "dataset.dir").read_bytes(), selected)
    native_verify(root / "dataset", selected)
    return handoff_result(root, selected)


def read_catalogue(archive):
    """Read only validated regular record/index pairs from a metadata archive.

    Returns
    -------
    dict
        Safe internal IDs mapped to exact original record and index bytes.
    """
    members = {}
    with tarfile.open(archive, "r:") as bundle:
        for item in bundle:
            if (
                not item.isfile()
                or not re.fullmatch(r"[0-9a-f]{64}/dataset\.(dvc|dir)", item.name)
                or item.name in members
                or item.pax_headers
            ):
                raise Invalid(
                    "Unsafe, duplicate, or unexpected catalogue archive member"
                )
            members[item.name] = bundle.extractfile(item).read()
    keys = {name.split("/")[0] for name in members}
    result = {}
    for key in keys:
        if {f"{key}/dataset.dvc", f"{key}/dataset.dir"} - members.keys():
            raise Invalid("Catalogue registration lacks a record or index")
        raw = members[f"{key}/dataset.dvc"]
        index = members[f"{key}/dataset.dir"]
        selected = record(raw)
        if identity_key(selected["meta"]["id"]) != key:
            raise Invalid("Catalogue ID does not match its internal directory")
        validate_index(index, selected)
        result[key] = (raw, index)
    return result


def restore_catalogue(descriptor, root, remote):
    """Recover the metadata archive using only its descriptor and remote.

    Returns
    -------
    dict
        Validated catalogue with exact record and native index bytes.
    """
    if descriptor.is_symlink() or not descriptor.is_file():
        raise Invalid("Catalogue descriptor must exist as a regular file")
    raw = descriptor.read_bytes()
    record(raw, catalogue=True)
    with isolated_repo(root, remote) as repo:
        target = root / "catalogue.tar.dvc"
        target.write_bytes(raw)
        repo.pull(targets=[str(target)], remote="storage", jobs=2)
        archive = root / "catalogue.tar"
        _, info = hash_file(str(archive), LocalFileSystem(), "md5")
        output = record(raw, catalogue=True)["outs"][0]
        if info.value != output["md5"] or archive.stat().st_size != output["size"]:
            raise Mismatch("Downloaded catalogue archive digest mismatch")
        return read_catalogue(archive)


def write_catalogue(path, entries):
    """Write a deterministic tar of exact registration records and native indexes.

    Parameters
    ----------
    path : Path
        Output archive, separate from datasets and active DVC tracking files.
    entries : dict
        Complete catalogue metadata for this snapshot.
    """
    with tarfile.open(path, "w", format=tarfile.USTAR_FORMAT) as bundle:
        for key, pair in sorted(entries.items()):
            for name, data in zip(("dataset.dvc", "dataset.dir"), pair, strict=True):
                info = tarfile.TarInfo(f"{key}/{name}")
                info.size, info.mode, info.mtime = len(data), 0o644, 0
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                bundle.addfile(info, io.BytesIO(data))


@contextmanager
def workspace_lock(root):
    """Fail immediately when another writer holds the local workspace lock.

    Yields
    ------
    None
        Exclusive access for one catalogue writer.
    """
    root.mkdir(parents=True, exist_ok=True)
    fd = os.open(root / "writer.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise Invalid("Workspace already has an active writer") from exc
        yield


def atomic_descriptor(path, data):
    """Install a fully published bootstrap descriptor by atomic replacement.

    Parameters
    ----------
    path : Path
        Caller-owned bootstrap pointer, updated only after successful pushes.
    data : bytes
        Exact native DVC archive descriptor.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".catalogue-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def register(
    dataset,
    dataset_id,
    provenance_path,
    workspace,
    remote_url,
    catalogue,
    force=False,
    new_catalogue=False,
):
    """Register and publish one immutable identity and a complete metadata snapshot.

    Returns
    -------
    dict
        ID, native Dataset hash, durable local descriptor path, and remote locator.
    """
    source, work, descriptor = (
        Path(p).absolute() for p in (dataset, workspace, catalogue)
    )
    remote = remote_locator(remote_url)
    key = identity_key(dataset_id)
    provenance_file = Path(provenance_path)
    if provenance_file.is_symlink() or not provenance_file.is_file():
        raise Invalid("Provenance must be a regular JSON file")
    supplied = provenance(read_json(provenance_file.read_bytes()))
    check_dataset_files(source)
    if not urlsplit(remote).scheme:
        remote_path = Path(remote).resolve()
        for local in (source.resolve(), work.resolve()):
            if remote_path.is_relative_to(local) or local.is_relative_to(remote_path):
                raise Invalid(
                    "Local remote must be separate from source and managed workspace"
                )
    if (
        work.resolve().is_relative_to(source.resolve())
        or source.resolve().is_relative_to(work.resolve())
        or descriptor.resolve().is_relative_to(source.resolve())
    ):
        raise Invalid(
            "Source must be separate from managed workspace and catalogue descriptor"
        )
    with workspace_lock(work):
        if new_catalogue:
            if descriptor.exists() or descriptor.is_symlink():
                raise Invalid("--new-catalogue requires an absent descriptor")
        elif not descriptor.is_file():
            raise Invalid(
                "Catalogue descriptor is required; use --new-catalogue only deliberately"
            )
        with tempfile.TemporaryDirectory(prefix="operation-", dir=work) as operation:
            op = Path(operation)
            entries = (
                {}
                if new_catalogue
                else restore_catalogue(descriptor, op / "restore", remote)
            )
            registration = op / "registration"
            with isolated_repo(registration, remote) as repo:
                data_dir = registration / "dataset"
                shutil.copytree(source, data_dir, symlinks=True)
                check_dataset_files(data_dir)
                repo.add(str(data_dir))
                target = registration / "dataset.dvc"
                value = yaml.load(target.read_bytes(), Loader=UniqueLoader)
                value["meta"] = {"version": 1, "id": dataset_id, "provenance": supplied}
                raw = yaml.safe_dump(
                    value, sort_keys=False, allow_unicode=True
                ).encode()
                selected = record(raw)
                digest = selected["outs"][0]["md5"]
                if key in entries:
                    previous = record(entries[key][0])
                    if (
                        previous["meta"] != selected["meta"]
                        or previous["outs"][0]["md5"] != digest
                    ):
                        raise Invalid(
                            "Dataset ID is immutable: contents or provenance changed"
                        )
                    if not force:
                        raise Invalid(
                            "Dataset ID already exists; explicit --force is required for retry"
                        )
                    raw = entries[key][0]
                    selected = previous
                else:
                    matches = [
                        record(pair[0])["meta"]["id"]
                        for pair in entries.values()
                        if record(pair[0])["outs"][0]["md5"] == digest
                    ]
                    if matches and not force:
                        raise Invalid(
                            "Dataset content already registered; use --force for a distinct identity. Matching IDs: "
                            + json.dumps(matches)
                        )
                target.write_bytes(raw)
                index = Path(repo.cache.local.oid_to_path(digest)).read_bytes()
                validate_index(index, selected)
                native_verify(data_dir, selected)
                # Dataset files stay in Cloud Storage; only the catalogue is published.
                entries[key] = (raw, index)
            archive_root = op / "publication"
            with isolated_repo(archive_root, remote) as repo:
                archive = archive_root / "catalogue.tar"
                write_catalogue(archive, entries)
                repo.add(str(archive))
                target = archive_root / "catalogue.tar.dvc"
                bootstrap = target.read_bytes()
                archive_record = record(bootstrap, catalogue=True)
                publish(repo, target)
            snapshots = work / "snapshots"
            snapshots.mkdir(exist_ok=True)
            if descriptor.exists():
                old = descriptor.read_bytes()
                old_digest = record(old, catalogue=True)["outs"][0]["md5"]
                old_path = snapshots / f"{old_digest}.dvc"
                if old_path.exists() and old_path.read_bytes() != old:
                    raise Mismatch("An immutable snapshot descriptor differs")
                old_path.write_bytes(old)
            snapshot = snapshots / f"{archive_record['outs'][0]['md5']}.dvc"
            if snapshot.exists() and snapshot.read_bytes() != bootstrap:
                raise Mismatch("An immutable snapshot descriptor differs")
            snapshot.write_bytes(bootstrap)
            registrations = work / "registrations"
            registrations.mkdir(exist_ok=True)
            retained = registrations / key
            if not retained.exists():
                shutil.move(str(registration), retained)
            catalogues = work / "catalogues"
            catalogues.mkdir(exist_ok=True)
            retained_archive = catalogues / archive_record["outs"][0]["md5"]
            if not retained_archive.exists():
                shutil.move(str(archive_root), retained_archive)
            atomic_descriptor(descriptor, bootstrap)
    return {
        "id": dataset_id,
        "dataset_hash": digest,
        "catalogue": str(descriptor),
        "remote_url": remote,
    }


def stage(catalogue, dataset_id, destination, remote_url):
    """Verify a Dataset already copied from Cloud Storage against its record.

    The caller copies the files to ``destination/dataset``; this adds the
    catalogue record and index beside it, then verifies the files.

    Returns
    -------
    dict
        Verified ID, hash, dataset, record, and index paths.
    """
    remote = remote_locator(remote_url)
    key = identity_key(dataset_id)
    dest = Path(destination).absolute()
    with tempfile.TemporaryDirectory(prefix="stage-") as temporary:
        entries = restore_catalogue(
            Path(catalogue).absolute(), Path(temporary) / "catalogue", remote
        )
    if key not in entries or record(entries[key][0])["meta"]["id"] != dataset_id:
        raise Invalid("Dataset ID is absent from this catalogue snapshot")
    if (
        dest.is_symlink()
        or not dest.is_dir()
        or [item.name for item in dest.iterdir()] != ["dataset"]
    ):
        raise Invalid("Destination must hold only the copied dataset directory")
    raw, index = entries[key]
    (dest / "dataset.dvc").write_bytes(raw)
    (dest / "dataset.dir").write_bytes(index)
    try:
        return verify(dest)
    except Exception:
        (dest / "dataset.dvc").unlink()
        (dest / "dataset.dir").unlink()
        raise


@contextmanager
def diagnostics_only():
    """Route even DVC's prebound stdout handlers to stderr during an operation.

    Yields
    ------
    None
        A stdout channel reserved for the final successful JSON result.
    """
    sys.stdout.flush()
    saved = os.dup(1)
    try:
        os.dup2(2, 1)
        with redirect_stdout(sys.stderr):
            yield
    finally:
        sys.stdout.flush()
        os.dup2(saved, 1)
        os.close(saved)


def shell_call(operation, **arguments):
    """Execute a shell-parsed operation with clean JSON and safe diagnostics.

    Returns
    -------
    int
        Zero on success, two for invalid input, one for an operational failure.
    """
    try:
        with diagnostics_only():
            result = {"register": register, "stage": stage, "verify": verify}[
                operation
            ](**arguments)
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except (Invalid, json.JSONDecodeError, yaml.YAMLError, UnicodeError) as exc:
        # Parser exceptions can include source snippets; only our own messages are safe.
        print(
            str(exc) if isinstance(exc, Invalid) else "Invalid JSON or YAML metadata",
            file=sys.stderr,
        )
        return 2
    except Mismatch as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print(
            f"Operation failed ({type(exc).__name__}); check input files and remote access. Catalogue was not reported as published.",
            file=sys.stderr,
        )
        return 1


# DVC uses logging for progress; keep protocol stdout exclusively for the result.
logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
