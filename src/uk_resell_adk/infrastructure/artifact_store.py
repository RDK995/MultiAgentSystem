from __future__ import annotations

"""Artifact path resolution and read helpers for the visualizer API."""

from pathlib import Path
from urllib.parse import parse_qs
from typing import Any


def resolve_artifact_path(query: str, *, project_root: Path | None = None) -> Path | None:
    params = parse_qs(query)
    raw_path = params.get("path", [""])[0]
    if not raw_path:
        return None

    root = (project_root or Path.cwd()).resolve()
    artifact_path = Path(raw_path)
    if not artifact_path.is_absolute():
        artifact_path = root / artifact_path

    try:
        resolved = artifact_path.resolve(strict=True)
    except FileNotFoundError:
        return None

    if root not in resolved.parents and resolved != root:
        return None
    return resolved


def read_artifact_preview(path: Path, *, max_chars: int = 12000) -> dict[str, Any]:
    if path.suffix.lower() == ".html":
        return {
            "path": str(path),
            "kind": "html",
            "content": path.read_text(encoding="utf-8", errors="ignore"),
        }
    return {
        "path": str(path),
        "kind": "text",
        "content": path.read_text(encoding="utf-8", errors="ignore")[:max_chars],
    }


def read_artifact_file(path: Path) -> tuple[bytes, str]:
    content = path.read_bytes()
    content_type = "text/html; charset=utf-8" if path.suffix.lower() == ".html" else "text/plain; charset=utf-8"
    return content, content_type
