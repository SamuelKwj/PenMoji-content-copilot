from __future__ import annotations


def review_next_step(topic: str) -> dict:
    return {"label": "继续打分", "prompt": f"打分：{topic}"}
