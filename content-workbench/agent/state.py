from __future__ import annotations

import json
from pathlib import Path
from typing import Callable


def default_session_state() -> dict:
    return {
        "profile": {"platform": "", "track": "", "niche": "", "persona": "", "content_type": ""},
        "pending_spark": {},
        "collecting_spark": False,
        "updated_at": "",
    }


def load_session_state_file(path: Path) -> dict:
    data = default_session_state()
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except (json.JSONDecodeError, OSError):
            data = default_session_state()
    state = default_session_state()
    if isinstance(data.get("profile"), dict):
        state["profile"].update({k: str(v) for k, v in data["profile"].items() if k in state["profile"]})
    if isinstance(data.get("pending_spark"), dict):
        state["pending_spark"] = data["pending_spark"]
    state["collecting_spark"] = bool(data.get("collecting_spark"))
    state["updated_at"] = str(data.get("updated_at") or "")
    return state


def save_session_state_file(path: Path, state: dict, now_iso: Callable[[], str]) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = now_iso()
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    return state
