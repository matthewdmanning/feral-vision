"""Google Compute client integration contract used by cloud preflight."""

from __future__ import annotations

import json
from pathlib import Path

import googleapiclient.discovery_cache
from googleapiclient.http import HttpMockSequence

from scripts.cloud_preflight import get_compute_instance


# ---------------------------------------------------------------------------
# Helpers / local fixtures
# ---------------------------------------------------------------------------


class _RecordingHttpMockSequence(HttpMockSequence):
    """Google's HTTP response sequence with a record of outgoing requests."""

    def __init__(self, responses: list[tuple[dict[str, str], str]]) -> None:
        super().__init__(responses)
        self.requests: list[tuple[str, str]] = []

    def request(
        self,
        uri: str,
        method: str = "GET",
        body: str | None = None,
        headers: dict[str, str] | None = None,
        **kwargs: object,
    ) -> tuple[object, bytes]:
        """Record each request before returning Google's configured mock response."""
        self.requests.append((uri, method))
        return super().request(uri, method=method, body=body, headers=headers, **kwargs)


def _compute_discovery_document() -> str:
    """Read the Compute v1 discovery document packaged with Google's client."""
    path = (
        Path(googleapiclient.discovery_cache.__file__).parent
        / "documents"
        / "compute.v1.json"
    )
    return path.read_text()


# ---------------------------------------------------------------------------
# Compute Engine request contract
# ---------------------------------------------------------------------------


def test_get_compute_instance_calls_selected_compute_endpoint() -> None:
    """The client requests and returns the manifest-selected GCE instance."""
    response = {
        "kind": "compute#instance",
        "name": "feral-vision-trainer",
        "zone": "https://www.googleapis.com/compute/v1/projects/project/zones/us-central1-a",
        "status": "RUNNING",
        "serviceAccounts": [{"email": "trainer@project.iam.gserviceaccount.com"}],
    }
    http = _RecordingHttpMockSequence(
        [
            ({"status": "200"}, _compute_discovery_document()),
            ({"status": "200"}, json.dumps(response)),
        ]
    )

    instance = get_compute_instance(
        "project", "us-central1-a", "feral-vision-trainer", http=http
    )

    assert instance == response
    assert http.requests[-1] == (
        "https://compute.googleapis.com/compute/v1/projects/project/"
        "zones/us-central1-a/instances/feral-vision-trainer?alt=json",
        "GET",
    )
