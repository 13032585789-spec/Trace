"""Cache, inventory, collab and contract tests. No API keys, no dataset needed."""
from pathlib import Path

import pytest

FIX = Path(__file__).parent / "fixtures"
CONTRACT = {"value", "unit", "items", "sources", "method", "warnings"}


@pytest.fixture(autouse=True)
def _env(monkeypatch, tmp_path):
    from agent import config

    monkeypatch.setattr(config, "DATA_DIR", FIX.resolve())
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "test")


def test_vision_cache_second_call_skips_api(monkeypatch):
    from agent import vision

    calls = {"g": 0, "n": 0}

    def g(png, t):
        calls["g"] += 1
        return [{"box_2d": [100, 100, 200, 200]}]

    def n(png, t):
        calls["n"] += 1
        return 1

    monkeypatch.setattr(vision, "_gemini_detect", g)
    monkeypatch.setattr(vision, "_nemotron_count", n)
    monkeypatch.setattr(vision.config, "NEMOTRON_MODEL", "nemotron-test")
    a = vision.count_in_drawing("data/demo/plan.png", "toilet")
    b = vision.count_in_drawing("data/demo/plan.png", "toilet")
    assert calls == {"g": 1, "n": 1}
    assert a["cached"] is False and b["cached"] is True
    assert a["value"] == b["value"] == 1 and b["verified_by"]["agreement"] is True


def test_cache_key_depends_on_prompt(monkeypatch):
    from agent import vision

    calls = []
    monkeypatch.setattr(vision, "_gemini_detect", lambda png, t: calls.append(t) or [])
    monkeypatch.setattr(vision, "_nemotron_count", lambda png, t: None)
    vision.count_in_drawing("data/demo/plan.png", "toilet")
    vision.count_in_drawing("data/demo/plan.png", "door")
    assert calls == ["toilet", "door"]


def test_none_results_are_not_cached(monkeypatch):
    from agent import vision

    calls = []
    monkeypatch.setattr(vision, "_gemini_detect", lambda png, t: [])
    monkeypatch.setattr(vision, "_nemotron_count", lambda png, t: calls.append(1))
    vision.count_in_drawing("data/demo/plan.png", "toilet")
    vision.count_in_drawing("data/demo/plan.png", "toilet")
    assert len(calls) == 2


def test_inventory_numbers_per_category(monkeypatch):
    from agent import vision

    dets = [{"category": "toilet", "box_2d": [0, 0, 10, 10]}, {"category": "door", "box_2d": [0, 0, 10, 10]},
            {"category": "toilet", "box_2d": [20, 20, 30, 30]}, {"category": "unicorn", "box_2d": [0, 0, 1, 1]}]
    monkeypatch.setattr(vision, "_gemini_inventory", lambda png, p: dets)
    r = vision.scan_drawing_inventory("data/demo/plan.png")
    assert CONTRACT <= r.keys()
    assert [i["name"] for i in r["items"]] == ["WC 1", "Door 1", "WC 2"]
    assert r["by_category"] == {"toilet": 2, "door": 1} and r["value"] == 3
    assert len(r["sources"]) == 3 and all(len(s["bbox"]) == 4 for s in r["sources"])


def test_inventory_without_key_is_marked_mock(monkeypatch):
    from agent import vision

    monkeypatch.setattr(vision.config, "GEMINI_API_KEY", "")
    r = vision.scan_drawing_inventory("data/demo/plan.png")
    assert CONTRACT <= r.keys() and any("MOCK DATA" in w for w in r["warnings"])


@pytest.mark.parametrize("tool", ["list_spaces", "count_elements", "elements_in_space", "space_area",
                                  "locate_elements", "element_status", "search_drawings"])
def test_every_engine_tool_returns_contract_with_mock_flag(tool):
    from agent import tools

    r = tools.call(tool, {"path": "x.ifc"})
    assert CONTRACT <= r.keys() and any("MOCK DATA" in w for w in r["warnings"])


def test_unsupported_numbers_detects_invented_values():
    from agent import agent

    ev = [{"value": 2, "items": [{}, {}]}]
    assert agent.unsupported_numbers("There are 2 toilets.", "How many?", ev) == []
    assert agent.unsupported_numbers("There are 5 toilets.", "How many?", ev) == [5.0]


def test_path_traversal_rejected_on_inventory():
    from fastapi.testclient import TestClient

    from agent.app import app

    assert TestClient(app).get("/inventory", params={"path": "../../etc/passwd"}).status_code == 404


def test_collab_status_and_messages():
    from fastapi.testclient import TestClient

    from agent.app import app

    c = TestClient(app)
    assert c.post("/collab/status", json={"space_id": "B204", "status": "missing_wall"}).status_code == 200
    assert c.post("/collab/status", json={"space_id": "B204", "status": "bogus"}).status_code == 400
    c.post("/collab/message", json={"space_id": "B204", "text": "Wall broken, fix before WC", "role": "architect",
                                    "notify": ["plumber"]})
    c.post("/collab/message", json={"space_id": "B999", "text": "other room"})
    r = c.get("/collab", params={"space_id": "B204"}).json()
    assert r["status"]["B204"]["status"] == "missing_wall"
    assert [m["text"] for m in r["messages"]][-1] == "Wall broken, fix before WC"
    assert all(m["space_id"] == "B204" for m in r["messages"])


def test_role_hints_cover_all_trades():
    from agent import agent

    assert {"architect", "electrician", "plumber", "owner"} <= agent.ROLE_HINTS.keys()
