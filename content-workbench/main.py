from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import re
import shutil
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlencode, urlparse


APP_VERSION = "0.1.0"
APP_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = APP_ROOT.parent
STATIC_ROOT = APP_ROOT / "static"
DATA_ROOT = Path(os.environ.get("CONTENT_WORKBENCH_HOME", Path.home() / ".content-workbench"))
CONFIG_PATH = DATA_ROOT / "config.json"
INBOX_PATH = DATA_ROOT / "inbox.jsonl"
CONVERSATIONS_DIR = DATA_ROOT / "conversations"
LEGACY_DEFAULT_PROJECT_PATH = WORKSPACE_ROOT / "Content Creator Pipeline"
DEFAULT_PROJECT_PATH = DATA_ROOT / "projects" / "default-content-project"
MASKED_KEY = "********"
DEMO_TOPIC = "普通人为什么做个人IP总是半途而废"
DELIVERABLE_LABELS = {
    "spark_card": "灵感固化卡",
    "review": "内容审核",
    "score": "内容评分",
    "prediction": "发布预测",
    "video_script": "视频脚本",
    "text_pack": "标题/发布文字",
    "static_page": "静态页文案",
}
SPARK_RUBRIC = [
    {"key": "HP", "label": "钩子强度", "weight": 1.5},
    {"key": "ER", "label": "情感共鸣", "weight": 1.5},
    {"key": "SR", "label": "社会议题", "weight": 1.5},
    {"key": "QL", "label": "金句密度", "weight": 1.0},
    {"key": "NA", "label": "叙事性", "weight": 1.0},
    {"key": "AB", "label": "受众广度", "weight": 1.0},
    {"key": "SAT", "label": "反差讽刺", "weight": 1.0},
]


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def ensure_data_dirs() -> None:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)
    (DEFAULT_PROJECT_PATH / "archive").mkdir(parents=True, exist_ok=True)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def default_config() -> dict:
    return {
        "version": APP_VERSION,
        "api_base_url": "https://api.openai.com/v1",
        "api_key": "",
        "model": "gpt-4.1-mini",
        "content_project_path": str(DEFAULT_PROJECT_PATH),
        "creator": {
            "content_type": "",
            "niche": "",
            "platform": "douyin",
        },
        "cloud": {
            "base_url": "",
            "device_id": "",
            "last_sync_at": "",
        },
        "license": {
            "status": "trial",
            "token": "",
            "activated_at": "",
            "last_checked_at": "",
            "offline_grace_days": 7,
        },
    }


def load_config(include_secret: bool = True) -> dict:
    ensure_data_dirs()
    config = default_config()
    if CONFIG_PATH.exists():
        try:
            saved = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            deep_update(config, saved)
        except json.JSONDecodeError:
            backup = CONFIG_PATH.with_suffix(".json.broken")
            CONFIG_PATH.replace(backup)
    if Path(config.get("content_project_path") or "") == LEGACY_DEFAULT_PROJECT_PATH:
        config["content_project_path"] = str(DEFAULT_PROJECT_PATH)
    if not include_secret:
        config = json.loads(json.dumps(config, ensure_ascii=False))
        if config.get("api_key"):
            config["api_key"] = MASKED_KEY
        if config.get("license", {}).get("token"):
            config["license"]["token"] = MASKED_KEY
    return config


def save_config(incoming: dict) -> dict:
    existing = load_config(include_secret=True)
    api_key = incoming.get("api_key", None)
    license_token = incoming.get("license", {}).get("token") if isinstance(incoming.get("license"), dict) else None

    if api_key is None or api_key == "" or api_key == MASKED_KEY:
        incoming.pop("api_key", None)
    if isinstance(incoming.get("license"), dict) and (license_token is None or license_token == "" or license_token == MASKED_KEY):
        incoming["license"].pop("token", None)

    deep_update(existing, incoming)
    existing["version"] = APP_VERSION
    atomic_write_text(CONFIG_PATH, json.dumps(existing, ensure_ascii=False, indent=2))
    return load_config(include_secret=False)


def deep_update(target: dict, incoming: dict) -> dict:
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            deep_update(target[key], value)
        else:
            target[key] = value
    return target


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    items: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError:
            items.append({"id": str(uuid.uuid4()), "type": "broken", "content": line, "sync_status": "error"})
    return items


def append_jsonl(path: Path, item: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item, ensure_ascii=False) + "\n")


def rewrite_jsonl(path: Path, items: list[dict]) -> None:
    text = "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in items)
    atomic_write_text(path, text)


def update_inbox_item(item_id: str, updates: dict) -> dict | None:
    items = read_jsonl(INBOX_PATH)
    updated = None
    for item in items:
        if item.get("id") == item_id:
            item.update(updates)
            updated = item
            break
    if updated:
        rewrite_jsonl(INBOX_PATH, items)
    return updated


def normalize_inspiration(item: dict, user_id: str = "local-user") -> dict:
    allowed_types = {"text", "voice", "image", "link", "video_link"}
    item_type = item.get("type") if item.get("type") in allowed_types else "text"
    tags = item.get("tags") if isinstance(item.get("tags"), list) else []
    normalized = {
        "id": item.get("id") or str(uuid.uuid4()),
        "user_id": item.get("user_id") or user_id,
        "type": item_type,
        "content": item.get("content", ""),
        "media_url": item.get("media_url", ""),
        "tags": tags,
        "created_at": item.get("created_at") or now_iso(),
        "sync_status": item.get("sync_status") or "pulled",
        "local_path": item.get("local_path", ""),
        "source_url": item.get("source_url", ""),
    }
    for key in (
        "demo",
        "skill_score",
        "blind_score",
        "score_source",
        "score_breakdown",
        "rubric_breakdown",
        "title_candidates",
        "selected_title",
        "scored_at",
        "artifact_paths",
    ):
        if key in item:
            normalized[key] = item[key]
    return normalized


def mirror_to_project_archive(item: dict, config: dict) -> str:
    raw_project_path = config.get("content_project_path") or ""
    if not raw_project_path.strip():
        return ""
    project_path = Path(raw_project_path)
    archive_path = project_path / "archive" / "inbox.jsonl"
    try:
        mirrored = dict(item)
        mirrored["sync_status"] = "archived"
        mirrored["local_path"] = str(archive_path)
        append_jsonl(archive_path, mirrored)
        return str(archive_path)
    except OSError:
        return ""


def list_project_files(config: dict) -> dict:
    raw_project_path = config.get("content_project_path") or ""
    project_path = Path(raw_project_path) if raw_project_path.strip() else Path()
    groups = {}
    for name in ["deliverables", "scripts", "predictions", "archive"]:
        base = project_path / name
        files = []
        if base.exists():
            for path in sorted(base.rglob("*")):
                if path.is_file():
                    files.append(
                        {
                            "path": str(path),
                            "name": path.name,
                            "size": path.stat().st_size,
                            "modified_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
                        }
                    )
        groups[name] = files
    return {"project_path": str(project_path), "groups": groups}


def resolve_project_file(config: dict, raw_path: str) -> Path:
    raw_project_path = config.get("content_project_path") or ""
    project_path = Path(raw_project_path) if raw_project_path.strip() else Path()
    project_root = project_path.resolve()
    resolved = Path(raw_path).resolve()
    try:
        resolved.relative_to(project_root)
    except ValueError as exc:
        raise ValueError("file must be inside the content project") from exc
    if not resolved.exists() or not resolved.is_file():
        raise FileNotFoundError("file not found")
    return resolved


def safe_slug(text: str, fallback: str = "idea", max_len: int = 36) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff]+", "-", text, flags=re.UNICODE).strip("-_")
    cleaned = cleaned[:max_len].strip("-_")
    return cleaned or fallback


def ensure_project_structure(project_path: Path) -> None:
    for folder in ["deliverables", "scripts", "predictions", "archive"]:
        (project_path / folder).mkdir(parents=True, exist_ok=True)


def project_path_from_config(config: dict) -> Path:
    raw = config.get("content_project_path") or str(DEFAULT_PROJECT_PATH)
    path = Path(raw)
    ensure_project_structure(path)
    return path


def route_deliverables(message: str) -> tuple[str, list[str]]:
    text = message.strip()
    explicit_routes = [
        (r"^(固化|收录|整理|候选|开始流程)", "spark_solidify", ["spark_card"]),
        (r"^(审核|审稿|验证|判断|检查)", "on_demand_production", ["review"]),
        (r"^(评分|打分|给.*评分|给.*打分)", "on_demand_production", ["score"]),
        (r"^(预测|预判)", "on_demand_production", ["prediction"]),
        (r"^(写.*脚本|生成.*脚本|视频脚本|口播脚本|口播稿)", "on_demand_production", ["video_script"]),
        (r"^(标题|封面|发布文案|简介|话题|评论区)", "on_demand_production", ["text_pack"]),
        (r"^(生成.*静态页|静态页|图文页|卡片文案|轮播)", "on_demand_production", ["static_page"]),
    ]
    for pattern, stage, deliverables in explicit_routes:
        if re.search(pattern, text):
            return stage, deliverables

    requested_full = any(token in text for token in ["完整", "全套", "做成视频", "成片", "完整流程"])
    if requested_full:
        return "guided_workflow", ["spark_card"]

    deliverables: list[str] = []
    if any(token in text for token in ["审核", "审稿", "验证", "值不值得", "值得做", "适合做", "人设匹配", "受众", "风险", "能不能发", "红线"]):
        deliverables.append("review")
    if any(token in text for token in ["评分", "打分", "分数"]):
        deliverables.append("score")
    if any(token in text for token in ["预测", "预判", "爆款", "播放"]):
        deliverables.append("prediction")
    if any(token in text for token in ["脚本", "口播脚本", "口播稿"]):
        deliverables.append("video_script")
    if any(token in text for token in ["标题", "封面", "发布文案", "简介", "话题", "评论区"]):
        deliverables.append("text_pack")
    if any(token in text for token in ["静态页", "图文页", "卡片文案", "轮播"]):
        deliverables.append("static_page")

    if deliverables:
        return "on_demand_production", list(dict.fromkeys(deliverables))
    if any(token in text for token in ["固化", "火花", "灵感", "收录", "候选"]):
        return "spark_solidify", ["spark_card"]
    if text:
        return "spark_solidify", ["spark_card"]
    return "deliverable_selection", []


def build_llm_prompt(message: str, deliverables: list[str], config: dict) -> str:
    creator = config.get("creator", {})
    labels = "、".join(DELIVERABLE_LABELS[key] for key in deliverables) if deliverables else "交付物选择"
    return (
        "你是一个给内容创作新手使用的本地 Agent。请按流程逐步引导："
        "灵感固化 -> 审核 -> 评分 -> 预测 -> 视频脚本 -> 文字/静态页物料。"
        "不要直接产出视频，不要一上来全套生产；核心产物是视频脚本和文字/静态页材料。"
        "输出要能直接给创作者使用，中文，清晰，避免空泛。\n\n"
        f"内容形态：{creator.get('content_type') or '未配置'}\n"
        f"赛道/人设：{creator.get('niche') or '未配置'}\n"
        f"平台：{creator.get('platform') or 'douyin'}\n"
        f"用户请求：{message}\n"
        f"本次只生产这些交付物：{labels}\n"
    )


def call_openai_compatible(prompt: str, config: dict) -> tuple[str, str]:
    api_key = config.get("api_key", "")
    if not api_key:
        return "", "未配置 API Key，使用本地 deterministic fallback。"
    base_url = (config.get("api_base_url") or "").rstrip("/")
    model = config.get("model") or "gpt-4.1-mini"
    if not base_url:
        return "", "未配置 API Base URL，使用本地 deterministic fallback。"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是新手创作者的脚本工作流助手，返回可直接落盘的中文内容。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
    }
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
        return content.strip(), "LLM 调用成功。"
    except (urllib.error.URLError, KeyError, json.JSONDecodeError, TimeoutError) as exc:
        return "", f"LLM 调用失败，使用本地 fallback：{exc}"


def test_openai_compatible(config: dict) -> dict:
    prompt = "请只回复：模型连接成功"
    content, note = call_openai_compatible(prompt, config)
    return {
        "ok": bool(content),
        "note": note,
        "model": config.get("model", ""),
        "api_base_url": config.get("api_base_url", ""),
        "reply": content,
    }


def cloud_request(method: str, base_url: str, path: str, payload: dict | None = None, timeout: int = 20) -> dict:
    url = base_url.rstrip("/") + path
    data = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def pull_cloud_inspirations(config: dict) -> tuple[list[dict], str]:
    cloud = config.get("cloud", {})
    base_url = (cloud.get("base_url") or "").strip()
    if not base_url:
        return [], "未配置 cloud.base_url，跳过云端拉取。"
    query = urlencode({"device_id": cloud.get("device_id", "")})
    try:
        data = cloud_request("GET", base_url, f"/api/desktop/inspirations/pending?{query}", None)
        items = data.get("items", []) if isinstance(data.get("items"), list) else []
        ids = [item.get("id") for item in items if item.get("id")]
        if ids:
            cloud_request("POST", base_url, "/api/desktop/inspirations/ack", {"ids": ids})
        return items, f"从云端拉取 {len(items)} 条灵感。"
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError) as exc:
        return [], f"云端拉取失败：{exc}"


def read_cloud_subscription(config: dict) -> dict:
    cloud = config.get("cloud", {})
    base_url = (cloud.get("base_url") or "").strip()
    if not base_url:
        return {}
    try:
        return cloud_request("GET", base_url, "/api/account/subscription", None)
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError):
        return {}


def extract_topic(message: str) -> str:
    text = message.strip()
    prefixes = [
        r"^(帮我|请|给我|做一个|做个|生成|写一个|写个)",
        r"^(看看|分析|优化|评价)",
        r"^(全套物料|全套|完整流程|完整|做成视频|成片)",
        r"^(固化灵感|固化这个灵感|审核这个灵感|审核这个选题|给这个选题评分|给这个灵感评分)",
        r"^(预测这个选题|预测这个灵感|写视频脚本|生成静态页文案|生成静态页|标题封面句|标题|发布文案)",
    ]
    changed = True
    while changed:
        changed = False
        for pattern in prefixes:
            updated = re.sub(pattern, "", text).strip(" ：:")
            if updated != text:
                text = updated
                changed = True
    return text or "未命名灵感"


def render_spark_card(topic: str, config: dict) -> str:
    creator = config.get("creator", {})
    niche = creator.get("niche") or "待配置"
    platform = creator.get("platform") or "douyin"
    return f"""# 灵感固化卡

原始灵感：{topic}

一句话选题：把“{topic}”收束成一个能被观众立刻理解的问题。

内容形态：{creator.get("content_type") or "待配置"}

适合人设：{niche}

目标平台：{platform}

目标受众：已经有类似困扰、但说不清问题到底卡在哪里的人。

核心痛点：想改变或表达，但缺少一个可判断、可行动的入口。

核心冲突：表面原因看起来是“不努力/不会做”，真实原因可能是“入口选错/判断标准错”。

可讲的个人场景：补充一个你自己或客户真实遇到的具体瞬间。

推荐切入角度：先讲一个具体画面，再给反常识判断，最后给一个简单判断标准。

前 3 秒钩子：你以为问题是不会做，其实可能是一开始就选错了入口。

下一步建议：先做内容审核，确认这个灵感是否值得进入评分和预测。
"""


def render_review(topic: str, config: dict) -> str:
    creator = config.get("creator", {})
    return f"""# 内容审核

主题：{topic}

审核结论：可以继续打磨，但需要补足“具体场景”和“个人判断”。

人设匹配：{creator.get("niche") or "未配置人设，建议先补充赛道/人设。"}

清晰度：
- 优点：问题方向有现实感，容易引发代入。
- 风险：如果只讲道理，会像泛观点，缺少记忆点。

平台风险：
- 暂无明显高风险表达。
- 避免绝对化承诺，比如“这样做一定爆”。

可信度：
- 需要加入真实案例、客户观察、失败经历或具体对比。

建议修改：
1. 把抽象观点换成一个具体画面。
2. 明确“我为什么有资格讲这个”。
3. 给观众一个能立刻自测的判断标准。

下一步建议：进入评分，判断这个选题是否值得写脚本。
"""


def render_score(topic: str) -> str:
    return f"""# 内容评分

主题：{topic}

> MVP 评分用于选题初筛，不等同于完整盲打分系统。

| 维度 | 分数 | 理由 |
|------|------|------|
| 受众痛感 | 4/5 | 主题指向常见困扰，容易被代入。 |
| 人设承载 | 3/5 | 需要补充个人经历或专业场景。 |
| 反常识强度 | 4/5 | “不是不努力，而是入口错”有转折。 |
| 具体度 | 2/5 | 当前仍偏抽象，需要一个真实例子。 |
| 互动潜力 | 4/5 | 适合引导评论区讲自己的卡点。 |

综合评分：17/25

推荐等级：B

处理建议：不要直接拍，先补一个具体故事或真实案例，再进入预测。
"""


def unique_strings(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        cleaned = re.sub(r"\s+", " ", item).strip(" ，。！？:：")
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result


def title_topic(topic: str, max_len: int = 18) -> str:
    cleaned = extract_topic(topic)
    cleaned = re.sub(r"^(测试火花|演示流|火花|灵感)[：:]\s*", "", cleaned)
    cleaned = re.sub(r"[\r\n]+", " ", cleaned).strip()
    return cleaned[:max_len].strip(" ，。！？:：") or "这个选题"


def generate_title_candidates(topic: str) -> list[str]:
    short = title_topic(topic)
    question_title = short if "为什么" in short else f"为什么{short}总是卡住？"
    candidates = [
        question_title,
        "你以为是执行力问题，其实是入口没想清楚",
        f"{short}背后的真正问题",
        "普通人做个人IP前，先问自己这个问题",
    ]
    return unique_strings(candidates)[:4]


def has_any(text: str, tokens: list[str]) -> bool:
    return any(token in text for token in tokens)


def dim_result(key: str, label: str, score: int, confidence: str, reason: str) -> dict:
    return {
        "dimension": key,
        "label": f"{key} {label}",
        "score": max(0, min(5, score)),
        "max": 5,
        "confidence": confidence,
        "reason": reason,
    }


def score_spark_dimensions(topic: str, selected_title: str) -> list[dict]:
    text = f"{selected_title}\n{topic}"
    length = len(topic)
    concrete = has_any(text, ["比如", "客户", "我", "你", "场景", "经历", "案例", "一次", "今天"])
    pain = has_any(text, ["痛", "卡", "失败", "焦虑", "半途", "拖延", "不会", "不敢", "困扰", "问题"])
    contrast = has_any(text, ["以为", "其实", "不是", "而是", "反差", "误区", "真相", "别急"])
    broad = has_any(text, ["普通人", "很多人", "新手", "大多数", "个人IP", "内容", "职场", "AI", "商业"])
    question = has_any(text, ["为什么", "怎么", "如何", "？", "?"])

    hp = 2 + int(question) + int(contrast) + int(len(selected_title) <= 34)
    er = 2 + int(pain) + int(has_any(text, ["普通人", "很多人", "你", "我"])) + int(concrete)
    sr = 1 + int(broad) + int(has_any(text, ["平台", "流量", "商业", "职场", "AI", "个人IP"])) + int(has_any(text, ["普通人", "新手"]))
    ql = 2 + int(contrast) + int(has_any(text, ["真相", "入口", "标准", "问题"])) + int(len(selected_title) <= 28)
    na = 1 + int(concrete) + int(length >= 18) + int(has_any(text, ["先", "再", "最后", "结果"]))
    ab = 2 + int(broad) + int(has_any(text, ["普通人", "很多人", "新手"])) + int(not has_any(text, ["极小众", "仅限"]))
    sat = 1 + int(contrast) + int(has_any(text, ["误区", "真相", "你以为", "别"])) + int(question)

    return [
        dim_result("HP", "钩子强度", hp, "high" if question or contrast else "medium", "标题有问题钩子/反常识入口" if question or contrast else "标题可读但钩子还可加强"),
        dim_result("ER", "情感共鸣", er, "high" if pain else "medium", "文本里有痛点词，容易代入" if pain else "情绪信号偏弱，需补真实场景"),
        dim_result("SR", "社会议题", sr, "medium" if broad else "low", "连接到普通人/平台/职业议题" if broad else "暂时偏个人问题，社会托底不足"),
        dim_result("QL", "金句密度", ql, "medium", "有可压缩成金句的反差判断" if contrast else "观点需要更锋利的一句话"),
        dim_result("NA", "叙事性", na, "medium" if concrete else "low", "已有场景线索，可展开故事" if concrete else "缺少具体人物或事件线"),
        dim_result("AB", "受众广度", ab, "high" if broad else "medium", "受众范围较宽，适合口播解释" if broad else "受众需要进一步界定"),
        dim_result("SAT", "反差讽刺", sat, "medium" if contrast else "low", "存在以为/其实式反差" if contrast else "讽刺和反差还不明显"),
    ]


def composite_score(dimensions: list[dict]) -> tuple[float, int]:
    weights = {item["key"]: item["weight"] for item in SPARK_RUBRIC}
    weighted = sum(dimension["score"] * weights.get(dimension["dimension"], 1.0) for dimension in dimensions)
    max_weighted = sum(item["weight"] * 5 for item in SPARK_RUBRIC)
    composite = round(weighted / max_weighted * 10, 2)
    return composite, round(composite * 10)


def blind_score_spark(topic: str, selected_title: str = "") -> dict:
    candidates = generate_title_candidates(topic)
    chosen_title = selected_title.strip() or candidates[0]
    if chosen_title not in candidates:
        candidates = unique_strings([chosen_title, *candidates])[:4]
    dimensions = score_spark_dimensions(topic, chosen_title)
    composite, skill_score = composite_score(dimensions)
    scoring_text = f"{chosen_title}\n{topic}"
    return {
        "skill_score": skill_score,
        "blind_score": skill_score,
        "score_source": "cheat-score-blind-compatible/local-v0",
        "score_source_note": "桌面后端按 blind-score JSON 字段写入；真实 sub-agent 接入后可替换 provider。",
        "rubric_version": "spark-v0",
        "composite": composite,
        "score_breakdown": dimensions,
        "title_candidates": candidates,
        "selected_title": chosen_title,
        "scored_at": now_iso(),
        "script_hash": hashlib.sha256(scoring_text.encode("utf-8")).hexdigest()[:12],
    }


def render_blind_score(topic: str, score_data: dict) -> str:
    rows = "\n".join(
        f"| {item['label']} | {item['score']}/5 | {item['confidence']} | {item['reason']} |"
        for item in score_data.get("score_breakdown", [])
    )
    candidates = "\n".join(f"- {candidate}" for candidate in score_data.get("title_candidates", []))
    return f"""# 火花盲评分

主题：{topic}

选用标题：{score_data.get("selected_title", "")}

综合分：{score_data.get("skill_score", 0)}/100

Composite：{score_data.get("composite", 0)}/10

评分来源：{score_data.get("score_source", "")}

说明：{score_data.get("score_source_note", "")}

候选标题：
{candidates}

| 维度 | 分数 | 置信度 | 理由 |
|------|------|--------|------|
{rows}

下一步建议：进入内容审核，判断风险、人设匹配和是否值得继续写脚本。
"""


def score_spark_item(item: dict, selected_title: str, config: dict, demo: bool = False) -> tuple[dict, list[dict]]:
    topic = item.get("content") or item.get("media_url") or "未命名灵感"
    score_data = blind_score_spark(topic, selected_title)
    rendered = {"score": render_blind_score(topic, score_data)}
    source = {"inbox_id": item.get("id", ""), "score_source": score_data["score_source"]}
    if demo:
        source["demo"] = True
    artifacts = write_deliverable_artifacts(
        f"给这个选题评分：{topic}",
        "blind_score",
        ["score"],
        rendered,
        "",
        config,
        source=source,
    )
    existing_paths = item.get("artifact_paths") if isinstance(item.get("artifact_paths"), list) else []
    score_data["artifact_paths"] = [*existing_paths, *[entry["path"] for entry in artifacts]]
    return score_data, artifacts


def is_demo_inbox_item(item: dict) -> bool:
    tags = item.get("tags") if isinstance(item.get("tags"), list) else []
    content = item.get("content") or item.get("media_url") or ""
    return bool(item.get("demo")) or "演示" in tags or content == DEMO_TOPIC


def manifest_is_demo(manifest: dict) -> bool:
    source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
    request = manifest.get("request") or ""
    topic = manifest.get("topic") or ""
    return bool(source.get("demo")) or topic == DEMO_TOPIC or DEMO_TOPIC in request


def reset_demo_data(config: dict) -> dict:
    inbox_items = read_jsonl(INBOX_PATH)
    kept_items = [item for item in inbox_items if not is_demo_inbox_item(item)]
    removed_inbox = len(inbox_items) - len(kept_items)
    if removed_inbox:
        rewrite_jsonl(INBOX_PATH, kept_items)

    project_path = project_path_from_config(config)
    deliverables_root = (project_path / "deliverables").resolve()
    removed_dirs = 0
    if deliverables_root.exists():
        manifest_paths = list(deliverables_root.rglob("manifest.json"))
        for manifest_path in manifest_paths:
            if not manifest_path.exists():
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if not manifest_is_demo(manifest):
                continue
            target_dir = manifest_path.parent.resolve()
            try:
                target_dir.relative_to(deliverables_root)
            except ValueError:
                continue
            shutil.rmtree(target_dir)
            removed_dirs += 1
    return {"removed_inbox": removed_inbox, "removed_deliverable_dirs": removed_dirs}


def render_prediction(topic: str) -> str:
    return f"""# 发布预测

主题：{topic}

预测档位：中等偏上

主要增长点：
- 观众容易被“我不是不努力”这类自我辩护/自我理解击中。
- 如果开头足够具体，完播会明显变好。

主要风险：
- 如果案例不足，会被理解成普通鸡汤。
- 如果标题太大，内容承接不住。

建议发布前补强：
1. 补一个 20 秒以内的真实案例。
2. 开头直接说判断，不要铺垫背景。
3. 结尾给一个自测问题，引导评论。

预测结论：可以写脚本，但脚本必须优先服务“具体场景 -> 反常识判断 -> 自测标准”。
"""


def render_video_script(topic: str) -> str:
    return f"""# 视频脚本 Draft

> 注意：这是 AI 生成的脚本骨架，发布前必须改成你自己的经历、语气和判断。

今天想讲一个很多人做个人 IP 时都会踩的坑。

你以为自己坚持不下去，是因为懒、拖延、执行力差。

但很多时候不是。

真正的问题是，你一开始就选了一个不属于你的入口。

比如你看到别人讲商业很火，你也去讲商业。
看到别人做情绪价值很火，你也去讲情绪价值。
但你没有真实经历，没有稳定观点，也没有持续观察这个领域的习惯。

结果就会发生一件事：
你不是不会做内容，你是每次都在硬演一个不属于你的人设。

所以普通人做 IP，第一步不是找爆款公式。
第一步是问自己：
这个选题，我能不能连续讲十条，而且每一条都有自己的真实经验？

如果不能，它就不是你的主线。

你可以蹭一次热点，但不要把它当成长期方向。

真正能坚持下来的内容，一定不是最热的，而是你有长期感受、长期案例、长期表达冲动的。

这才是普通人做内容最容易忽略的起点。

主题：{topic}
"""


def render_text_pack(topic: str) -> str:
    return f"""# 标题与发布文字

主题：{topic}

标题备选：
1. 你不是不努力，你是一开始就选错入口
2. 为什么普通人做内容总是半途而废
3. 真正拖垮你的，不是懒，是判断标准错了
4. 做个人 IP 前，先搞懂这件事
5. 别急着开干，先问自己这个问题

封面句：
- 不是不行，是入口错了
- 你缺的不是方法
- 半途而废的真相

发布文案：
很多人做内容半途而废，并不是因为懒，也不是因为没有方法。
真正的问题是：一开始选的目标就没有和自己的处境、资源、表达欲匹配。
这条聊聊怎么在开干前先判断一件事值不值得做。

话题：
#个人IP #内容创作 #普通人成长 #副业 #认知
"""


def render_static_page(topic: str) -> str:
    return f"""# 静态页文案

主题：{topic}

第 1 页：你不是不努力
副标题：你可能是一开始就选错了入口。

第 2 页：很多人误判了问题
正文：他们以为自己缺方法、缺执行力，其实缺的是一个适合自己的判断标准。

第 3 页：错误入口的三个信号
正文：
1. 没有真实经历。
2. 没有稳定观点。
3. 没有持续观察。

第 4 页：一个自测问题
正文：这个主题，你能不能连续讲十条，而且每一条都有自己的真实经验？

第 5 页：结论
正文：热点可以蹭，但主线必须属于你。
"""


def render_deliverables(topic: str, deliverables: list[str], config: dict) -> dict[str, str]:
    renderers = {
        "spark_card": lambda: render_spark_card(topic, config),
        "review": lambda: render_review(topic, config),
        "score": lambda: render_score(topic),
        "prediction": lambda: render_prediction(topic),
        "video_script": lambda: render_video_script(topic),
        "text_pack": lambda: render_text_pack(topic),
        "static_page": lambda: render_static_page(topic),
    }
    return {key: renderers[key]() for key in deliverables if key in renderers}


def write_deliverable_artifacts(
    message: str,
    stage: str,
    deliverables: list[str],
    rendered: dict[str, str],
    llm_text: str,
    config: dict,
    source: dict | None = None,
) -> list[dict]:
    if not deliverables and not llm_text:
        return []
    topic = extract_topic(message)
    project_path = project_path_from_config(config)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    artifact_dir = project_path / "deliverables" / f"{stamp}_{safe_slug(topic)}"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    files: list[dict] = []

    name_map = {
        "spark_card": "spark-card.md",
        "review": "review.md",
        "score": "score.md",
        "prediction": "prediction.md",
        "video_script": "video-script.md",
        "text_pack": "text-pack.md",
        "static_page": "static-page.md",
    }
    for key, content in rendered.items():
        path = artifact_dir / name_map.get(key, f"{key}.md")
        atomic_write_text(path, content)
        files.append({"type": key, "label": DELIVERABLE_LABELS.get(key, key), "path": str(path)})

    if llm_text:
        path = artifact_dir / "llm-output.md"
        atomic_write_text(path, "# LLM Output\n\n" + llm_text + "\n")
        files.append({"type": "llm_output", "label": "LLM 输出", "path": str(path)})

    manifest = {
        "id": str(uuid.uuid4()),
        "created_at": now_iso(),
        "stage": stage,
        "request": message,
        "topic": topic,
        "deliverables": deliverables,
        "source": source or {},
        "files": files,
    }
    manifest_path = artifact_dir / "manifest.json"
    atomic_write_text(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2))
    files.append({"type": "manifest", "label": "Manifest", "path": str(manifest_path)})
    return files


def next_step_for(deliverables: list[str], topic: str) -> dict:
    present = set(deliverables)
    if "static_page" in present:
        return {"label": "完成", "prompt": "这个选题的 MVP 文字流程已完成，可以人工修改脚本后进入拍摄。"}
    if "video_script" in present:
        return {"label": "静态页文案", "prompt": f"生成静态页文案：{topic}"}
    if "prediction" in present:
        return {"label": "视频脚本", "prompt": f"写视频脚本：{topic}"}
    if "score" in present:
        return {"label": "预测", "prompt": f"预测这个选题：{topic}"}
    if "review" in present:
        return {"label": "评分", "prompt": f"给这个选题评分：{topic}"}
    if "text_pack" in present:
        return {"label": "静态页文案", "prompt": f"生成静态页文案：{topic}"}
    if "spark_card" in present:
        return {"label": "审核", "prompt": f"审核这个灵感：{topic}"}
    return {"label": "灵感固化", "prompt": f"固化这个灵感：{topic}"}


def local_agent_reply(message: str, config: dict, source: dict | None = None) -> dict:
    text = message.strip()
    stage, deliverables = route_deliverables(text)
    topic = extract_topic(text)

    worklog = [
        "读取当前创作者配置。",
        "按内容生产入口规则判断用户阶段。",
        f"本次阶段：{stage}。",
    ]

    llm_text = ""
    llm_note = "未请求 LLM。"
    if deliverables:
        llm_text, llm_note = call_openai_compatible(build_llm_prompt(text, deliverables, config), config)
        worklog.append(llm_note)

    rendered = render_deliverables(topic, deliverables, config)
    artifacts = write_deliverable_artifacts(text, stage, deliverables, rendered, llm_text, config, source)
    if artifacts:
        worklog.append(f"已落盘 {len(artifacts)} 个产物文件。")

    next_step = next_step_for(deliverables, topic)

    if stage == "guided_workflow":
        summary = "先不急着一次做完。我已完成第一步：灵感固化，并给出下一步引导。"
    elif deliverables:
        labels = "、".join(DELIVERABLE_LABELS[key] for key in deliverables)
        summary = f"当前步骤已完成：{labels}，我已写入本地文件。"
    else:
        summary = "请先输入一个灵感火花，或从手机灵感点“开始流程”。"

    if deliverables:
        result = {
            "topic": topic,
            "deliverables": [{"type": key, "label": DELIVERABLE_LABELS[key]} for key in deliverables],
            "llm_used": bool(llm_text),
            "llm_note": llm_note,
            "artifacts": artifacts,
            "preview": {key: value.splitlines()[:8] for key, value in rendered.items()},
            "next_step": next_step,
        }
    else:
        result = {
            "options": [
                "输入一个灵感火花",
                "固化灵感",
                "审核",
                "评分",
                "预测",
                "视频脚本",
                "标题/发布文字",
                "静态页文案",
            ]
        }

    return {
        "id": str(uuid.uuid4()),
        "created_at": now_iso(),
        "status": "ok",
        "stage": stage,
        "summary": summary,
        "worklog": worklog,
        "actions": [{"type": "open_file", "path": item["path"], "label": item["label"]} for item in artifacts],
        "result": result,
    }


class WorkbenchHandler(BaseHTTPRequestHandler):
    server_version = "ContentWorkbench/0.1"

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/":
            self.serve_file(STATIC_ROOT / "index.html")
        elif path.startswith("/static/"):
            rel = unquote(path.removeprefix("/static/"))
            self.serve_file(STATIC_ROOT / rel)
        elif path == "/api/status":
            config = load_config(include_secret=False)
            self.send_json(
                {
                    "status": "ok",
                    "version": APP_VERSION,
                    "data_root": str(DATA_ROOT),
                    "project_path": config.get("content_project_path"),
                    "license": config.get("license", {}),
                }
            )
        elif path == "/api/config":
            self.send_json(load_config(include_secret=False))
        elif path == "/api/inbox":
            self.send_json({"items": read_jsonl(INBOX_PATH)})
        elif path == "/api/files":
            self.send_json(list_project_files(load_config(include_secret=False)))
        elif path == "/api/license/status":
            config = load_config(include_secret=False)
            license_data = config.get("license", {})
            cloud_subscription = read_cloud_subscription(config)
            if cloud_subscription.get("status"):
                license_data = {**license_data, **cloud_subscription, "source": "cloud"}
            self.send_json(
                {
                    "status": license_data.get("status", "trial"),
                    "offline_grace_days": license_data.get("offline_grace_days", 7),
                    "last_checked_at": license_data.get("last_checked_at", ""),
                    "activated_at": license_data.get("activated_at", ""),
                    "source": license_data.get("source", "local"),
                }
            )
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            payload = self.read_json_body()
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if path == "/api/config":
            self.send_json(save_config(payload))
        elif path == "/api/chat":
            config = load_config(include_secret=True)
            if payload.get("force_local"):
                config["api_key"] = ""
            message = payload.get("message", "")
            source = {"demo": True} if payload.get("demo") else None
            reply = local_agent_reply(message, config, source=source)
            self.save_conversation_turn(message, reply)
            self.send_json(reply)
        elif path == "/api/llm/test":
            config = load_config(include_secret=True)
            result = test_openai_compatible(config)
            self.send_json(result, HTTPStatus.OK if result["ok"] else HTTPStatus.BAD_GATEWAY)
        elif path == "/api/file/read":
            config = load_config(include_secret=False)
            try:
                file_path = resolve_project_file(config, payload.get("path", ""))
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except (ValueError, FileNotFoundError, OSError) as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            self.send_json({"status": "ok", "name": file_path.name, "content": content})
        elif path == "/api/file/open":
            config = load_config(include_secret=False)
            try:
                file_path = resolve_project_file(config, payload.get("path", ""))
                os.startfile(file_path)  # type: ignore[attr-defined]
            except (ValueError, FileNotFoundError, OSError) as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            self.send_json({"status": "ok", "path": str(file_path)})
        elif path == "/api/inbox":
            item = normalize_inspiration(payload)
            append_jsonl(INBOX_PATH, item)
            self.send_json({"status": "ok", "item": item}, HTTPStatus.CREATED)
        elif path == "/api/spark/blind-score":
            config = load_config(include_secret=True)
            item_id = payload.get("id", "")
            content = (payload.get("content") or "").strip()
            selected_title = payload.get("selected_title", "")
            item = next((entry for entry in read_jsonl(INBOX_PATH) if entry.get("id") == item_id), None)
            created = False
            if not item:
                if not content:
                    self.send_json({"error": "content is required"}, HTTPStatus.BAD_REQUEST)
                    return
                item = normalize_inspiration(
                    {
                        "id": item_id or str(uuid.uuid4()),
                        "type": payload.get("type", "text"),
                        "content": content,
                        "media_url": payload.get("media_url", ""),
                        "tags": payload.get("tags") if isinstance(payload.get("tags"), list) else [],
                        "sync_status": "pulled",
                        "demo": bool(payload.get("demo")),
                    }
                )
                created = True
            score_updates, artifacts = score_spark_item(item, selected_title, config, demo=bool(payload.get("demo") or item.get("demo")))
            if payload.get("demo"):
                score_updates["demo"] = True
            if created:
                item.update(score_updates)
                append_jsonl(INBOX_PATH, item)
                updated = item
            else:
                updated = update_inbox_item(item["id"], score_updates) or {**item, **score_updates}
            self.send_json({"status": "ok", "item": updated, "artifacts": artifacts})
        elif path == "/api/demo/reset":
            result = reset_demo_data(load_config(include_secret=False))
            self.send_json({"status": "ok", **result})
        elif path == "/api/inbox/produce":
            item_id = payload.get("id", "")
            instruction = payload.get("instruction", "选题分析")
            item = next((entry for entry in read_jsonl(INBOX_PATH) if entry.get("id") == item_id), None)
            if not item:
                self.send_json({"error": "inbox item not found"}, HTTPStatus.NOT_FOUND)
                return
            message = f"{instruction}：{item.get('content') or item.get('media_url') or ''}"
            config = load_config(include_secret=True)
            reply = local_agent_reply(message, config, source={"inbox_id": item_id})
            artifact_paths = [entry["path"] for entry in reply.get("result", {}).get("artifacts", [])]
            updated = update_inbox_item(
                item_id,
                {
                    "sync_status": "processed",
                    "processed_at": now_iso(),
                    "artifact_paths": artifact_paths,
                },
            )
            self.save_conversation_turn(message, reply)
            self.send_json({"status": "ok", "item": updated, "reply": reply})
        elif path == "/api/cloud/link-device":
            config = load_config(include_secret=True)
            cloud = config.get("cloud", {})
            base_url = (cloud.get("base_url") or "").strip()
            if not base_url:
                self.send_json({"error": "cloud.base_url is required"}, HTTPStatus.BAD_REQUEST)
                return
            device_name = payload.get("device_name") or os.environ.get("COMPUTERNAME") or "desktop"
            try:
                linked = cloud_request("POST", base_url, "/api/device/link", {"device_name": device_name})
            except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError) as exc:
                self.send_json({"error": f"device link failed: {exc}"}, HTTPStatus.BAD_GATEWAY)
                return
            config["cloud"]["device_id"] = linked.get("device_id", "")
            save_config(config)
            self.send_json({"status": "ok", "device": linked})
        elif path == "/api/sync/inspirations":
            config = load_config(include_secret=True)
            items = payload.get("items") if isinstance(payload.get("items"), list) else []
            sync_note = "使用请求体中的 items。"
            if not items:
                items, sync_note = pull_cloud_inspirations(config)
            pulled = []
            for raw_item in items:
                item = normalize_inspiration(raw_item)
                item["sync_status"] = "pulled"
                archive_path = mirror_to_project_archive(item, config)
                if archive_path:
                    item["sync_status"] = "archived"
                    item["local_path"] = archive_path
                append_jsonl(INBOX_PATH, item)
                pulled.append(item)
            config["cloud"]["last_sync_at"] = now_iso()
            save_config(config)
            self.send_json({"status": "ok", "pulled": len(pulled), "items": pulled, "note": sync_note})
        elif path == "/api/license/activate":
            token = payload.get("token", "").strip()
            if not token:
                self.send_json({"error": "token is required"}, HTTPStatus.BAD_REQUEST)
                return
            config = load_config(include_secret=True)
            config["license"]["token"] = token
            config["license"]["status"] = "active"
            config["license"]["activated_at"] = now_iso()
            config["license"]["last_checked_at"] = now_iso()
            self.send_json(save_config(config).get("license", {}))
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON body") from exc
        if not isinstance(data, dict):
            raise ValueError("JSON body must be an object")
        return data

    def save_conversation_turn(self, message: str, reply: dict) -> None:
        item = {"message": message, "reply": reply, "created_at": now_iso()}
        path = CONVERSATIONS_DIR / (datetime.now().strftime("%Y-%m-%d") + ".jsonl")
        append_jsonl(path, item)

    def serve_file(self, path: Path) -> None:
        try:
            resolved = path.resolve()
            static_root = STATIC_ROOT.resolve()
            try:
                resolved.relative_to(static_root)
            except ValueError:
                self.send_error(HTTPStatus.NOT_FOUND, "Not found")
                return
            if not resolved.exists() or not resolved.is_file():
                self.send_error(HTTPStatus.NOT_FOUND, "Not found")
                return
            content_type = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
            data = resolved.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_cors_headers()
            self.send_header("Content-Type", content_type + "; charset=utf-8" if content_type.startswith("text/") else content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except OSError:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "Could not read file")

    def send_json(self, data: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, fmt: str, *args: object) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {self.address_string()} {fmt % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Content Workbench local server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7870)
    args = parser.parse_args()
    ensure_data_dirs()
    server = ThreadingHTTPServer((args.host, args.port), WorkbenchHandler)
    print(f"Content Workbench {APP_VERSION} running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
