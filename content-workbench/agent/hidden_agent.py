from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


LlmCallback = Callable[[list[dict], dict, float, int], tuple[str, str]]


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def hidden_score_user_prompt(topic: str, selected_title: str = "", rubric: list[dict] | None = None) -> str:
    rubric_lines = "\n".join(
        f"- {item.get('key', '')} {item.get('label', '')}: weight={item.get('weight', 1)}"
        for item in (rubric or [])
    )
    return (
        "下面是隐藏评分 agent 唯一允许看到的输入。\n\n"
        f"选题/稿件：{topic}\n\n"
        f"选用标题：{selected_title or '未指定'}\n\n"
        f"评分规则：\n{rubric_lines}\n\n"
        "请只基于以上内容完成评分，不要推断任何聊天历史、发布数据或用户反馈。"
    )


def build_hidden_agent_messages(skill_route: dict, topic: str, selected_title: str = "", rubric: list[dict] | None = None) -> list[dict]:
    skill_prompt = str(skill_route.get("prompt") or "").strip()
    system_prompt = (
        f"{skill_prompt}\n\n"
        "你是隐藏子 agent。本次运行是隔离上下文：没有可见聊天历史，没有发布后数据，没有用户评价。"
    ).strip()
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": hidden_score_user_prompt(topic, selected_title, rubric)},
    ]


def run_hidden_agent(
    *,
    skill_route: dict,
    topic: str,
    selected_title: str = "",
    rubric: list[dict] | None = None,
    project_path: Path | None = None,
    config: dict | None = None,
    llm_callback: LlmCallback | None = None,
) -> dict:
    """Run and persist a hidden-agent envelope.

    The visible conversation is not accepted as an argument. Stored input is
    limited to topic/title/rubric and LLM metadata never includes secrets.
    """
    run_id = str(uuid.uuid4())
    messages = build_hidden_agent_messages(skill_route, topic, selected_title, rubric)
    input_payload = {
        "topic": topic,
        "selected_title": selected_title,
        "rubric": rubric or [],
    }
    payload = {
        "id": run_id,
        "created_at": now_iso(),
        "agent_mode": "hidden",
        "skill": skill_route.get("skill", ""),
        "prompt_file": skill_route.get("prompt_file", ""),
        "prompt_excerpt": str(skill_route.get("prompt") or "")[:500],
        "input_policy": skill_route.get("input_policy", "topic-title-rubric-only"),
        "conversation_history_used": False,
        "input_hash": hashlib.sha256(json.dumps(input_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest(),
        "input": input_payload,
        "llm_call": {
            "attempted": False,
            "message_count": len(messages),
            "note": "LLM callback not configured.",
            "raw_output_hash": "",
            "raw_output_excerpt": "",
        },
    }
    if llm_callback:
        content, note = llm_callback(messages, config or {}, 0.1, 60)
        payload["llm_call"] = {
            "attempted": True,
            "message_count": len(messages),
            "note": note,
            "raw_output_hash": hashlib.sha256(content.encode("utf-8")).hexdigest() if content else "",
            "raw_output_excerpt": content[:1200] if content else "",
        }
    if project_path:
        run_dir = project_path / "hidden-agent-runs"
        run_dir.mkdir(parents=True, exist_ok=True)
        run_path = run_dir / f"{run_id}.json"
        run_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        payload["run_path"] = str(run_path)
        run_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
