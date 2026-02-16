from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any, TypeVar, cast


F = TypeVar("F", bound=Callable[..., Any])


try:
    from langsmith import traceable as _traceable
except Exception:
    _traceable = None


def traceable(*args: Any, **kwargs: Any) -> Callable[[F], F]:
    """Return LangSmith traceable decorator when available, else no-op."""

    if _traceable is None:
        def _decorator(func: F) -> F:
            return func

        return _decorator
    return cast(Callable[[F], F], _traceable(*args, **kwargs))


def configure_langsmith(project_name: str = "uk-resell-adk") -> None:
    """Enable tracing defaults when a LangSmith API key is configured."""

    if not os.getenv("LANGSMITH_API_KEY"):
        return
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGSMITH_PROJECT", project_name)
