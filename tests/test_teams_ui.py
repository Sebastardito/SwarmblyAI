"""Teams UI strings (3.5, D-019): English and Spanish are both complete."""

from __future__ import annotations

import json


def test_ui_strings_exist_in_english_and_spanish():
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent / "swarmbly_app" / "web" / "i18n"
    keys = ("nav.teams", "teams.title", "teams.create", "teams.edit",
            "teams.delete", "teams.duplicate", "teams.use", "teams.role.search",
            "teams.placeholderRequired", "chat.team", "chat.teamNone",
            "chat.partial")
    for lang in ("en", "es"):
        data = json.loads((root / f"{lang}.json").read_text(encoding="utf-8"))
        for key in keys:
            node = data
            for part in key.split("."):
                assert isinstance(node, dict) and part in node, (lang, key)
                node = node[part]
            assert str(node).strip(), (lang, key)
