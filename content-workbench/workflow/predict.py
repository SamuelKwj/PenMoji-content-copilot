from __future__ import annotations


def prediction_next_step(topic: str) -> dict:
    return {"label": "拍摄登记", "prompt": f"已拍：{topic}"}
