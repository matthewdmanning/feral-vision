"""Register static model-definition metadata in the MLflow Model Registry.

Inspection (inspect_model MCP tool or adapter.inspect()) produces metadata;
this script consumes it and stores the result in MLflow. When the configured
tracking service is unavailable, it queues the registration in a temporary
offline journal for replay.

Usage:
    uv run python scripts/register_model.py \\
        --source hf_hub \\
        --model-id facebook/detr-resnet-50

    uv run python scripts/register_model.py \\
        --source ultralytics \\
        --model-id yolo11n-seg.pt

    uv run python scripts/register_model.py \\
        --source torch_hub \\
        --model-id ultralytics/ultralytics \\
        --weights-id yolo11n-seg \\
        --fetch-if-needed
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def main() -> None:
    """Inspect a model and register its static metadata with MLflow."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--source",
        required=True,
        help="Adapter source key (hf_hub, ultralytics, torch_hub, ...)",
    )
    parser.add_argument(
        "--model-id",
        required=True,
        dest="model_id",
        help="Hub repo ID or model filename",
    )
    parser.add_argument(
        "--weights-id",
        nargs="*",
        dest="weights_id",
        help="Weight filenames or asset names",
    )
    parser.add_argument(
        "--weights-location",
        dest="weights_location",
        help="Local path to cache weights",
    )
    parser.add_argument(
        "--fetch-if-needed",
        action="store_true",
        dest="fetch_if_needed",
        help="Download model weights to inspect architecture when hub metadata is unavailable",
    )
    parser.add_argument(
        "--tracking-uri",
        default=os.environ.get("MLFLOW_TRACKING_URI"),
        help="MLflow tracking URI; absent or unreachable queues a temporary offline journal",
    )
    args = parser.parse_args()

    if args.tracking_uri:
        import mlflow

        mlflow.set_tracking_uri(args.tracking_uri)

    from omegaconf import OmegaConf

    from feral_vision.models.register_model import _get_adapter, register_model

    cfg_dict: dict = {
        "architecture": {"source": args.source, "id": args.model_id, "location": None}
    }
    if args.weights_id:
        cfg_dict["weights"] = {
            "source": args.source,
            "id": args.weights_id,
            "location": args.weights_location,
        }
    cfg = OmegaConf.create(cfg_dict)

    adapter = _get_adapter(args.source)
    props, metadata = adapter.inspect(cfg, fetch_if_needed=args.fetch_if_needed)

    register_model(args.model_id, cfg, props, metadata)

    print(
        json.dumps(
            {
                "registered": args.model_id,
                "tracking_uri": args.tracking_uri,
                "model_outputs": [t.value for t in props.model_outputs],
                "metadata": metadata,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
