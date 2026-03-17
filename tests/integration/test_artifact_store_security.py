from __future__ import annotations

from pathlib import Path

from uk_resell_adk.infrastructure.artifact_store import resolve_artifact_path


def test_resolve_artifact_path_blocks_parent_traversal(tmp_path: Path) -> None:
    root = tmp_path / "project"
    reports = root / "reports"
    reports.mkdir(parents=True)
    artifact = reports / "sample.html"
    artifact.write_text("<html>ok</html>", encoding="utf-8")

    outside = tmp_path / "outside.txt"
    outside.write_text("nope", encoding="utf-8")
    traversal = f"path=../{outside.name}"

    resolved = resolve_artifact_path(traversal, project_root=root)

    assert resolved is None
    assert resolve_artifact_path(f"path=reports/{artifact.name}", project_root=root) == artifact.resolve()


def test_resolve_artifact_path_blocks_absolute_paths_outside_project(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir(parents=True)

    outside = tmp_path / "outside.html"
    outside.write_text("<html>outside</html>", encoding="utf-8")

    resolved = resolve_artifact_path(f"path={outside}", project_root=root)

    assert resolved is None
