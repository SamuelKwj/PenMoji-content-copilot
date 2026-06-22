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


def build_skill_messages(skill_route: dict, input_text: str) -> list[dict]:
    prompt = str(skill_route.get("prompt") or "").strip()
    system_prompt = (
        f"{prompt}\n\n"
        "你是内容工作台的 skill executor。只处理本次输入，不读取可见聊天历史、账号密钥、发布后数据或用户评价。"
    ).strip()
    user_prompt = (
        "下面是本次 skill 唯一允许看到的输入。\n\n"
        f"内容：{input_text}\n\n"
        "请按 skill 要求输出可直接写入文件的中文结果。"
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def run_skill_executor(
    *,
    skill_route: dict,
    input_text: str,
    project_path: Path | None = None,
    config: dict | None = None,
    llm_callback: LlmCallback | None = None,
) -> dict:
    run_id = str(uuid.uuid4())
    messages = build_skill_messages(skill_route, input_text)
    input_payload = {"text": input_text}
    output = ""
    note = "LLM callback not configured."
    attempted = False
    if llm_callback:
        attempted = True
        output, note = llm_callback(messages, config or {}, 0.4, 60)
    payload = {
        "id": run_id,
        "created_at": now_iso(),
        "agent_mode": skill_route.get("agent_mode", "inline"),
        "skill": skill_route.get("skill", ""),
        "prompt_file": skill_route.get("prompt_file", ""),
        "prompt_excerpt": str(skill_route.get("prompt") or "")[:500],
        "input_policy": skill_route.get("input_policy", "text-only"),
        "conversation_history_used": False,
        "input_hash": hashlib.sha256(json.dumps(input_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest(),
        "input": input_payload,
        "llm_call": {
            "attempted": attempted,
            "message_count": len(messages),
            "note": note,
            "raw_output_hash": hashlib.sha256(output.encode("utf-8")).hexdigest() if output else "",
            "raw_output_excerpt": output[:1200] if output else "",
        },
    }
    if project_path:
        run_dir = project_path / "skill-runs"
        run_dir.mkdir(parents=True, exist_ok=True)
        run_path = run_dir / f"{run_id}.json"
        payload["run_path"] = str(run_path)
        run_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {**payload, "output": output}
