from __future__ import annotations


def publish_next_step(topic: str) -> dict:
    return {"label": "T+3 复盘", "prompt": f"复盘：{topic}"}
