from __future__ import annotations

import re


def classify_user_intent(text: str) -> str:
    """Return the coarse content-workbench intent for a user message."""
    cleaned = (text or "").strip()
    if not cleaned:
        return "empty"
    if re.search(r"我是做|平台|赛道|人设|内容形态|目标受众", cleaned):
        return "profile_update"
    if re.search(r"我有.*灵感|收录.*灵感|火花", cleaned):
        return "spark_collect"
    if re.search(r"值不值得|行不行|怎么看|判断.*选题", cleaned):
        return "topic_validation"
    if re.search(r"打分|评分", cleaned):
        return "score"
    if re.search(r"预测|预判", cleaned):
        return "predict"
    if re.search(r"审稿|限流|违规", cleaned):
        return "review"
    if re.search(r"拍了|拍摄", cleaned):
        return "shoot"
    if re.search(r"发布|已发", cleaned):
        return "publish"
    if re.search(r"复盘|数据", cleaned):
        return "retro"
    return "chat"
