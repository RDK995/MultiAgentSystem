from __future__ import annotations

"""LangSmith tracing integration helpers.

The wrappers in this module keep LangSmith optional; the app runs cleanly even
when tracing is not installed or not configured.
"""

import os
import sys
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

    if _traceable is None:
        print(
            "Warning: LANGSMITH_API_KEY is set but langsmith is not installed in this Python environment; tracing is disabled.",
            file=sys.stderr,
        )
