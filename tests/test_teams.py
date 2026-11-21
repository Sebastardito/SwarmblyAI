"""Teams (3.5, D-019): stored plan templates.

Validation is the security boundary of this module: a malformed template must
be refused on save and on load, and a built-in can never be edited or deleted.
"""

from __future__ import annotations

import json

import pytest

from swarmbly_app.teams import (MAX_INSTRUCTION, MAX_STEPS, TEAMS_SCHEMA,
                                TeamError, TeamStore, builtin_teams,
                                normalise_team)


def _team(**over):
    raw = {
        "name": "Example",
        "description": "Two steps",
        "steps": [
            {"id": "s1", "name": "Write", "role": "large_model",
             "instruction": "Write about {request}"},
            {"id": "s2", "name": "Review", "role": "reasoner",
             "depends_on": ["s1"], "instruction": "Review the draft."},
        ],
    }
    raw.update(over)
    return raw


def _store(tmp_path):
    return TeamStore(tmp_path / "data")


# -- validation ----------------------------------------------------------------------

def test_builtins_are_valid_and_read_only(tmp_path):
    teams = builtin_teams()
    assert len(teams) >= 2
    assert {team["id"] for team in teams} >= {
        "example-research-brief", "example-source-review"}
    for team in teams:
        assert team["builtin"] is True
        assert normalise_team(team, team_id=team["id"])["steps"]
        assert any("{request}" in step["instruction"] for step in team["steps"])
    store = _store(tmp_path)
    for team in teams:
        with pytest.raises(TeamError, match="read-only"):
            store.update(team["id"], _team())
        with pytest.raises(TeamError, match="read-only"):
            store.delete(team["id"])


def test_unknown_role_is_rejected():
    raw = _team()
    raw["steps"][0]["role"] = "admin"
    with pytest.raises(TeamError, match="role"):
        normalise_team(raw)


def test_forward_dependency_is_rejected():
    raw = _team()
    raw["steps"][0]["depends_on"] = ["s2"]   # s2 is later
    with pytest.raises(TeamError, match="not an earlier step"):
        normalise_team(raw)


def test_cycle_is_rejected():
    raw = _team()
    raw["steps"][0]["depends_on"] = ["s2"]
    raw["steps"][1]["depends_on"] = ["s1"]
    with pytest.raises(TeamError, match="not an earlier step"):
        normalise_team(raw)


def test_self_dependency_is_rejected():
    raw = _team()
    raw["steps"][0]["depends_on"] = ["s1"]
    with pytest.raises(TeamError, match="itself"):
        normalise_team(raw)


def test_step_bounds_and_names():
    raw = _team()
    raw["steps"] = [{"id": f"s{i}", "name": f"Step {i}",
                     "instruction": "{request}"} for i in range(MAX_STEPS + 1)]
    with pytest.raises(TeamError, match="at most"):
        normalise_team(raw)
    with pytest.raises(TeamError, match="team name"):
        normalise_team(_team(name=""))
    with pytest.raises(TeamError, match="step 1 name"):
        normalise_team(_team(steps=[
            {"id": "s1", "name": "x" * 50, "instruction": "{request}"}]))
    with pytest.raises(TeamError, match="instruction"):
        normalise_team(_team(steps=[
            {"id": "s1", "name": "Write",
             "instruction": "{request}" + "x" * MAX_INSTRUCTION}]))
    with pytest.raises(TeamError, match="at least one step"):
        normalise_team(_team(steps=[]))
    with pytest.raises(TeamError, match="placeholder"):
        normalise_team(_team(steps=[
            {"id": "s1", "name": "Write", "instruction": "No placeholder"}]))
    with pytest.raises(TeamError, match="repeated"):
        normalise_team(_team(steps=[
            {"id": "s1", "name": "One", "instruction": "{request}"},
            {"id": "s1", "name": "Two", "instruction": "two"}]))


# -- storage -------------------------------------------------------------------------

def test_create_list_update_delete_and_reload(tmp_path):
    store = _store(tmp_path)
    created = store.create(_team())
    assert created["builtin"] is False and created["project_id"] == ""
    assert created["id"].startswith("team-")
    listed = store.list_teams()
    assert any(team["id"] == created["id"] for team in listed)
    assert store.get(created["id"])["name"] == "Example"
    edited = store.update(created["id"], _team(name="Edited"))
    assert edited["name"] == "Edited"
    assert store.get(created["id"])["name"] == "Edited"
    # a fresh instance reads the same validated file
    assert TeamStore(tmp_path / "data").get(created["id"])["name"] == "Edited"
    store.delete(created["id"])
    assert store.find(created["id"]) is None


def test_duplicate_builtin_copies_steps(tmp_path):
    store = _store(tmp_path)
    source = store.get("example-research-brief", "")
    copy = store.duplicate("example-research-brief", name="Mi equipo")
    assert copy["id"] != source["id"] and copy["name"] == "Mi equipo"
    assert copy["steps"] == source["steps"]
    assert store.get(copy["id"])["builtin"] is False


def test_project_teams_are_kept_apart(tmp_path):
    project_a = tmp_path / "project-a"
    project_b = tmp_path / "project-b"
    paths = {"pa": project_a, "pb": project_b}
    store = TeamStore(tmp_path / "data",
                      project_path=lambda pid: paths.get(pid))
    user = store.create(_team(name="User team"))
    own = store.create(_team(name="Project team"), project_id="pa")
    assert store.find(user["id"], "pa") is not None       # user teams travel
    assert store.find(own["id"], "pa") is not None
    assert store.find(own["id"], "pb") is None
    assert store.find(own["id"], "") is None


def test_a_corrupt_or_wrong_schema_file_is_refused_on_load(tmp_path):
    store = _store(tmp_path)
    store.user_file().parent.mkdir(parents=True, exist_ok=True)
    store.user_file().write_text("not json", encoding="utf-8")
    with pytest.raises(TeamError, match="cannot be read"):
        store.list_teams()
    store.user_file().write_text(json.dumps({"schema": "other", "teams": []}),
                                 encoding="utf-8")
    with pytest.raises(TeamError, match="not a swarmbly.teams"):
        store.list_teams()


def test_stored_files_are_private_and_valid(tmp_path):
    store = _store(tmp_path)
    store.create(_team())
    path = store.user_file()
    assert path.is_file()
    mode = path.stat().st_mode & 0o777
    assert mode == 0o600
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["schema"] == TEAMS_SCHEMA and len(raw["teams"]) == 1
