"""Teams API (3.5, D-019): list, create, edit, delete, duplicate, run."""

from __future__ import annotations

import json

from swarmbly_app.teams import MAX_STEPS

from test_teams import _team


# -- API and UI strings --------------------------------------------------------------

def test_api_crud_and_builtin_read_only(app_state):
    from fastapi.testclient import TestClient
    from swarmbly_app.api import create_app

    app = create_app(app_state)
    c = TestClient(app, base_url="http://127.0.0.1:8765")
    c.headers["X-Swarmbly-Token"] = app.state.guard.token
    listed = c.get("/api/teams")
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert any(team["builtin"] for team in body["teams"])
    assert body["limits"]["steps"] == MAX_STEPS
    created = c.post("/api/teams", json=_team())
    assert created.status_code == 200, created.text
    team_id = created.json()["id"]
    assert c.put(f"/api/teams/{team_id}", json=_team(name="Renamed")).status_code == 200
    assert c.get("/api/teams").json()["teams"][-1]["name"] == "Renamed"
    assert c.delete(f"/api/teams/{team_id}").status_code == 200
    # built-ins cannot be edited or deleted
    builtin = next(team["id"] for team in body["teams"] if team["builtin"])
    assert c.put(f"/api/teams/{builtin}", json=_team()).status_code == 403
    assert c.delete(f"/api/teams/{builtin}").status_code == 403
    bad = _team()
    bad["steps"][0]["depends_on"] = ["s2"]
    assert c.post("/api/teams", json=bad).status_code == 400


def test_api_send_uses_the_selected_team(app_state):
    from fastapi.testclient import TestClient
    from swarmbly_app.api import create_app

    seen = {}

    class Stub:
        def run(self, prompt, **kwargs):
            seen["team"] = kwargs.get("team")
            return {"routed": "distributed", "text": "stub answer",
                    "status": "complete",
                    "metadata": {"status": "complete", "steps": [],
                                 "team": {"id": (kwargs.get("team") or {}).get("id")}},
                    "stages": []}

    app_state.chat.orchestrator = lambda: Stub()  # type: ignore[assignment]
    app = create_app(app_state)
    c = TestClient(app, base_url="http://127.0.0.1:8765")
    c.headers["X-Swarmbly-Token"] = app.state.guard.token
    team = app_state.teams.create(_team())
    conv = app_state.chat.create_conversation(mode="lan")
    out = c.post(f"/api/conversations/{conv['id']}/messages", json={
        "text": "write this", "mode": "lan", "team_id": team["id"]})
    assert out.status_code == 202, out.text
    import time
    for _ in range(50):
        if seen.get("team"):
            break
        time.sleep(0.05)
    assert seen["team"]["id"] == team["id"]
    # an unknown team is refused before anything runs
    out = c.post(f"/api/conversations/{conv['id']}/messages", json={
        "text": "write this", "mode": "lan", "team_id": "team-nope"})
    assert out.status_code == 404
