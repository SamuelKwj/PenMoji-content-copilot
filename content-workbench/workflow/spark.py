from __future__ import annotations

import re


def strip_collect_prefix(content: str) -> str:
    return re.sub(r"^(固化|收录|整理|保存)(这个)?(灵感|火花|想法)?[:：\s]*", "", content.strip())


def is_empty_collect_request(text: str) -> bool:
    cleaned = text.strip()
    return bool(re.fullmatch(r"(固化|收录|整理|保存)(这个)?(灵感|火花|想法)?[:：\s]*", cleaned))


def is_confirm_collect(text: str) -> bool:
    return bool(re.search(r"^(确认收录|就这个|收录吧|可以收录|确定收录|确认)", text.strip()))


def looks_like_spark_candidate_text(text: str, route_stage: str, collecting_spark: bool = False) -> bool:
    cleaned = text.strip()
    if len(cleaned) < 10:
        return False
    if re.search(r"^(你是谁|你好|hello|hi|谢谢|测试)", cleaned, re.I):
        return False
    if route_stage != "chat":
        return False
    if collecting_spark:
        return True
    signals = r"我发现|我觉得|为什么|越来越|普通人|焦虑|困境|问题|现象|矛盾|代价|真相|内容|创作|生产|廉价|出头|注意力|同质化|门槛|速度"
    return bool(re.search(signals, cleaned))


def clean_spark_core(content: str) -> str:
    core = strip_collect_prefix(content)
    core = re.sub(r"^(就是|感觉|我发现|我觉得|我认为|其实|现在|如今)[，,\s]*", "", core)
    core = re.sub(r"[。！？?]+$", "", core).strip()
    return core or strip_collect_prefix(content).strip()


def title_options_for_spark(content: str) -> list[str]:
    core = clean_spark_core(content)

    if "学AI" in core and "焦虑" in core:
        return [
            "普通人学AI越焦虑，不是学得少，是判断入口错了",
            "AI学习真正的陷阱，是把工具焦虑误当成能力焦虑",
            "越努力学AI，越容易被“必须全会”的幻觉拖垮",
        ]

    if "内容" in core and any(token in core for token in ["廉价", "生产", "速度", "同质化"]):
        return [
            "内容生产越快，真正稀缺的越不是产能，是判断",
            "AI让内容变廉价，但也让人的观点更值钱",
            "所有人都会生成内容以后，不会表达的人反而更危险",
        ]

    if "个人IP" in core or "个人ip" in core:
        return [
            "普通人做个人IP最容易输在一开始就没观点",
            "个人IP不是每天发内容，是持续证明你怎么看世界",
            "做个人IP卡住，往往不是工具不够，是判断不够硬",
        ]

    subject = core[:30]
    return [
        f"{subject}背后真正的矛盾，是效率变高以后判断更稀缺",
        f"别急着解决{subject}，先看清它正在放大什么问题",
        f"{subject}不是一个工具问题，而是一个判断力问题",
    ]
