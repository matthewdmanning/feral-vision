"""Exercise the release independently of the production checkout."""

from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile

import pytest


@pytest.fixture
def released_files(tmp_path: Path) -> Path:
    """Build and unpack the actual wheel into an isolated installation directory."""
    root = Path(__file__).resolve().parents[1]
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(tmp_path / "dist")],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    wheel = next((tmp_path / "dist").glob("*.whl"))
    installation = tmp_path / "installed"
    with ZipFile(wheel) as archive:
        archive.extractall(installation)
    return installation


def test_wheel_separates_library_starters_and_production(released_files: Path) -> None:
    """Release only library code and starter assets, including non-Python files."""
    roots = {path.name for path in released_files.iterdir()}
    assert roots == {
        "sightkit_learn",
        "templates",
        next(released_files.glob("*.dist-info")).name,
    }
    templates = released_files / "templates"
    assert {p.name for p in templates.iterdir() if p.is_dir()} == {
        "conf",
        "scripts",
        "deploy",
        "terraform",
        "data",
        "models",
    }
    for asset in (
        "conf/runs/detection.yaml",
        "scripts/runs/container_train.sh",
        "deploy/Dockerfile.gcp",
        "terraform/runs/detection/main.tf",
    ):
        assert (templates / asset).is_file()
    assert not (released_files / "sightkit_learn" / "data" / "fetch.py").exists()


def test_released_trainer_composes_copied_starter_without_checkout(
    released_files: Path, tmp_path: Path
) -> None:
    """Compose the packaged recipe using only the installed library and assets."""
    command = """
import runpy
import sys
from pathlib import Path
sys.path.insert(0, sys.argv.pop(1))
import sightkit_learn
assert Path(sightkit_learn.__file__).is_relative_to(sys.path[0])
runpy.run_module('sightkit_learn.training.trainer', run_name='__main__')
"""
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            command,
            str(released_files),
            "--config-dir",
            str(released_files / "templates" / "conf"),
            "--config-name",
            "runs/detection",
            "--cfg",
            "job",
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "train:" in result.stdout
    assert "task: detection" in result.stdout
