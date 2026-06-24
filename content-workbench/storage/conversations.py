from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Callable


def conversation_path(conversations_dir: Path, conversation_id: str) -> Path:
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "", conversation_id or "")
    if not safe_id:
        raise ValueError("conversation_id is required")
    return conversations_dir / f"{safe_id}.json"


def conversation_title_from_message(message: str) -> str:
    title = re.sub(r"\s+", " ", (message or "").strip())[:24]
    return title or "新对话"


def create_conversation_file(conversations_dir: Path, atomic_write_text: Callable[[Path, str], None], now_iso: Callable[[], str], title: str = "新对话") -> dict:
    conversations_dir.mkdir(parents=True, exist_ok=True)
    conversation = {
        "id": str(uuid.uuid4()),
        "title": title.strip() or "新对话",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "messages": [],
    }
    atomic_write_text(conversation_path(conversations_dir, conversation["id"]), json.dumps(conversation, ensure_ascii=False, indent=2))
    return conversation


def load_conversation_file(conversations_dir: Path, conversation_id: str) -> dict:
    try:
        path = conversation_path(conversations_dir, conversation_id)
    except ValueError:
        return {}
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    data.setdefault("id", conversation_id)
    data.setdefault("title", "新对话")
    data.setdefault("messages", [])
    return data


def list_conversation_files(conversations_dir: Path, load_conversation: Callable[[str], dict]) -> list[dict]:
    conversations_dir.mkdir(parents=True, exist_ok=True)
    items = []
    for path in conversations_dir.glob("*.json"):
        conversation = load_conversation(path.stem)
        if not conversation:
            continue
        items.append({
            "id": conversation.get("id"),
            "title": conversation.get("title") or "新对话",
            "created_at": conversation.get("created_at", ""),
            "updated_at": conversation.get("updated_at", ""),
            "message_count": len(conversation.get("messages", [])),
        })
    return sorted(items, key=lambda item: item.get("updated_at", ""), reverse=True)


def delete_conversation_file(conversations_dir: Path, conversation_id: str) -> bool:
    try:
        path = conversation_path(conversations_dir, conversation_id)
    except ValueError:
        return False
    if path.exists():
        path.unlink()
        return True
    return False


def rename_conversation_file(
    conversations_dir: Path,
    atomic_write_text: Callable[[Path, str], None],
    now_iso: Callable[[], str],
    conversation_id: str,
    title: str,
) -> dict:
    conversation = load_conversation_file(conversations_dir, conversation_id)
    if not conversation:
        return {}
    clean_title = re.sub(r"\s+", " ", (title or "").strip())[:60]
    conversation["title"] = clean_title or "新对话"
    conversation["updated_at"] = now_iso()
    atomic_write_text(conversation_path(conversations_dir, conversation["id"]), json.dumps(conversation, ensure_ascii=False, indent=2))
    return conversation


def append_conversation_turn_file(
    conversations_dir: Path,
    atomic_write_text: Callable[[Path, str], None],
    now_iso: Callable[[], str],
    load_conversation: Callable[[str], dict],
    create_conversation: Callable[[str], dict],
    conversation_id: str,
    message: str,
    reply: dict,
) -> dict:
    conversation = load_conversation(conversation_id) or create_conversation(conversation_title_from_message(message))
    if conversation.get("id") != conversation_id:
        conversation_id = conversation["id"]
    messages = conversation.setdefault("messages", [])
    now = now_iso()
    messages.append({"role": "user", "content": message, "created_at": now})
    messages.append({"role": "assistant", "content": reply.get("summary", ""), "reply": reply, "created_at": now_iso()})
    if not conversation.get("title") or conversation.get("title") == "新对话":
        conversation["title"] = conversation_title_from_message(message)
    conversation["updated_at"] = now_iso()
    atomic_write_text(conversation_path(conversations_dir, conversation["id"]), json.dumps(conversation, ensure_ascii=False, indent=2))
    return conversation


def conversation_history_for_llm(conversation: dict, limit: int = 16) -> list[dict]:
    history = []
    for item in conversation.get("messages", [])[-limit:]:
        role = "assistant" if item.get("role") == "assistant" else "user"
        content = item.get("content") or item.get("reply", {}).get("summary") or ""
        if content:
            history.append({"role": role, "content": content})
    return history
