from __future__ import annotations

from pathlib import Path
from typing import Any

from uk_resell_adk.application import run_service


class _FakeStore:
    def __init__(self, running: bool = False) -> None:
        self._running = running
        self.set_running_calls: list[bool] = []

    def is_running(self) -> bool:
        return self._running

    def set_running(self, running: bool) -> None:
        self._running = running
        self.set_running_calls.append(running)


def test_default_html_output_path_uses_reports_prefix() -> None:
    path = run_service.default_html_output_path()
    assert path.parent == Path("reports")
    assert path.name.startswith("uk_resell_report_")
    assert path.suffix == ".html"


def test_seed_available_agents_registers_expected_agents(monkeypatch: Any) -> None:
    registered: list[str] = []

    def _register_agent(**kwargs: Any) -> None:
        registered.append(str(kwargs["agent_id"]))

    monkeypatch.setattr(run_service, "register_agent", _register_agent)
    run_service.seed_available_agents()

    assert registered == ["orchestrator", "sourcing", "profitability", "report"]


def test_run_visualized_workflow_returns_early_when_store_already_running(monkeypatch: Any) -> None:
    fake_store = _FakeStore(running=True)
    called = {"start": False}

    monkeypatch.setattr(run_service, "get_live_event_store", lambda: fake_store)
    monkeypatch.setattr(run_service, "start_visual_run", lambda **_: called.__setitem__("start", True))

    run_service.run_visualized_workflow(
        run_workflow=lambda: {},
        write_report=lambda _result, _path: Path("reports/unused.html"),
    )

    assert called["start"] is False


def test_run_visualized_workflow_success_emits_completion(monkeypatch: Any) -> None:
    fake_store = _FakeStore(running=False)
    calls: dict[str, Any] = {
        "start_args": None,
        "complete_args": None,
        "fail_args": None,
        "emitted_events": [],
    }

    monkeypatch.setattr(run_service, "get_live_event_store", lambda: fake_store)
    monkeypatch.setattr(run_service, "start_visual_run", lambda **kwargs: calls.__setitem__("start_args", kwargs))
    monkeypatch.setattr(run_service, "seed_available_agents", lambda: None)
    monkeypatch.setattr(run_service, "update_agent_status", lambda **_: None)
    monkeypatch.setattr(run_service, "emit_visual_event", lambda **kwargs: calls["emitted_events"].append(kwargs))
    monkeypatch.setattr(run_service, "fail_visual_run", lambda **kwargs: calls.__setitem__("fail_args", kwargs))
    monkeypatch.setattr(
        run_service, "complete_visual_run", lambda **kwargs: calls.__setitem__("complete_args", kwargs)
    )
    monkeypatch.setattr(run_service, "default_html_output_path", lambda: Path("reports/test_report.html"))

    result_payload = {
        "marketplaces": [{"name": "A"}],
        "candidate_items": [{"title": "Item"}],
        "assessments": [{"item_title": "Item"}],
    }

    run_service.run_visualized_workflow(
        run_workflow=lambda: result_payload,
        write_report=lambda _result, _path: Path("reports/generated.html"),
    )

    assert calls["start_args"] == {
        "title": run_service.SERVER_TITLE,
        "objective": run_service.SERVER_OBJECTIVE,
    }
    assert calls["fail_args"] is None
    assert calls["complete_args"] is not None
    assert calls["complete_args"]["metadata"]["marketplaces"] == 1
    assert calls["complete_args"]["metadata"]["candidate_items"] == 1
    assert calls["complete_args"]["metadata"]["assessments"] == 1
    assert fake_store.set_running_calls and fake_store.set_running_calls[0] is True
    assert any(event["agent_id"] == "report" for event in calls["emitted_events"])


def test_run_visualized_workflow_failure_emits_fail(monkeypatch: Any) -> None:
    fake_store = _FakeStore(running=False)
    captured: dict[str, Any] = {"fail_args": None}

    monkeypatch.setattr(run_service, "get_live_event_store", lambda: fake_store)
    monkeypatch.setattr(run_service, "start_visual_run", lambda **_: None)
    monkeypatch.setattr(run_service, "seed_available_agents", lambda: None)
    monkeypatch.setattr(run_service, "update_agent_status", lambda **_: None)
    monkeypatch.setattr(run_service, "emit_visual_event", lambda **_: None)
    monkeypatch.setattr(run_service, "complete_visual_run", lambda **_: None)
    monkeypatch.setattr(
        run_service, "fail_visual_run", lambda **kwargs: captured.__setitem__("fail_args", kwargs)
    )

    def _explode() -> dict[str, Any]:
        raise RuntimeError("boom")

    run_service.run_visualized_workflow(
        run_workflow=_explode,
        write_report=lambda _result, _path: Path("reports/ignored.html"),
    )

    assert captured["fail_args"] is not None
    assert "boom" in captured["fail_args"]["summary"]
