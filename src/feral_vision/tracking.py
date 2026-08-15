"""Tracking URI validation shared by local and cloud training entrypoints."""

from __future__ import annotations

from urllib.parse import urlparse

_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def validate_tracking_uri(uri: str) -> str:
    """Use this function to validate an HTTPS or explicitly local MLflow server URI."""
    parsed = urlparse(uri)
    if parsed.scheme == "https" and parsed.netloc:
        return uri
    if parsed.scheme == "http" and parsed.hostname in _LOCAL_HOSTS:
        return uri
    raise ValueError(
        "tracking URI must be an HTTPS endpoint or an explicit local MLflow server"
    )
