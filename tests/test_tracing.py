from __future__ import annotations

from typing import Any

from uk_resell_adk import tracing


def test_configure_langsmith_does_nothing_without_api_key(monkeypatch: Any) -> None:
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)

    tracing.configure_langsmith()

    assert "LANGSMITH_TRACING" not in tracing.os.environ
    assert "LANGSMITH_PROJECT" not in tracing.os.environ


def test_configure_langsmith_sets_defaults_with_api_key(monkeypatch: Any) -> None:
    monkeypatch.setenv("LANGSMITH_API_KEY", "key")
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)

    tracing.configure_langsmith(project_name="custom-project")

    assert tracing.os.environ["LANGSMITH_TRACING"] == "true"
    assert tracing.os.environ["LANGSMITH_PROJECT"] == "custom-project"


def test_configure_langsmith_preserves_existing_values(monkeypatch: Any) -> None:
    monkeypatch.setenv("LANGSMITH_API_KEY", "key")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGSMITH_PROJECT", "existing")

    tracing.configure_langsmith(project_name="new")

    assert tracing.os.environ["LANGSMITH_TRACING"] == "false"
    assert tracing.os.environ["LANGSMITH_PROJECT"] == "existing"


def test_traceable_returns_passthrough_when_langsmith_missing(monkeypatch: Any) -> None:
    monkeypatch.setattr(tracing, "_traceable", None)

    decorator = tracing.traceable(name="x")

    def sample() -> str:
        return "ok"

    wrapped = decorator(sample)
    assert wrapped is sample
    assert wrapped() == "ok"


def test_traceable_delegates_to_langsmith_when_available(monkeypatch: Any) -> None:
    calls: dict[str, Any] = {}

    def fake_traceable(*args: Any, **kwargs: Any):
        calls["args"] = args
        calls["kwargs"] = kwargs

        def _decorator(func: Any) -> Any:
            calls["func"] = func
            return func

        return _decorator

    monkeypatch.setattr(tracing, "_traceable", fake_traceable)

    decorator = tracing.traceable(name="abc", run_type="tool")

    def sample() -> int:
        return 1

    wrapped = decorator(sample)

    assert wrapped is sample
    assert calls["kwargs"] == {"name": "abc", "run_type": "tool"}
    assert calls["func"] is sample
