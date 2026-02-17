from __future__ import annotations

from typing import Any

from uk_resell_adk import tracing


def test_configure_tracing_langsmith_does_nothing_without_api_key(monkeypatch: Any) -> None:
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.setenv("ENABLE_LANGSMITH_TRACING", "true")
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)

    tracing.configure_tracing()

    assert "LANGSMITH_TRACING" not in tracing.os.environ
    assert "LANGSMITH_PROJECT" not in tracing.os.environ


def test_configure_tracing_sets_langsmith_defaults_with_api_key(monkeypatch: Any) -> None:
    monkeypatch.setenv("LANGSMITH_API_KEY", "key")
    monkeypatch.setenv("ENABLE_LANGSMITH_TRACING", "true")
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)

    tracing.configure_tracing(project_name="custom-project")

    assert tracing.os.environ["LANGSMITH_TRACING"] == "true"
    assert tracing.os.environ["LANGSMITH_PROJECT"] == "custom-project"


def test_configure_tracing_sets_langfuse_defaults_with_keys(monkeypatch: Any) -> None:
    monkeypatch.setenv("ENABLE_LANGFUSE_TRACING", "true")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    monkeypatch.setenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")
    monkeypatch.delenv("LANGFUSE_TRACING_ENABLED", raising=False)
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)

    tracing.configure_tracing()

    assert tracing.os.environ["LANGFUSE_TRACING_ENABLED"] == "true"
    assert tracing.os.environ["LANGFUSE_HOST"] == "https://cloud.langfuse.com"


def test_configure_tracing_preserves_existing_langsmith_values(monkeypatch: Any) -> None:
    monkeypatch.setenv("LANGSMITH_API_KEY", "key")
    monkeypatch.setenv("ENABLE_LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGSMITH_PROJECT", "existing")

    tracing.configure_tracing(project_name="new")

    assert tracing.os.environ["LANGSMITH_TRACING"] == "false"
    assert tracing.os.environ["LANGSMITH_PROJECT"] == "existing"


def test_traceable_returns_passthrough_when_providers_disabled(monkeypatch: Any) -> None:
    monkeypatch.setenv("ENABLE_LANGSMITH_TRACING", "false")
    monkeypatch.setenv("ENABLE_LANGFUSE_TRACING", "false")
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

    decorator = tracing.traceable(name="x")

    def sample() -> str:
        return "ok"

    wrapped = decorator(sample)
    assert wrapped is sample
    assert wrapped() == "ok"


def test_traceable_delegates_to_both_when_available(monkeypatch: Any) -> None:
    events: list[str] = []

    def fake_langsmith_traceable(*args: Any, **kwargs: Any):
        assert kwargs == {"name": "abc", "run_type": "tool"}

        def _decorator(func: Any) -> Any:
            def _wrapped(*f_args: Any, **f_kwargs: Any) -> Any:
                events.append("langsmith")
                return func(*f_args, **f_kwargs)

            return _wrapped

        return _decorator

    def fake_langfuse_observe(*args: Any, **kwargs: Any):
        assert kwargs == {"name": "abc", "as_type": "tool"}

        def _decorator(func: Any) -> Any:
            def _wrapped(*f_args: Any, **f_kwargs: Any) -> Any:
                events.append("langfuse")
                return func(*f_args, **f_kwargs)

            return _wrapped

        return _decorator

    monkeypatch.setattr(tracing, "_langsmith_traceable", fake_langsmith_traceable)
    monkeypatch.setattr(tracing, "_langfuse_observe", fake_langfuse_observe)
    monkeypatch.setenv("ENABLE_LANGSMITH_TRACING", "true")
    monkeypatch.setenv("ENABLE_LANGFUSE_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "ls-key")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "lf-pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "lf-sk")

    decorator = tracing.traceable(name="abc", run_type="tool")

    def sample() -> int:
        return 1

    wrapped = decorator(sample)

    assert wrapped() == 1
    assert events == ["langfuse", "langsmith"]
