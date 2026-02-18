from __future__ import annotations

"""Optional tracing integration helpers.

This module supports concurrent tracing to LangSmith and Langfuse.
All call sites use one decorator API (`traceable`) so provider wiring remains
centralized and easy to evolve.
"""

import atexit
import functools
import os
import sys
from collections.abc import Callable
from typing import Any, TypeVar, cast


F = TypeVar("F", bound=Callable[..., Any])


try:
    from langsmith import traceable as _langsmith_traceable
except Exception:
    _langsmith_traceable = None

try:
    # Langfuse exposes a decorator API for observation spans.
    from langfuse import observe as _langfuse_observe
except Exception:
    _langfuse_observe = None

try:
    # Optional client access for flush() on process exit.
    from langfuse import get_client as _langfuse_get_client
except Exception:
    _langfuse_get_client = None

try:
    # Preferred way to assign user/session for nested observations.
    from langfuse import propagate_attributes as _langfuse_propagate_attributes
except Exception:
    _langfuse_propagate_attributes = None

try:
    # Context API supports setting session/user attributes on the current trace.
    from langfuse.decorators import langfuse_context as _langfuse_context
except Exception:
    _langfuse_context = None


_AEXIT_REGISTERED = False


def _env_truthy(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _compose_decorators(decorators: list[Callable[[F], F]]) -> Callable[[F], F]:
    if not decorators:

        def _identity(func: F) -> F:
            return func

        return _identity

    def _decorator(func: F) -> F:
        wrapped = func
        # Apply in reverse so the first provider in list is outermost.
        for dec in reversed(decorators):
            wrapped = dec(wrapped)
        return wrapped

    return _decorator


def _langfuse_as_type(run_type: Any) -> str | None:
    value = str(run_type).strip().lower() if run_type is not None else ""
    if value in {"tool", "chain", "agent"}:
        return value
    return None


def _langfuse_trace_identity_decorator() -> Callable[[F], F]:
    def _decorator(func: F) -> F:
        if _langfuse_context is None and _langfuse_propagate_attributes is None:
            return func

        @functools.wraps(func)
        def _wrapped(*f_args: Any, **f_kwargs: Any) -> Any:
            user_id = os.getenv("LANGFUSE_USER_ID")
            session_id = os.getenv("LANGFUSE_SESSION_ID")
            if not (user_id or session_id):
                return func(*f_args, **f_kwargs)

            if _langfuse_propagate_attributes is not None:
                try:
                    propagated_attributes = _langfuse_propagate_attributes(user_id=user_id, session_id=session_id)
                except Exception:
                    propagated_attributes = None
                if propagated_attributes is not None:
                    with propagated_attributes:
                        return func(*f_args, **f_kwargs)

            if _langfuse_context is not None:
                try:
                    _langfuse_context.update_current_trace(user_id=user_id, session_id=session_id)
                except Exception:
                    pass
            return func(*f_args, **f_kwargs)

        return cast(F, _wrapped)

    return _decorator


def traceable(*args: Any, **kwargs: Any) -> Callable[[F], F]:
    """Return a decorator that fans out traces to enabled providers."""
    decorators: list[Callable[[F], F]] = []

    langfuse_enabled = _env_truthy("ENABLE_LANGFUSE_TRACING", True) and bool(os.getenv("LANGFUSE_PUBLIC_KEY")) and bool(
        os.getenv("LANGFUSE_SECRET_KEY")
    )
    if langfuse_enabled and _langfuse_observe is not None:
        lf_kwargs = dict(kwargs)
        as_type = _langfuse_as_type(kwargs.get("run_type"))
        lf_kwargs.pop("run_type", None)
        if as_type is not None:
            lf_kwargs["as_type"] = as_type
        decorators.append(cast(Callable[[F], F], _langfuse_observe(*args, **lf_kwargs)))
        decorators.append(_langfuse_trace_identity_decorator())

    langsmith_enabled = _env_truthy("ENABLE_LANGSMITH_TRACING", True) and bool(os.getenv("LANGSMITH_API_KEY"))
    if langsmith_enabled and _langsmith_traceable is not None:
        decorators.append(cast(Callable[[F], F], _langsmith_traceable(*args, **kwargs)))

    return _compose_decorators(decorators)


def _flush_tracing_clients() -> None:
    # Best-effort flush to reduce dropped spans on short-lived CLI processes.
    if _langfuse_get_client is not None:
        try:
            _langfuse_get_client().flush()
        except Exception:
            pass


def configure_langsmith(project_name: str = "uk-resell-adk") -> None:
    """Backward-compatible alias for legacy call sites.

    This now configures both LangSmith and Langfuse tracing defaults.
    """
    configure_tracing(project_name=project_name)


def configure_tracing(project_name: str = "uk-resell-adk") -> None:
    """Enable tracing defaults for LangSmith and Langfuse concurrently."""
    global _AEXIT_REGISTERED

    langsmith_enabled = _env_truthy("ENABLE_LANGSMITH_TRACING", True) and bool(os.getenv("LANGSMITH_API_KEY"))
    if langsmith_enabled:
        os.environ.setdefault("LANGSMITH_TRACING", "true")
        os.environ.setdefault("LANGSMITH_PROJECT", project_name)
        if _langsmith_traceable is None:
            print(
                "Warning: LangSmith tracing enabled but langsmith SDK is not installed; LangSmith tracing is disabled.",
                file=sys.stderr,
            )

    langfuse_enabled = _env_truthy("ENABLE_LANGFUSE_TRACING", True) and bool(os.getenv("LANGFUSE_PUBLIC_KEY")) and bool(
        os.getenv("LANGFUSE_SECRET_KEY")
    )
    if langfuse_enabled:
        os.environ.setdefault("LANGFUSE_TRACING_ENABLED", "true")
        os.environ.setdefault("LANGFUSE_HOST", os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com"))
        if _langfuse_observe is None:
            print(
                "Warning: Langfuse tracing enabled but langfuse SDK is not installed; Langfuse tracing is disabled.",
                file=sys.stderr,
            )

    if not _AEXIT_REGISTERED:
        atexit.register(_flush_tracing_clients)
        _AEXIT_REGISTERED = True
