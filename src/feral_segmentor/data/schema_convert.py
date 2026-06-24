"""Convert appearance schema JSON to Hydra-compatible YAML.

Usage:
    python -m feral_segmentor.data.schema_convert \\
        --input  src/feral_segmentor/data/draft_appearance_schema.json \\
        --output conf/schemas/appearance.yaml
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml


def _convert_node(node: dict) -> dict:
    """Recursively convert a schema node to a plain dict for YAML output."""
    out: dict = {
        "input_type": node["input_type"],
        "description": node.get("description", ""),
    }
    options = node.get("options", {})
    converted_options: dict = {}
    for key, val in options.items():
        if isinstance(val, str):
            converted_options[key] = {"description": val}
        elif isinstance(val, dict):
            converted_options[key] = _convert_node(val)
        else:
            converted_options[key] = val
    if converted_options:
        out["options"] = converted_options
    return out


def convert(input_path: str | Path, output_path: str | Path) -> None:
    """Convert JSON appearance schema to YAML and write to output_path."""
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with input_path.open(encoding="utf-8") as f:
        schema = json.load(f)

    converted = {key: _convert_node(val) for key, val in schema.items()}

    with output_path.open("w", encoding="utf-8") as f:
        yaml.dump(converted, f, allow_unicode=True, sort_keys=False)

    print(f"written: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Path to appearance schema JSON")
    parser.add_argument("--output", required=True, help="Output path for YAML")
    args = parser.parse_args()
    convert(args.input, args.output)


if __name__ == "__main__":
    main()
