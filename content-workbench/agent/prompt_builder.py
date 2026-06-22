from __future__ import annotations

from pathlib import Path


def load_workflow_prompt_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def build_workflow_system_prompt_text(config: dict, workflow_prompt: str, profile: dict | None = None) -> str:
    profile = profile or {}
    creator = config.get("creator", {})
    identity = (
        "你是「Mosmori」内容创作助理，不是闲聊测试机器人。"
        "你的工作是陪创作者把碎片想法推进成可发布内容，同时避免过度生产。"
    )
    context = (
        f"\n\n当前创作者配置：内容形态={creator.get('content_type') or profile.get('content_type') or '未配置'}；"
        f"平台={profile.get('platform') or creator.get('platform') or '未配置'}；"
        f"赛道/人设={profile.get('track') or creator.get('niche') or '未配置'}；"
        f"细分赛道={profile.get('niche') or creator.get('niche') or '未配置'}。"
    )
    if workflow_prompt:
        return f"{identity}\n\n{workflow_prompt}{context}"
    return (
        f"{identity}"
        "完整工作流是：火花/灵感 -> 标题选项 -> 用户选择标题 -> 盲打分 -> 收录 -> 深挖成稿 -> 盲打分 -> 预测 -> 审稿 -> 发布 -> 复盘。"
        "不要一条路走到黑；先做需求分类；只执行当前一步。"
        f"{context}"
    )
