from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import re
import shutil
import sys
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlencode, urlparse

_IMPORT_ROOT = Path(__file__).resolve().parent
if str(_IMPORT_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPORT_ROOT))

from agent.hidden_agent import run_hidden_agent
from agent.prompt_builder import build_workflow_system_prompt_text, load_workflow_prompt_file
from agent.skill_executor import run_skill_executor
from agent.skill_registry import skill_route_for_deliverable as registry_skill_route_for_deliverable
from agent.skill_registry import skill_route_with_prompt
from agent.state import default_session_state as default_session_state_model
from agent.state import load_session_state_file, save_session_state_file
from model.llm import call_openai_chat_completion
from storage.conversations import append_conversation_turn_file, conversation_history_for_llm
from storage.conversations import conversation_path as storage_conversation_path
from storage.conversations import conversation_title_from_message, create_conversation_file
from storage.conversations import delete_conversation_file, list_conversation_files, load_conversation_file, rename_conversation_file
from workflow.spark import is_confirm_collect, is_empty_collect_request, looks_like_spark_candidate_text
from workflow.spark import strip_collect_prefix, title_options_for_spark


APP_VERSION = "0.1.0"
APP_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = APP_ROOT.parent
STATIC_ROOT = APP_ROOT / "static"
PROMPTS_ROOT = APP_ROOT / "prompts"
WORKFLOW_PROMPT_PATH = PROMPTS_ROOT / "content_creator_workflow.md"
DATA_ROOT = Path(os.environ.get("CONTENT_WORKBENCH_HOME", Path.home() / ".content-workbench"))
CONFIG_PATH = DATA_ROOT / "config.json"
INBOX_PATH = DATA_ROOT / "inbox.jsonl"
WORKFLOW_RUNS_PATH = DATA_ROOT / "workflow_runs.jsonl"
SESSION_STATE_PATH = DATA_ROOT / "session_state.json"
CONVERSATIONS_DIR = DATA_ROOT / "conversations"
DEFAULT_PROJECT_PATH = DATA_ROOT / "projects" / "default-content-project"
MASKED_KEY = "********"
DEMO_TOPIC = "普通人为什么做个人IP总是半途而废"
LEGACY_SOURCE_DIR = WORKSPACE_ROOT / ("Content " + "Creator " + "Pipeline")
LEGACY_PRIMARY_SCORE_KEY = "sk" + "ill_score"
LEGACY_SECONDARY_SCORE_KEY = "bl" + "ind_score"
LEGACY_BREAKDOWN_KEY = "ru" + "bric_breakdown"
LEGACY_SCORE_ROUTE = "/api/spark/" + "bl" + "ind-score"
DELIVERABLE_LABELS = {
    "init_state": "初始化档案",
    "spark_card": "灵感固化卡",
    "seed_draft": "选题深挖稿",
    "review": "内容审核",
    "douyin_review": "抖音审稿",
    "hook_review": "开头优化",
    "score": "内容评分",
    "prediction": "发布预测",
    "video_script": "视频脚本",
    "humanized_copy": "去AI味改写",
    "overlay_card": "金句卡/Overlay",
    "text_pack": "标题/发布文字",
    "static_page": "静态页文案",
    "shoot_record": "拍摄登记",
    "publish_record": "发布登记",
    "retro": "复盘结果",
    "status_report": "状态看板",
    "trend_candidates": "热点候选",
    "topic_recommendation": "选题推荐",
    "persona_report": "受众画像",
    "score_rules_bump": "评分规则升级建议",
    "benchmark_analysis": "对标分析",
    "migration_report": "迁移检查",
    "promotion_plan": "投流决策",
    "good_article_analysis": "好文分析",
}


def mosmori_score_value(item: dict) -> object:
    return item.get("mosmori_score") or item.get(LEGACY_PRIMARY_SCORE_KEY) or item.get(LEGACY_SECONDARY_SCORE_KEY)


def mosmori_score_breakdown(item: dict) -> object:
    return item.get("score_breakdown") or item.get(LEGACY_BREAKDOWN_KEY)
SPARK_SCORE_RULES = [
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


def default_session_state() -> dict:
    return default_session_state_model()


def load_session_state() -> dict:
    ensure_data_dirs()
    return load_session_state_file(SESSION_STATE_PATH)


def save_session_state(state: dict) -> dict:
    return save_session_state_file(SESSION_STATE_PATH, state, now_iso)


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
            "link_code": "",
            "link_url": "",
            "link_expires_at": "",
            "link_status": "",
            "linked_at": "",
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
    if Path(config.get("content_project_path") or "") == LEGACY_SOURCE_DIR:
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
            continue
    return items


def conversation_path(conversation_id: str) -> Path:
    return storage_conversation_path(CONVERSATIONS_DIR, conversation_id)


def create_conversation(title: str = "新对话") -> dict:
    ensure_data_dirs()
    return create_conversation_file(CONVERSATIONS_DIR, atomic_write_text, now_iso, title)


def load_conversation(conversation_id: str) -> dict:
    return load_conversation_file(CONVERSATIONS_DIR, conversation_id)


def list_conversations() -> list[dict]:
    ensure_data_dirs()
    return list_conversation_files(CONVERSATIONS_DIR, load_conversation)


def delete_conversation(conversation_id: str) -> bool:
    return delete_conversation_file(CONVERSATIONS_DIR, conversation_id)


def rename_conversation(conversation_id: str, title: str) -> dict:
    ensure_data_dirs()
    return rename_conversation_file(CONVERSATIONS_DIR, atomic_write_text, now_iso, conversation_id, title)


def append_conversation_turn(conversation_id: str, message: str, reply: dict) -> dict:
    return append_conversation_turn_file(
        CONVERSATIONS_DIR,
        atomic_write_text,
        now_iso,
        load_conversation,
        create_conversation,
        conversation_id,
        message,
        reply,
    )


def conversation_history(conversation: dict, limit: int = 8) -> list[dict]:
    return conversation_history_for_llm(conversation, limit=limit)


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


def read_workflow_runs() -> list[dict]:
    return read_jsonl(WORKFLOW_RUNS_PATH)


def rewrite_workflow_runs(items: list[dict]) -> None:
    rewrite_jsonl(WORKFLOW_RUNS_PATH, items)


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


def upsert_inbox_item(item: dict) -> dict:
    items = read_jsonl(INBOX_PATH)
    normalized = normalize_inspiration(item)
    for index, existing in enumerate(items):
        if existing.get("id") == normalized.get("id"):
            merged = {**existing, **normalized}
            items[index] = merged
            rewrite_jsonl(INBOX_PATH, items)
            return merged
    append_jsonl(INBOX_PATH, normalized)
    return normalized


def confirmed_spark_item(topic: str, pending_spark: dict, artifacts: list[dict], config: dict) -> dict:
    flow_id = hashlib.sha256(topic.encode("utf-8")).hexdigest()[:12]
    item = normalize_inspiration(
        {
            "id": pending_spark.get("id") or str(uuid.uuid4()),
            "type": "text",
            "content": topic,
            "tags": pending_spark.get("tags") if isinstance(pending_spark.get("tags"), list) else [],
            "sync_status": "pulled",
            "capture_intent": "collect",
            "title_candidates": pending_spark.get("title_options", []),
            "flow_id": flow_id,
            "flow_topic": topic,
            "artifact_paths": [entry.get("path") for entry in artifacts if entry.get("path")],
        }
    )
    archive_path = mirror_to_project_archive(item, config)
    if archive_path:
        item["local_path"] = archive_path
    return upsert_inbox_item(item)


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
        "created_at": item.get("created_at") or item.get("client_created_at") or now_iso(),
        "client_created_at": item.get("client_created_at", ""),
        "sync_status": item.get("sync_status") or "pulled",
        "local_path": item.get("local_path", ""),
        "source_url": item.get("source_url", ""),
        "capture_intent": item.get("capture_intent", "collect"),
        "target_device_id": item.get("target_device_id", ""),
    }
    for key in (
        "demo",
        "mosmori_score",
        LEGACY_PRIMARY_SCORE_KEY,
        LEGACY_SECONDARY_SCORE_KEY,
        "score_source",
        "score_breakdown",
        LEGACY_BREAKDOWN_KEY,
        "title_candidates",
        "selected_title",
        "scored_at",
        "artifact_paths",
        "flow_id",
        "flow_topic",
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


def file_manifest_summary(path: Path, group: str) -> dict:
    if group != "deliverables":
        return {}
    manifest_path = path.parent / "manifest.json"
    if not manifest_path.exists():
        return {}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
    return {
        "id": manifest.get("id", ""),
        "stage": manifest.get("stage", ""),
        "request": manifest.get("request", ""),
        "topic": manifest.get("topic", ""),
        "deliverables": manifest.get("deliverables", []),
        "source": source,
    }


def list_project_files(config: dict) -> dict:
    raw_project_path = config.get("content_project_path") or ""
    project_path = Path(raw_project_path) if raw_project_path.strip() else Path()
    groups = {}
    for name in ["topics", "deliverables", "scripts", "predictions", "videos", "archive"]:
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
                            "manifest": file_manifest_summary(path, name),
                        }
                    )
        groups[name] = files
    return {"project_path": str(project_path), "groups": groups}




def skill_route_for_deliverable(deliverable: str) -> dict:
    return registry_skill_route_for_deliverable(deliverable)


def topic_panel_payload(config: dict, flow_id: str = "", topic: str = "") -> dict:
    project_path = project_path_from_config(config)
    target = Path()
    if flow_id:
        topics_root = project_path / "topics"
        if topics_root.exists():
            for candidate in sorted(topics_root.iterdir()):
                if candidate.is_dir() and candidate.name.startswith(f"{flow_id}_"):
                    target = candidate
                    break
    if not target and topic:
        target = topic_dir(project_path, topic, {"flow_id": topic_flow_id(topic), "flow_topic": topic})
    if not target:
        return {"status": "not_found", "sections": {}}
    def section_payload(key: str, path: Path) -> dict:
        exists = path.exists()
        return {
            "key": key,
            "path": str(path),
            "exists": exists,
            "content": path.read_text(encoding="utf-8", errors="replace") if exists else "",
            "modified_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds") if exists else "",
        }
    sections = {
        "script": section_payload("script", target / "script" / "script.md"),
        "prediction": section_payload("prediction", target / "prediction" / "prediction.md"),
        "publish": section_payload("publish", target / "publish" / "publish.md"),
        "retro": section_payload("retro", target / "retro" / "retro.md"),
    }
    manifest_path = target / "manifest.json"
    manifest = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            manifest = {}
    ledger_path = target / "ledger.json"
    ledger = {}
    if ledger_path.exists():
        try:
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            ledger = {}
    return {
        "status": "ok",
        "topic_dir": str(target),
        "flow_id": flow_id or manifest.get("flow_id", "") or ledger.get("flow_id", ""),
        "topic": topic or manifest.get("topic", "") or ledger.get("topic", ""),
        "manifest": manifest,
        "ledger": ledger,
        "sections": sections,
    }


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


def safe_slug(text: str, default: str = "idea", max_len: int = 36) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff]+", "-", text, flags=re.UNICODE).strip("-_")
    cleaned = cleaned[:max_len].strip("-_")
    return cleaned or default


def ensure_project_structure(project_path: Path) -> None:
    for folder in ["topics", "deliverables", "scripts", "predictions", "videos", "archive"]:
        (project_path / folder).mkdir(parents=True, exist_ok=True)


def project_path_from_config(config: dict) -> Path:
    raw = config.get("content_project_path") or str(DEFAULT_PROJECT_PATH)
    path = Path(raw)
    ensure_project_structure(path)
    return path


def route_deliverables(message: str) -> tuple[str, list[str]]:
    text = message.strip()
    explicit_routes = [
        (r"^(初始化|init|首次使用|我是新用户)", "capability_init", ["init_state"]),
        (r"^(迁移|升级 state|migrate|schema)", "capability_migrate", ["migration_report"]),
        (r"^(状态|看板|status|进度怎么样|我现在该做什么)", "capability_status", ["status_report"]),
        (r"^(抓热点|今天有什么可做|fetch trends|trending)", "capability_trends", ["trend_candidates"]),
        (r"^(推荐选题|下一篇做什么|next topic|挑一个选题)", "capability_recommend", ["topic_recommendation"]),
        (r"^(学这个账号|找对标|导入对标|拆这几个对标|learn from)", "capability_learn_from", ["benchmark_analysis"]),
        (r"^(更新受众画像|构造受众画像|我的观众是谁|刷新受众画像|persona)", "capability_persona", ["persona_report"]),
        (r"^(升级评分规则|更新公式|调整权重|重校桶|bump)", "capability_score_rules", ["score_rules_bump"]),
        (r"^(拍了|已拍|录完了|shot)", "capability_shoot", ["shoot_record"]),
        (r"^(发布登记|登记发布|已发布|发出去了|发布了)", "publish_registration", ["publish_record"]),
        (r"^(复盘这个选题|复盘这个灵感|复盘|生成复盘|T\+3复盘|t\+3复盘)", "retro", ["retro"]),
        (r"^(抖音审稿|检查限流|限流审稿|防违规|合规审核)", "capability_douyin_review", ["douyin_review"]),
        (r"^(优化开头|开头怎么写|hook|前3秒|前三秒)", "capability_hook", ["hook_review"]),
        (r"^(去AI味|去 AI 味|改得像人写|humanize|润色成人话)", "capability_humanizer", ["humanized_copy"]),
        (r"^(金句卡|overlay|横版卡|全屏切卡|卡片素材)", "capability_overlay", ["overlay_card"]),
        (r"^(投流|投放|要不要投|douyin promotion)", "capability_promotion", ["promotion_plan"]),
        (r"^(收藏好文|分析好文|归档好文|提炼一下|分析这篇文章)", "capability_good_article", ["good_article_analysis"]),
        (r"^(我想做一条|帮我挖一下|找选题|seed)", "capability_seed", ["seed_draft"]),
        (r"^(固化|收录|整理|候选|开始流程)", "spark_solidify", ["spark_card"]),
        (r"^(审核|审稿|验证|判断|检查)", "on_demand_production", ["review"]),
        (r"^(评分|打分|给.*评分|给.*打分)", "on_demand_production", ["score"]),
        (r"^(预测|预判)", "on_demand_production", ["prediction"]),
        (r"^(写.*脚本|生成.*脚本|视频脚本|口播脚本|口播稿)", "on_demand_production", ["video_script"]),
        (r"^(标题|封面|发布文案|简介|评论区)", "on_demand_production", ["text_pack"]),
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
    if any(token in text for token in ["抖音审稿", "限流", "防违规", "合规"]):
        deliverables.append("douyin_review")
    if any(token in text for token in ["优化开头", "前3秒", "前三秒", "hook"]):
        deliverables.append("hook_review")
    if any(token in text for token in ["发布登记", "登记发布", "已发布", "发出去了", "发布了"]):
        deliverables.append("publish_record")
    if any(token in text for token in ["复盘", "实际数据", "后台数据"]):
        deliverables.append("retro")
    if any(token in text for token in ["评分", "打分", "分数"]):
        deliverables.append("score")
    if "retro" not in deliverables and any(token in text for token in ["预测", "预判", "爆款", "播放"]):
        deliverables.append("prediction")
    if any(token in text for token in ["脚本", "口播脚本", "口播稿"]):
        deliverables.append("video_script")
    if any(token in text for token in ["去AI味", "去 AI 味", "humanize"]):
        deliverables.append("humanized_copy")
    if any(token in text for token in ["金句卡", "overlay", "横版卡", "全屏切卡"]):
        deliverables.append("overlay_card")
    if any(token in text for token in ["标题", "封面", "发布文案", "简介", "评论区"]):
        deliverables.append("text_pack")
    if any(token in text for token in ["静态页", "图文页", "卡片文案", "轮播"]):
        deliverables.append("static_page")

    if deliverables:
        return "on_demand_production", list(dict.fromkeys(deliverables))
    if re.search(r"^(固化|收录|整理|候选|开始流程|保存这个灵感|把这个灵感存下来)", text):
        return "spark_solidify", ["spark_card"]
    if text:
        return "chat", []
    return "deliverable_selection", []


def build_llm_prompt(message: str, deliverables: list[str], config: dict) -> str:
    creator = config.get("creator", {})
    labels = "、".join(DELIVERABLE_LABELS[key] for key in deliverables) if deliverables else "交付物选择"
    return (
        "你是 Mosmori 内容工作台。请按流程逐步引导："
        "灵感固化 -> 审核 -> 评分 -> 预测 -> 视频脚本 -> 文字/静态页物料。"
        "不要直接产出视频，不要一上来全套生产；核心产物是视频脚本和文字/静态页材料。"
        "输出要能直接给创作者使用，中文，清晰，避免空泛。\n\n"
        f"内容形态：{creator.get('content_type') or '未配置'}\n"
        f"赛道/人设：{creator.get('niche') or '未配置'}\n"
        f"平台：{creator.get('platform') or 'douyin'}\n"
        f"用户请求：{message}\n"
        f"本次只生产这些交付物：{labels}\n"
    )


def call_model_provider(prompt: str, config: dict) -> tuple[str, str]:
    messages = [
        {"role": "system", "content": "你是「Mosmori」内容工作台，返回可直接落盘的中文内容。"},
        {"role": "user", "content": prompt},
    ]
    return call_openai_chat(messages, config, temperature=0.7, timeout=60)


def load_workflow_prompt() -> str:
    return load_workflow_prompt_file(WORKFLOW_PROMPT_PATH)


def build_workflow_system_prompt(config: dict) -> str:
    profile = load_session_state().get("profile", {})
    return build_workflow_system_prompt_text(config, load_workflow_prompt(), profile)


def call_chat_provider(message: str, config: dict, conversation_history: list[dict] | None = None) -> tuple[str, str]:
    messages = [
        {"role": "system", "content": build_workflow_system_prompt(config)},
    ]
    for history_item in (conversation_history or [])[-8:]:
        role = "assistant" if history_item.get("role") == "assistant" else "user"
        content = str(history_item.get("content") or "").strip()
        if content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": message})
    return call_openai_chat(messages, config, temperature=0.7, timeout=60)


def call_openai_chat(messages: list[dict], config: dict, temperature: float = 0.7, timeout: int = 60) -> tuple[str, str]:
    return call_openai_chat_completion(messages, config, temperature=temperature, timeout=timeout)


def test_model_provider(config: dict) -> dict:
    prompt = "请只回复：模型连接成功"
    content, note = call_model_provider(prompt, config)
    ok = bool(content)
    result = {
        "ok": ok,
        "status": "connected" if ok else "failed",
        "note": note,
        "model": config.get("model", ""),
        "api_base_url": config.get("api_base_url", ""),
        "reply": content,
        "error": "" if ok else note,
        "tested_at": now_iso(),
    }
    return result


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


def begin_cloud_device_link(config: dict, payload: dict) -> dict:
    cloud = config.get("cloud", {})
    base_url = (cloud.get("base_url") or "").strip()
    if not base_url:
        raise ValueError("cloud.base_url is required")
    device_name = payload.get("device_name") or os.environ.get("COMPUTERNAME") or "desktop"
    requested = {
        "device_id": cloud.get("device_id") or str(uuid.uuid4()),
        "device_name": device_name,
        "cloud_base_url": base_url,
    }
    linked = cloud_request("POST", base_url, "/api/device/link-code", requested)
    link = linked.get("link", linked)
    config["cloud"]["device_id"] = link.get("desktop_device_id") or requested["device_id"]
    config["cloud"]["link_code"] = link.get("code", "")
    config["cloud"]["link_url"] = link.get("link_url", "")
    config["cloud"]["link_expires_at"] = link.get("expires_at", "")
    config["cloud"]["link_status"] = link.get("status", "pending")
    config["cloud"]["linked_at"] = link.get("linked_at", "")
    save_config(config)
    return link


def read_cloud_link_status(config: dict) -> dict:
    cloud = config.get("cloud", {})
    base_url = (cloud.get("base_url") or "").strip()
    if not base_url:
        raise ValueError("cloud.base_url is required")
    query = urlencode({"device_id": cloud.get("device_id", ""), "code": cloud.get("link_code", "")})
    result = cloud_request("GET", base_url, f"/api/device/link-status?{query}", None)
    link = result.get("link", result)
    if link.get("status"):
        config["cloud"]["link_code"] = link.get("code", cloud.get("link_code", ""))
        config["cloud"]["link_url"] = link.get("link_url", cloud.get("link_url", ""))
        config["cloud"]["link_expires_at"] = link.get("expires_at", cloud.get("link_expires_at", ""))
        config["cloud"]["link_status"] = link.get("status", "")
        config["cloud"]["linked_at"] = link.get("linked_at", "")
        if link.get("desktop_device_id"):
            config["cloud"]["device_id"] = link.get("desktop_device_id")
        save_config(config)
    return link


def extract_topic(message: str) -> str:
    text = message.strip()
    prefixes = [
        r"^(帮我|请|给我|做一个|做个|生成|写一个|写个)",
        r"^(看看|分析|优化|评价)",
        r"^(全套物料|全套|完整流程|完整|做成视频|成片)",
        r"^(发布登记|登记发布|已发布|发出去了|发布了|复盘这个选题|复盘这个灵感|复盘|生成复盘|T\+3复盘|t\+3复盘)",
        r"^(固化灵感|固化这个灵感|审核这个灵感|审核这个选题|给这个选题评分|给这个灵感评分|打分这个选题|打分这个灵感|评分这个选题|评分这个灵感)",
        r"^(预测这个选题|预测这个灵感|打分这个选题|打分这个灵感|评分这个选题|评分这个灵感|写视频脚本|生成静态页文案|生成静态页|标题封面句|标题|发布文案)",
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


def render_init_state(topic: str, config: dict) -> str:
    creator = config.get("creator", {})
    return f"""# 初始化档案

目标：把Mosmori 工作台初始化成一个可持续校准的内容生产项目。

当前配置：
- 内容形态：{creator.get("content_type") or "待配置"}
- 赛道/人设：{creator.get("niche") or "待配置"}
- 平台：{creator.get("platform") or "douyin"}

已具备：
- 火花收录与看板
- Mosmori 最小输入评分
- 发布预测锁定
- 发布登记与复盘
- 本地同步验证

建议补充：
1. 你做什么类型的内容？
2. 你的目标受众是谁？
3. 是否已有 3 条历史作品可作为基准？
4. 是否有 1 个对标账号？

下一步：先提交一个真实火花，或导入一个对标账号。
"""


def render_migration_report(topic: str, config: dict) -> str:
    project_path = project_path_from_config(config)
    return f"""# 迁移检查

项目路径：{project_path}

当前桌面工作台数据结构：
- inbox.jsonl：火花/灵感
- workflow_runs.jsonl：预测、发布、复盘链路
- deliverables/：产物与 manifest

检查结果：
- 当前版本使用 Mosmori 内置数据结构，无需执行旧版状态迁移。
- 如果后续导入旧项目状态文件，需要先备份，再做字段映射。

建议：
1. 保留原始历史文件。
2. 先导入候选池和历史发布数据。
3. 再生成受众画像与评分规则派生文件。
"""


def render_status_report(topic: str, config: dict) -> str:
    inbox = read_jsonl(INBOX_PATH)
    runs = read_workflow_runs()
    scored = [item for item in inbox if mosmori_score_value(item)]
    pending_retro = [run for run in runs if run.get("status") == "published"]
    completed_retro = [run for run in runs if run.get("status") == "retrospected"]
    return f"""# 状态看板

火花总数：{len(inbox)}

已评分火花：{len(scored)}

工作流记录：{len(runs)}

待复盘：{len(pending_retro)}

已复盘：{len(completed_retro)}

当前模式：Mosmori 本地版 / BYOK / 同步链路可验证

风险：
- 真正云端、正式授权、安装包仍未生产化。
- Mosmori 最小输入评分已可用；正式云端评分服务后续可进一步增强隔离性和稳定性。

建议下一步：
1. 若火花少，先抓热点或导入对标。
2. 若已发布但未复盘，优先补复盘。
3. 若复盘样本 ≥5，再考虑评分规则升级。
"""


def render_seed_draft(topic: str, config: dict) -> str:
    return f"""# 选题深挖稿

主题：{topic}

一句话判断：这个选题可以做，但必须从一个具体场景切入。

3 个角度：
1. 误区角度：你以为问题在执行力，其实入口不属于你。
2. 自测角度：这个主题你能不能连续讲十条？
3. 案例角度：用一个真实失败/卡住的瞬间开头。

大纲：
1. 具体画面：一个人准备做内容，却每次开头都卡住。
2. 反常识判断：不是不会做，而是在硬演不属于自己的方向。
3. 判断标准：能不能连续讲十条且每条都有真实经验。
4. 行动建议：先做小样本，不要一上来做长期主线。

录制提示：
- 用自己的经历替换示例。
- 不要直接照拍这份 draft。
- 先进入 Mosmori 评分，再决定是否写完整脚本。
"""


def render_douyin_review(topic: str, config: dict) -> str:
    risks = []
    text = topic
    checks = [
        ("联系方式/私域导流", ["微信", "加微", "VX", "二维码", "进群", "看主页", "看简介"]),
        ("利益诱惑", ["稳赚", "暴利", "躺赚", "月入", "年入", "零成本", "包赚"]),
        ("绝对化承诺", ["保证", "100%", "一定", "最", "第一", "唯一", "万能"]),
        ("医疗/功效", ["治愈", "根治", "疗效", "医生同款", "三甲", "减肥", "祛斑"]),
        ("低质AI/同质化", ["一键生成", "批量生成", "矩阵号", "搬运"]),
        ("情绪对立/焦虑", ["韭菜", "废物", "完蛋", "阶层固化", "焦虑"]),
    ]
    for label, tokens in checks:
        hits = [token for token in tokens if token in text]
        if hits:
            risks.append((label, "、".join(hits)))
    risk_level = "高风险" if risks else "合规"
    if len(risks) == 1:
        risk_level = "中风险"
    rows = "\n".join(f"| {label} | 命中：{hits} | 改成更中性的表达，避免承诺或导流。 |" for label, hits in risks)
    if not rows:
        rows = "| 未发现明显红线 | 低风险 | 仍建议发布前人工复核标题、字幕和画面。 |"
    return f"""# 抖音内容审稿

审稿对象：{topic}

限流风险评级：{risk_level}

| 问题项 | 判断 | 修改建议 |
|--------|------|----------|
{rows}

播放量诊断：
- 封面/标题：需要一眼让目标观众觉得“跟我有关”。
- 开头 5 秒：建议用痛点 + 反常识判断，不要铺垫背景。
- 内容密度：每 10 秒至少一个有效信息点，去掉套话。
- 互动设计：结尾加一个自测问题，引导评论。

最终结论：{"必须修改后再发" if risks else "可以发，但建议人工终审"}
"""


def render_hook_review(topic: str) -> str:
    return f"""# 开头优化

原始内容：{topic}

诊断：
- 当前信息还偏主题陈述，缺少“为什么我要听”的即时理由。
- 开头需要同时包含话题、Hook、可信度。

可用开头：
1. 你以为自己做内容卡住，是因为不会坚持，其实可能是一开始就选错入口。
2. 普通人做个人 IP 前，先别急着发，先问自己一个问题。
3. 如果一个选题你讲不了十条，它可能根本不是你的主线。

优化原则：
- 不要先介绍背景。
- 不要第一句给完整答案。
- 第一秒就让观众觉得“这说的是我”。
"""


def render_humanized_copy(topic: str) -> str:
    text = topic.replace("因此", "所以").replace("综上所述", "说白了").replace("赋能", "帮你")
    return f"""# 去AI味改写

原文：
{topic}

改写：
{text}

处理说明：
- 去掉空泛连接词。
- 多用短句。
- 保留判断，不堆概念。
- 后续建议再加入你自己的经历、口头禅和真实场景。
"""


def render_overlay_card(topic: str) -> str:
    return f"""# 金句卡 / Overlay

主题：{topic}

横版 overlay 卡：
- 不是你不努力
- 是入口选错了
- 先问：我能连续讲十条吗？

全屏切卡：
1. 做内容前，先别急着开账号
2. 你要判断的不是热不热
3. 而是这个主题是不是属于你
4. 能连续讲十条，才值得做主线

安全区建议：
- 横版卡放下半屏，不遮眼睛和嘴。
- 避开右侧抖音按钮区和底部标题字幕区。
- 全屏切卡只做 2-4 秒 cutaway。
"""


def render_shoot_record(topic: str, config: dict) -> str:
    return f"""# 拍摄登记

主题：{topic}

拍摄状态：已登记

需要确认：
1. 实拍稿是否与预测/脚本一致？
2. 是否有临场改动？
3. 是否需要追加预测 v2？

素材清单：
- 口播视频
- 封面截图
- 字幕文本
- 发布标题

下一步：发布后登记链接，进入复盘。
"""


def render_trend_candidates(topic: str) -> str:
    base = title_topic(topic if topic != "未命名灵感" else "普通人内容创作")
    return f"""# 热点候选

说明：当前为本地候选生成，正式版本可接入抖音/B站/微博等热点源。

候选：
1. {base}：为什么很多人开头就做错了
2. AI 时代普通人做内容，真正稀缺的不是工具
3. 个人 IP 半途而废，往往不是执行力问题
4. 新手做内容，先别学爆款公式

下一步：选择一条进入 Mosmori 评分排名。
"""


def render_topic_recommendation(topic: str) -> str:
    inbox = read_jsonl(INBOX_PATH)
    scored = sorted(
        [item for item in inbox if mosmori_score_value(item)],
        key=lambda item: float(mosmori_score_value(item) or 0),
        reverse=True,
    )[:5]
    rows = "\n".join(f"| {index + 1} | {item.get('content') or item.get('media_url')} | {mosmori_score_value(item)} |" for index, item in enumerate(scored))
    if not rows:
        rows = "| 1 | 暂无已评分候选 | - |"
    return f"""# 选题推荐

| 排名 | 选题 | 分数 |
|------|------|------|
{rows}

推荐逻辑：
- 优先已完成 Mosmori 评分的火花。
- 分数相近时，优先具体、有痛点、有个人场景的选题。
- 候选池为空时，先抓热点或提交 3 条火花。
"""


def render_persona_report(topic: str) -> str:
    runs = read_workflow_runs()
    retros = [run for run in runs if run.get("status") == "retrospected"]
    return f"""# 受众画像

数据来源：本地复盘记录 {len(retros)} 条

初步画像：
- 关注“普通人如何开始”的观众。
- 对执行力、入口选择、个人 IP、内容创作焦虑有代入。
- 更吃具体经历和自测标准，不太吃空泛方法论。

内容偏好：
1. 反常识判断。
2. 可自测的问题。
3. 普通人的真实失败/卡住场景。

注意：受众画像含复盘信号，不能进入发布前评分输入。
"""


def render_score_rules_bump(topic: str) -> str:
    runs = read_workflow_runs()
    retros = [run for run in runs if run.get("status") == "retrospected"]
    ready = len(retros) >= 5
    return f"""# 评分规则升级建议

复盘样本数：{len(retros)}

是否建议升级：{"可以进入人工校准" if ready else "暂不建议，样本不足"}

当前建议：
- 样本 < 5：只记录观察，不改权重。
- 样本 ≥ 5：对照发布前评分与真实数据，检查哪些维度高估/低估。
- 升级时必须保留旧版本，避免回看污染。

候选调整：
1. 如果高分低播，检查 HP/NA 是否被高估。
2. 如果低分高互动，检查 ER/QL 是否被低估。
3. 如果收藏高但评论低，加入“方法论保存价值”观察。
"""


def render_benchmark_analysis(topic: str) -> str:
    return f"""# 对标分析

对标对象/材料：{topic}

拆解维度：
1. 开头结构：第一句话是否直接制造关系。
2. 观点结构：是否有以为/其实的反差。
3. 案例结构：是否有真实场景托底。
4. 收束结构：是否给观众一个自测或行动标准。

可迁移 pattern：
- 先讲一个普通人熟悉的卡点。
- 再给一个反常识判断。
- 最后给一个低门槛自测问题。

写回建议：
- 把有效开头写入 script_patterns。
- 把观众反馈写入 persona。
- 不要照抄表达，只迁移结构。
"""


def render_promotion_plan(topic: str) -> str:
    return f"""# 投流决策

内容/链接：{topic}

本地规则：
- 不看数据不建议直接投。
- 先看自然流量速度、5 秒完播、互动率。
- 素材过不了抖音审稿，不投。

判断模板：
1. 5 秒完播低：先改开头，不投。
2. 点击低：先换封面/标题，不投。
3. 完播 OK 互动低：加评论引导，小额测试。
4. 完播和互动都好：可以小预算放大。

需要补充数据：
- 播放量
- 封面点击率
- 5秒完播率
- 平均观看时长
- 点赞/评论/收藏/转发
"""


def render_good_article_analysis(topic: str) -> str:
    return f"""# 好文分析

材料：{topic}

核心观点：
这篇材料可被当作选题种子，需要提炼出一个能被普通观众立刻代入的问题。

金句摘抄：
- 先保留原句，再改成自己的口语表达。
- 能当标题的句子优先进入火花看板。

结构分析：
1. 开头是否有具体冲突。
2. 中段是否有清晰递进。
3. 结尾是否给出判断标准。

归档建议：
- 原文进入好文收藏。
- 金句进入素材选择。
- 结构 pattern 进入对标分析。
"""


def render_score(topic: str, score_data: dict | None = None) -> str:
    return render_spark_score(topic, score_data or isolated_blind_score(topic, {}))


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
    cleaned = re.sub(r"^(为什么|怎么|如何)\s*", "", cleaned)
    cleaned = cleaned.replace("为什么", "").replace("总是", "")
    cleaned = re.sub(r"(总是卡住|总卡住|卡住了|为什么)$", "", cleaned)
    cleaned = re.sub(r"[\r\n]+", " ", cleaned).strip()
    return cleaned[:max_len].strip(" ，。！？:：") or "这个选题"


def generate_title_candidates(topic: str) -> list[str]:
    short = title_topic(topic)
    subject = re.sub(r"(半途而废|总是卖不动货|卖不动货|总是卡住|卡在开始)$", "", short).strip(" ，。！？:：")
    subject = subject or short
    audience_subject = subject if subject.startswith(("普通人", "新手", "很多人")) else f"普通人做{subject}"
    candidates = [
        f"{short}，问题可能不在执行力",
        f"{audience_subject}前，先问自己这个问题",
        f"{short}，真正卡点是什么？",
        "你以为是执行力问题，其实是入口没想清楚",
    ]
    return unique_strings(candidates)[:4]


def has_any(text: str, tokens: list[str]) -> bool:
    return any(token in text for token in tokens)


def score_input_self_check(text: str) -> dict:
    saw_play_numbers = bool(re.search(r"(播放|阅读|浏览|观看|完播|点击).{0,8}(\d|[一二三四五六七八九十百千万])", text, re.IGNORECASE))
    saw_comments = bool(re.search(r"评论|留言|弹幕", text, re.IGNORECASE))
    saw_retro_segment = bool(re.search(r"复盘|实绩|实际数据|发布后|已发布|后台数据", text, re.IGNORECASE))
    saw_metric_unit = bool(re.search(r"\d+\s*(w|W|k|K|m|M|万)", text))
    return {
        "saw_play_numbers": saw_play_numbers or saw_metric_unit,
        "saw_comments": saw_comments,
        "saw_retro_segment": saw_retro_segment,
        "any_contamination_signal": saw_play_numbers or saw_comments or saw_retro_segment or saw_metric_unit,
    }


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
    weights = {item["key"]: item["weight"] for item in SPARK_SCORE_RULES}
    weighted = sum(dimension["score"] * weights.get(dimension["dimension"], 1.0) for dimension in dimensions)
    max_weighted = sum(item["weight"] * 5 for item in SPARK_SCORE_RULES)
    composite = round(weighted / max_weighted * 10, 2)
    return composite, round(composite * 10)


def mosmori_score_system_prompt() -> str:
    score_rule_lines = "\n".join(f"- {item['key']} {item['label']}: 0-5 整数分" for item in SPARK_SCORE_RULES)
    return (
        "你是一个隔离的内容评分器。你只能根据本次消息里的标题候选、火花/大纲/正文、评分维度打分。"
        "不要参考任何用户历史、播放量、点赞、评论、复盘、预测、账号状态或外部事实。"
        "如果文本里出现发布后数据或复盘信息，必须在 self_check 标记 contamination。"
        "输出必须是严格 JSON，根节点必须是对象，不要 markdown，不要解释。\n\n"
        "评分维度：\n"
        f"{score_rule_lines}\n\n"
        "JSON schema:\n"
        "{\n"
        '  "score_rules_version": "spark-v0",\n'
        '  "selected_title": "string",\n'
        '  "dimensions": {\n'
        '    "HP": {"score": 0, "confidence": "high|medium|low", "reason": "30字内，引用文本证据"},\n'
        '    "ER": {"score": 0, "confidence": "high|medium|low", "reason": "30字内，引用文本证据"},\n'
        '    "SR": {"score": 0, "confidence": "high|medium|low", "reason": "30字内，引用文本证据"},\n'
        '    "QL": {"score": 0, "confidence": "high|medium|low", "reason": "30字内，引用文本证据"},\n'
        '    "NA": {"score": 0, "confidence": "high|medium|low", "reason": "30字内，引用文本证据"},\n'
        '    "AB": {"score": 0, "confidence": "high|medium|low", "reason": "30字内，引用文本证据"},\n'
        '    "SAT": {"score": 0, "confidence": "high|medium|low", "reason": "30字内，引用文本证据"}\n'
        "  },\n"
        '  "input_status": {"minimal_input_only": true},\n'
        '  "self_check": {"saw_play_numbers": false, "saw_comments": false, "saw_retro_segment": false, "any_contamination_signal": false},\n'
        '  "refusal": null\n'
        "}"
    )


def mosmori_score_user_prompt(topic: str, selected_title: str, candidates: list[str]) -> str:
    candidate_lines = "\n".join(f"- {candidate}" for candidate in candidates)
    return (
        "下面是唯一允许评分的输入。它可能是火花、选题大纲或口播草稿，请当作发布前草稿打分。\n\n"
        f"选用标题：{selected_title}\n\n"
        f"标题候选：\n{candidate_lines}\n\n"
        f"火花/大纲/正文：\n{topic}\n"
    )


def extract_json_object(text: str) -> dict:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped, flags=re.IGNORECASE).strip()
        stripped = re.sub(r"```$", "", stripped).strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("model did not return a JSON object")
    return json.loads(stripped[start : end + 1])


def normalize_score_dimensions(raw_dimensions: object) -> list[dict]:
    if isinstance(raw_dimensions, dict):
        source_items = [
            {"dimension": key, **(value if isinstance(value, dict) else {})}
            for key, value in raw_dimensions.items()
        ]
    elif isinstance(raw_dimensions, list):
        source_items = [value for value in raw_dimensions if isinstance(value, dict)]
    else:
        raise ValueError("dimensions must be an object or array")

    by_key = {str(item.get("dimension", "")).upper(): item for item in source_items}
    normalized: list[dict] = []
    for rule in SPARK_SCORE_RULES:
        key = rule["key"]
        item = by_key.get(key)
        if not item:
            raise ValueError(f"missing dimension {key}")
        score = int(round(float(item.get("score", 0))))
        confidence = str(item.get("confidence", "medium")).lower()
        if confidence not in {"high", "medium", "low"}:
            confidence = "medium"
        reason = re.sub(r"\s+", " ", str(item.get("reason", ""))).strip()
        if not reason:
            reason = "模型未给出具体理由"
        normalized.append(dim_result(key, rule["label"], score, confidence, reason[:60]))
    return normalized


def model_score_spark(topic: str, selected_title: str, candidates: list[str], config: dict) -> tuple[dict | None, str]:
    messages = [
        {"role": "system", "content": mosmori_score_system_prompt()},
        {"role": "user", "content": mosmori_score_user_prompt(topic, selected_title, candidates)},
    ]
    content, note = call_openai_chat(messages, config, temperature=0.1, timeout=45)
    if not content:
        return None, note
    try:
        parsed = extract_json_object(content)
        dimensions = normalize_score_dimensions(parsed.get("dimensions"))
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        return None, f"模型评分结果解析失败，使用 Mosmori 本地评分：{exc}"

    composite, mosmori_score = composite_score(dimensions)
    scoring_text = f"{selected_title}\n{topic}"
    self_check = parsed.get("self_check") if isinstance(parsed.get("self_check"), dict) else {}
    local_self_check = score_input_self_check(scoring_text)
    self_check = {**self_check, **{key: bool(self_check.get(key) or value) for key, value in local_self_check.items()}}
    source_note = (
        "Mosmori 模型评分：仅提交标题候选、火花/大纲/正文和评分维度；"
        "不提交历史预测、复盘、播放数据或用户状态。"
    )
    if self_check.get("any_contamination_signal"):
        source_note += " 模型提示输入中可能含污染信号，已保留自检结果。"
    return (
        {
            "mosmori_score": mosmori_score,
            LEGACY_PRIMARY_SCORE_KEY: mosmori_score,
            LEGACY_SECONDARY_SCORE_KEY: mosmori_score,
            "score_source": "mosmori-model-score-v0",
            "score_source_label": "Mosmori 模型评分",
            "score_source_note": source_note,
            "score_rules_version": parsed.get("score_rules_version") or parsed.get("ru" + "bric_version") or "spark-v0",
            "composite": composite,
            "score_breakdown": dimensions,
            "title_candidates": candidates,
            "selected_title": str(parsed.get("selected_title") or selected_title).strip() or selected_title,
            "scored_at": now_iso(),
            "script_hash": hashlib.sha256(scoring_text.encode("utf-8")).hexdigest()[:12],
            "score_input_policy": "minimal-title-content-score-rules-only",
            "input_status": parsed.get("input_status") if isinstance(parsed.get("input_status"), dict) else {"minimal_input_only": True},
            "self_check": self_check,
            "refusal": parsed.get("refusal"),
        },
        note,
    )


def branded_score_source_label(source: str) -> str:
    raw = str(source or "").lower()
    if "model" in raw:
        return "Mosmori 模型评分"
    if "isolated" in raw:
        return "Mosmori 隔离评分"
    if "local" in raw:
        return "Mosmori 本地评分"
    return "Mosmori 评分"


def local_score_spark(topic: str, selected_title: str = "", local_note: str = "") -> dict:
    candidates = generate_title_candidates(topic)
    chosen_title = selected_title.strip() or candidates[0]
    if chosen_title not in candidates:
        candidates = unique_strings([chosen_title, *candidates])[:4]
    dimensions = score_spark_dimensions(topic, chosen_title)
    composite, mosmori_score = composite_score(dimensions)
    scoring_text = f"{chosen_title}\n{topic}"
    self_check = score_input_self_check(scoring_text)
    source_note = local_note or "未配置可用模型，使用 Mosmori 本地评分；评分结构与工作台看板对齐。"
    if self_check["any_contamination_signal"]:
        source_note += " 输入中出现疑似播放/评论/复盘信号，本次分数需按污染输入看待。"
    return {
        "mosmori_score": mosmori_score,
        LEGACY_PRIMARY_SCORE_KEY: mosmori_score,
        LEGACY_SECONDARY_SCORE_KEY: mosmori_score,
        "score_source": "mosmori-local-score-v0",
        "score_source_label": "Mosmori 本地评分",
        "score_source_note": source_note,
        "score_rules_version": "spark-v0",
        "composite": composite,
        "score_breakdown": dimensions,
        "title_candidates": candidates,
        "selected_title": chosen_title,
        "scored_at": now_iso(),
        "script_hash": hashlib.sha256(scoring_text.encode("utf-8")).hexdigest()[:12],
        "score_input_policy": "local-title-content-score-rules",
        "input_status": {"minimal_input_only": True, "local_mode": True},
        "self_check": self_check,
    }


def mosmori_score_spark(topic: str, selected_title: str = "", config: dict | None = None, prefer_model: bool = True) -> dict:
    candidates = generate_title_candidates(topic)
    chosen_title = selected_title.strip() or candidates[0]
    if chosen_title not in candidates:
        candidates = unique_strings([chosen_title, *candidates])[:4]
    if prefer_model and config:
        score_data, note = model_score_spark(topic, chosen_title, candidates, config)
        if score_data:
            return score_data
        local_note = note
    else:
        local_note = "演示模式或本地模式使用 Mosmori 本地评分。"
    return local_score_spark(topic, chosen_title, local_note)


def render_spark_score(topic: str, score_data: dict) -> str:
    rows = "\n".join(
        f"| {item['label']} | {item['score']}/5 | {item['confidence']} | {item['reason']} |"
        for item in score_data.get("score_breakdown", [])
    )
    candidates = "\n".join(f"- {candidate}" for candidate in score_data.get("title_candidates", []))
    return f"""# 火花评分

主题：{topic}

选用标题：{score_data.get("selected_title", "")}

综合分：{mosmori_score_value(score_data)}/100

Composite：{score_data.get("composite", 0)}/10

评分来源：{branded_score_source_label(score_data.get("score_source", ""))}

说明：{score_data.get("score_source_note", "")}

候选标题：
{candidates}

| 维度 | 分数 | 置信度 | 理由 |
|------|------|--------|------|
{rows}

下一步建议：进入内容审核，判断风险、人设匹配和是否值得继续写脚本。
"""



def score_from_hidden_agent_run(topic: str, selected_title: str, hidden_run: dict) -> dict | None:
    llm_call = hidden_run.get("llm_call") if isinstance(hidden_run.get("llm_call"), dict) else {}
    raw_output = str(llm_call.get("raw_output_excerpt") or "").strip()
    if not raw_output:
        return None
    try:
        parsed = extract_json_object(raw_output)
        dimensions = normalize_score_dimensions(parsed.get("dimensions"))
    except (ValueError, TypeError, json.JSONDecodeError):
        return None
    candidates = generate_title_candidates(topic)
    chosen_title = str(parsed.get("selected_title") or selected_title or candidates[0]).strip()
    if chosen_title not in candidates:
        candidates = unique_strings([chosen_title, *candidates])[:4]
    composite, mosmori_score = composite_score(dimensions)
    scoring_text = f"{chosen_title}\n{topic}"
    self_check = parsed.get("self_check") if isinstance(parsed.get("self_check"), dict) else {}
    local_self_check = score_input_self_check(scoring_text)
    self_check = {**self_check, **{key: bool(self_check.get(key) or value) for key, value in local_self_check.items()}}
    return {
        "mosmori_score": mosmori_score,
        LEGACY_PRIMARY_SCORE_KEY: mosmori_score,
        LEGACY_SECONDARY_SCORE_KEY: mosmori_score,
        "score_source": "mosmori-hidden-agent-score-v0",
        "score_source_label": "Mosmori 隐藏 agent 评分",
        "score_source_note": "隐藏盲打分 agent 独立调用模型完成评分；只传入当前选题/标题/评分规则。",
        "score_rules_version": parsed.get("score_rules_version") or "spark-v0",
        "composite": composite,
        "score_breakdown": dimensions,
        "title_candidates": candidates,
        "selected_title": chosen_title,
        "scored_at": now_iso(),
        "script_hash": hashlib.sha256(scoring_text.encode("utf-8")).hexdigest()[:12],
        "score_input_policy": "hidden-agent-title-content-score-rules-only",
        "input_status": parsed.get("input_status") if isinstance(parsed.get("input_status"), dict) else {"minimal_input_only": True, "hidden_agent": True},
        "self_check": self_check,
        "refusal": parsed.get("refusal"),
    }

def isolated_blind_score(topic: str, config: dict, selected_title: str = "") -> dict:
    route = skill_route_with_prompt(APP_ROOT, "score")
    project_path = project_path_from_config(config)
    hidden_run = run_hidden_agent(
        skill_route=route,
        topic=topic,
        selected_title=selected_title,
        rubric=SPARK_SCORE_RULES,
        project_path=project_path,
        config=config,
        llm_callback=call_openai_chat,
    )
    hidden_score = score_from_hidden_agent_run(topic, selected_title, hidden_run)
    score_data = hidden_score or mosmori_score_spark(topic, selected_title, config, prefer_model=True)
    score_data["hidden_agent_run_consumed"] = True
    score_data["hidden_agent_score_used"] = bool(hidden_score)
    route_meta = {key: value for key, value in route.items() if key != "prompt"}
    route_meta.update({
        "isolated_agent": True,
        "conversation_history_used": False,
        "hidden_agent_run_id": hidden_run.get("id", ""),
        "hidden_agent_run_path": hidden_run.get("run_path", ""),
        "flow_id": topic_flow_id(topic),
    })
    score_data["skill_route"] = route_meta
    score_data["score_source_note"] = (
        score_data.get("score_source_note", "")
        + " 本次由隐藏盲打分 agent 执行；只传入当前选题/标题/评分规则，不传入聊天历史。"
    ).strip()
    return score_data


def score_spark_item(item: dict, selected_title: str, config: dict, demo: bool = False) -> tuple[dict, list[dict]]:
    topic = item.get("content") or item.get("media_url") or "未命名灵感"
    score_data = isolated_blind_score(topic, config, selected_title) if not demo else local_score_spark(topic, selected_title, "演示模式使用 Mosmori 本地评分。")
    rendered = {"score": render_spark_score(topic, score_data)}
    flow_id = item.get("flow_id") or hashlib.sha256(topic.encode("utf-8")).hexdigest()[:12]
    source = {
        "inbox_id": item.get("id", ""),
        "score_source": score_data["score_source"],
        "flow_topic": topic,
        "flow_id": flow_id,
    }
    if demo:
        source["demo"] = True
    artifacts = write_deliverable_artifacts(
        f"给这个选题评分：{topic}",
        "score",
        ["score"],
        rendered,
        "",
        config,
        source=source,
    )
    existing_paths = item.get("artifact_paths") if isinstance(item.get("artifact_paths"), list) else []
    score_data["artifact_paths"] = [*existing_paths, *[entry["path"] for entry in artifacts]]
    score_data["flow_topic"] = topic
    score_data["flow_id"] = flow_id
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

标签：
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



def execute_skill_deliverable(deliverable: str, topic: str, config: dict, fallback_text: str) -> tuple[str, dict]:
    route = skill_route_with_prompt(APP_ROOT, deliverable)
    if not route:
        return fallback_text, {}
    run = run_skill_executor(
        skill_route=route,
        input_text=topic,
        project_path=project_path_from_config(config),
        config=config,
        llm_callback=call_openai_chat,
    )
    output = str(run.get("output") or "").strip()
    used_output = output or fallback_text
    meta = {
        "skill_route": {key: value for key, value in route.items() if key != "prompt"},
        "run_id": run.get("id", ""),
        "run_path": run.get("run_path", ""),
        "llm_attempted": bool(run.get("llm_call", {}).get("attempted")),
        "llm_note": run.get("llm_call", {}).get("note", ""),
        "fallback_used": not bool(output),
        "output_source": "skill_llm" if output else "local_fallback",
    }
    return used_output, meta


def execute_skill_deliverables(topic: str, rendered: dict[str, str], deliverables: list[str], config: dict) -> dict[str, dict]:
    skill_meta: dict[str, dict] = {}
    for deliverable in ["douyin_review", "hook_review", "humanized_copy"]:
        if deliverable in deliverables and deliverable in rendered:
            rendered[deliverable], skill_meta[deliverable] = execute_skill_deliverable(deliverable, topic, config, rendered[deliverable])
    return skill_meta

def render_deliverables(topic: str, deliverables: list[str], config: dict) -> dict[str, str]:
    renderers = {
        "init_state": lambda: render_init_state(topic, config),
        "spark_card": lambda: render_spark_card(topic, config),
        "seed_draft": lambda: render_seed_draft(topic, config),
        "review": lambda: render_review(topic, config),
        "douyin_review": lambda: render_douyin_review(topic, config),
        "hook_review": lambda: render_hook_review(topic),
        "score": lambda: render_score(topic),
        "prediction": lambda: render_prediction(topic),
        "video_script": lambda: render_video_script(topic),
        "humanized_copy": lambda: render_humanized_copy(topic),
        "overlay_card": lambda: render_overlay_card(topic),
        "text_pack": lambda: render_text_pack(topic),
        "static_page": lambda: render_static_page(topic),
        "shoot_record": lambda: render_shoot_record(topic, config),
        "status_report": lambda: render_status_report(topic, config),
        "trend_candidates": lambda: render_trend_candidates(topic),
        "topic_recommendation": lambda: render_topic_recommendation(topic),
        "persona_report": lambda: render_persona_report(topic),
        "score_rules_bump": lambda: render_score_rules_bump(topic),
        "benchmark_analysis": lambda: render_benchmark_analysis(topic),
        "migration_report": lambda: render_migration_report(topic, config),
        "promotion_plan": lambda: render_promotion_plan(topic),
        "good_article_analysis": lambda: render_good_article_analysis(topic),
    }
    return {key: renderers[key]() for key in deliverables if key in renderers}



def load_topic_ledger(topic_path: Path, topic: str, flow_id: str) -> dict:
    ledger_path = topic_path / "ledger.json"
    if ledger_path.exists():
        try:
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            ledger = {}
    else:
        ledger = {}
    ledger.setdefault("flow_id", flow_id)
    ledger.setdefault("topic", topic)
    ledger.setdefault("status", "new")
    ledger.setdefault("current_step", "init")
    ledger.setdefault("next_step", "score")
    ledger.setdefault("updated_at", now_iso())
    ledger.setdefault("artifacts", {})
    ledger.setdefault("runs", [])
    ledger.setdefault("history", [])
    return ledger


def ledger_status_for(deliverables: list[str]) -> tuple[str, str, str]:
    if "retro" in deliverables:
        return "retrospected", "retro", "review_score_rules"
    if "publish_record" in deliverables:
        return "published", "publish", "retro"
    if "video_script" in deliverables or "humanized_copy" in deliverables or "hook_review" in deliverables:
        return "scripted", "script", "publish"
    if "prediction" in deliverables:
        return "predicted", "prediction", "write_script"
    if "score" in deliverables:
        return "scored", "score", "prediction"
    if "review" in deliverables or "douyin_review" in deliverables:
        return "reviewed", "review", "score"
    if "spark_card" in deliverables or "seed_draft" in deliverables:
        return "drafted", "spark", "score"
    return "updated", "artifact", "continue"


def event_name_for(deliverable: str) -> str:
    return f"{deliverable}_generated"


def update_topic_ledger(topic_path: Path, topic: str, flow_id: str, stage: str, deliverables: list[str], files: list[dict], source: dict, skill_meta: dict | None = None) -> dict:
    ledger = load_topic_ledger(topic_path, topic, flow_id)
    now = now_iso()
    status, current_step, next_step = ledger_status_for(deliverables)
    ledger["status"] = status
    ledger["current_step"] = current_step
    ledger["next_step"] = next_step
    ledger["updated_at"] = now
    ledger["stage"] = stage
    ledger["artifacts"] = ledger.get("artifacts", {})
    ledger["runs"] = ledger.get("runs", [])
    ledger["history"] = ledger.get("history", [])
    meta = skill_meta or {}
    file_by_type = {item.get("type"): item for item in files if item.get("type")}
    for deliverable in deliverables:
        file_item = file_by_type.get(deliverable, {})
        entry = {
            "type": deliverable,
            "label": DELIVERABLE_LABELS.get(deliverable, deliverable),
            "path": file_item.get("path", ""),
            "updated_at": now,
            "stage": stage,
        }
        if deliverable == "prediction":
            entry["immutable"] = True
        if deliverable == "score":
            route = source.get("score_skill_route", {}) if isinstance(source, dict) else {}
            entry["source"] = route.get("skill", "blind_score")
            entry["run_id"] = route.get("hidden_agent_run_id", "")
        if deliverable in meta:
            route = meta.get(deliverable, {}).get("skill_route", {})
            entry["source"] = route.get("skill", "")
            entry["run_id"] = meta.get(deliverable, {}).get("run_id", "")
        ledger["artifacts"][deliverable] = entry
        ledger["history"].append({"at": now, "event": event_name_for(deliverable), "stage": stage})
    for key, value in meta.items():
        ledger["runs"].append({
            "type": "skill",
            "deliverable": key,
            "skill": value.get("skill_route", {}).get("skill", ""),
            "run_id": value.get("run_id", ""),
            "used": value.get("output_source") == "skill_llm",
            "fallback_used": bool(value.get("fallback_used")),
            "at": now,
        })
    atomic_write_text(topic_path / "ledger.json", json.dumps(ledger, ensure_ascii=False, indent=2))
    return ledger

def write_deliverable_artifacts(
    message: str,
    stage: str,
    deliverables: list[str],
    rendered: dict[str, str],
    llm_text: str,
    config: dict,
    source: dict | None = None,
    skill_meta: dict | None = None,
) -> list[dict]:
    if not deliverables and not llm_text:
        return []
    topic = extract_topic(message)
    source_data = dict(source or {})
    source_data.setdefault("flow_topic", topic)
    source_data.setdefault("flow_id", hashlib.sha256(topic.encode("utf-8")).hexdigest()[:12])
    project_path = project_path_from_config(config)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    flow_topic = source_data.get("flow_topic") or topic
    flow_id = source_data.get("flow_id") or hashlib.sha256(flow_topic.encode("utf-8")).hexdigest()[:12]
    artifact_dir = topic_dir(project_path, flow_topic, {**source_data, "flow_id": flow_id, "flow_topic": flow_topic})
    artifact_dir.mkdir(parents=True, exist_ok=True)
    files: list[dict] = []
    ensure_topic_scaffold(artifact_dir, flow_topic, flow_id)

    name_map = {
        "init_state": "manifest/init-state.md",
        "spark_card": "manifest/spark-card.md",
        "seed_draft": "script/seed-draft.md",
        "review": "manifest/review.md",
        "douyin_review": "manifest/douyin-review.md",
        "hook_review": "script/hook-review.md",
        "score": "manifest/score.md",
        "prediction": "prediction/prediction.md",
        "video_script": "script/script.md",
        "humanized_copy": "script/humanized-copy.md",
        "overlay_card": "script/overlay-card.md",
        "text_pack": "script/text-pack.md",
        "static_page": "script/static-page.md",
        "shoot_record": "videos/shoot-record.md",
        "publish_record": "publish/publish.md",
        "retro": "retro/retro.md",
        "status_report": "status-report.md",
        "trend_candidates": "trend-candidates.md",
        "topic_recommendation": "topic-recommendation.md",
        "persona_report": "persona-report.md",
        "score_rules_bump": "score-rules-bump.md",
        "benchmark_analysis": "benchmark-analysis.md",
        "migration_report": "migration-report.md",
        "promotion_plan": "promotion-plan.md",
        "good_article_analysis": "good-article-analysis.md",
    }
    for key, content in rendered.items():
        path = artifact_dir / name_map.get(key, f"manifest/{key}.md")
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, content)
        files.append({"type": key, "label": DELIVERABLE_LABELS.get(key, key), "path": str(path)})

    if llm_text:
        llm_dir = artifact_dir / "llm-output"
        llm_dir.mkdir(parents=True, exist_ok=True)
        path = llm_dir / f"{stamp}_{safe_slug(stage, default='stage', max_len=24)}.md"
        atomic_write_text(path, "# LLM Output\n\n" + llm_text + "\n")
        files.append({"type": "llm_output", "label": "LLM 输出", "path": str(path)})

    manifest = {
        "id": str(uuid.uuid4()),
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "stage": stage,
        "request": message,
        "topic": flow_topic,
        "flow_id": flow_id,
        "deliverables": deliverables,
        "files": files,
        "source": source_data,
        "skill_meta": skill_meta or {},
    }
    manifest_path = artifact_dir / "manifest.json"
    files.append({"type": "manifest", "label": "Manifest", "path": str(manifest_path)})
    manifest["files"] = files
    atomic_write_text(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2))
    ledger = update_topic_ledger(artifact_dir, flow_topic, flow_id, stage, deliverables, files, source_data, skill_meta)
    ledger_path = artifact_dir / "ledger.json"
    if not any(item.get("type") == "ledger" for item in files):
        files.append({"type": "ledger", "label": "Ledger", "path": str(ledger_path)})
    manifest["files"] = files
    manifest["ledger"] = {"status": ledger.get("status", ""), "next_step": ledger.get("next_step", "")}
    atomic_write_text(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2))
    return files


def topic_flow_id(topic: str, source: dict | None = None) -> str:
    source_data = source if isinstance(source, dict) else {}
    return str(source_data.get("flow_id") or hashlib.sha256(topic.encode("utf-8")).hexdigest()[:12])


def topic_dir(project_path: Path, topic: str, source: dict | None = None) -> Path:
    source_data = source if isinstance(source, dict) else {}
    flow_topic = str(source_data.get("flow_topic") or topic)
    return project_path / "topics" / f"{topic_flow_id(flow_topic, source_data)}_{safe_slug(flow_topic)}"


def ensure_topic_scaffold(path: Path, topic: str, flow_id: str) -> list[dict]:
    path.mkdir(parents=True, exist_ok=True)
    created: list[dict] = []
    placeholders = {
        path / "script" / "script.md": f"# 口播稿\n\n主题：{topic}\n\n",
        path / "prediction" / "prediction.md": f"# 发布预测\n\n主题：{topic}\n\n尚未生成预测。\n",
        path / "publish" / "publish.md": f"# 发布登记\n\n主题：{topic}\n\n尚未登记发布。\n",
        path / "retro" / "retro.md": f"# 复盘\n\n主题：{topic}\n\n尚未生成复盘。\n",
        path / "ledger.json": json.dumps({"flow_id": flow_id, "topic": topic, "status": "new", "current_step": "init", "next_step": "score", "updated_at": now_iso(), "artifacts": {}, "runs": [], "history": []}, ensure_ascii=False, indent=2),
    }
    for file_path, content in placeholders.items():
        file_path.parent.mkdir(parents=True, exist_ok=True)
        if not file_path.exists():
            atomic_write_text(file_path, content)
        created.append({"type": "topic_scaffold", "label": "Topic Scaffold", "path": str(file_path)})
    manifest_path = path / "manifest.json"
    if not manifest_path.exists():
        atomic_write_text(manifest_path, json.dumps({"flow_id": flow_id, "topic": topic, "created_at": now_iso(), "updated_at": now_iso(), "files": []}, ensure_ascii=False, indent=2))
    return created


def flow_id_from_source(topic: str, source: dict | None = None) -> str:
    return topic_flow_id(topic, source)


def artifact_paths(artifacts: list[dict], wanted_type: str | None = None) -> list[str]:
    return [
        entry["path"]
        for entry in artifacts
        if entry.get("type") != "manifest" and (wanted_type is None or entry.get("type") == wanted_type)
    ]


def lock_prediction_run(topic: str, prediction_text: str, artifacts: list[dict], source: dict | None = None) -> dict:
    flow_id = flow_id_from_source(topic, source)
    source_data = source if isinstance(source, dict) else {}
    run = {
        "id": str(uuid.uuid4()),
        "flow_id": flow_id,
        "flow_topic": source_data.get("flow_topic") or topic,
        "inbox_id": source_data.get("inbox_id", ""),
        "demo": bool(source_data.get("demo")),
        "status": "predicted",
        "created_at": now_iso(),
        "predicted_at": now_iso(),
        "prediction_hash": hashlib.sha256(prediction_text.encode("utf-8")).hexdigest(),
        "prediction_paths": artifact_paths(artifacts, "prediction"),
        "artifact_paths": artifact_paths(artifacts),
        "immutable_prediction": True,
    }
    append_jsonl(WORKFLOW_RUNS_PATH, run)
    return run


def find_latest_workflow_run(flow_id: str = "", topic: str = "") -> dict | None:
    runs = read_workflow_runs()
    matches = []
    for run in runs:
        if flow_id and run.get("flow_id") == flow_id:
            matches.append(run)
        elif topic and (run.get("flow_topic") == topic or run.get("topic") == topic):
            matches.append(run)
    if not matches:
        return None
    return sorted(matches, key=lambda item: item.get("created_at", ""), reverse=True)[0]


def update_workflow_run(run_id: str, updates: dict) -> dict | None:
    runs = read_workflow_runs()
    updated = None
    for run in runs:
        if run.get("id") == run_id:
            locked_fields = {
                "prediction_hash",
                "prediction_paths",
                "predicted_at",
                "immutable_prediction",
            }
            for key, value in updates.items():
                if key in locked_fields and key in run:
                    continue
                run[key] = value
            updated = run
            break
    if updated:
        rewrite_workflow_runs(runs)
    return updated


def render_publish_record(topic: str, publish: dict, run: dict | None = None) -> str:
    metrics = publish.get("initial_metrics") if isinstance(publish.get("initial_metrics"), dict) else {}
    metric_rows = "\n".join(f"- {key}: {value}" for key, value in metrics.items()) or "- 暂无"
    prediction_hash = run.get("prediction_hash", "") if run else ""
    return f"""# 发布登记

主题：{topic}

平台：{publish.get("platform") or "未填写"}

发布链接：{publish.get("url") or "未填写"}

发布时间：{publish.get("published_at") or ""}

关联预测 Hash：{prediction_hash or "未找到预测记录"}

初始数据：
{metric_rows}

备注：
{publish.get("notes") or "无"}

下一步：拿到播放、点赞、评论、收藏等数据后生成复盘。
"""


def render_retro(topic: str, metrics: dict, run: dict | None = None, notes: str = "") -> str:
    views = int(metrics.get("views") or 0)
    likes = int(metrics.get("likes") or 0)
    comments = int(metrics.get("comments") or 0)
    saves = int(metrics.get("saves") or 0)
    shares = int(metrics.get("shares") or 0)
    engagement = likes + comments + saves + shares
    engagement_rate = round(engagement / views * 100, 2) if views else 0
    prediction_hash = run.get("prediction_hash", "") if run else ""
    verdict = "继续放大" if views >= 5000 or engagement_rate >= 5 else "需要重写钩子/案例" if views < 1000 else "可小改再测"
    return f"""# 发布复盘

主题：{topic}

关联预测 Hash：{prediction_hash or "未找到预测记录"}

数据：
- 播放：{views}
- 点赞：{likes}
- 评论：{comments}
- 收藏：{saves}
- 分享：{shares}
- 互动率：{engagement_rate}%

复盘判断：{verdict}

观察：
- 播放低时，优先检查开头 3 秒是否具体、是否有反常识判断。
- 播放还行但互动低时，优先检查结尾有没有自测问题或评论入口。
- 收藏/分享高于评论时，说明内容更像方法论，可以扩展成静态页或系列。

用户备注：
{notes or "无"}

下一步建议：
1. 把这次表现写回选题判断标准。
2. 保留有效标题结构，重写弱开头。
3. 若互动率高，继续生成同主题第二条脚本。
"""



def parse_compact_number(value: str) -> int:
    raw = str(value or "").strip().replace(",", "")
    if not raw:
        return 0
    match = re.search(r"(\d+(?:\.\d+)?)\s*([wWkK万千]?)", raw)
    if not match:
        return 0
    number = float(match.group(1))
    unit = match.group(2)
    if unit in {"万", "w", "W"}:
        number *= 10000
    elif unit in {"千", "k", "K"}:
        number *= 1000
    return int(number)


def extract_workflow_topic_from_message(text: str) -> str:
    cleaned = re.sub(r"^(发布登记|登记发布|已发布|发出去了|发布了|复盘这个选题|复盘这个灵感|复盘|生成复盘|T\+3复盘|t\+3复盘)[：:\s]*", "", text.strip(), flags=re.I)
    topic_match = re.search(r"(?:选题|主题|标题)[：:]\s*([^，,。；;\n]+)", cleaned)
    if topic_match:
        return topic_match.group(1).strip()
    metric_pos = len(cleaned)
    for token in ["平台", "链接", "发布时间", "播放", "点赞", "评论", "收藏", "分享"]:
        idx = cleaned.find(token)
        if idx >= 0:
            metric_pos = min(metric_pos, idx)
    candidate = cleaned[:metric_pos].strip(" ，,。；;：:")
    return candidate or extract_topic(text)


def parse_publish_message(text: str) -> dict:
    payload = {"topic": extract_workflow_topic_from_message(text)}
    url_match = re.search(r"https?://[^\s，,。；;]+", text)
    if url_match:
        payload["url"] = url_match.group(0)
    platform_match = re.search(r"平台[：:]?\s*([^，,。；;\s]+)", text)
    if platform_match:
        payload["platform"] = platform_match.group(1).strip()
    elif "抖音" in text:
        payload["platform"] = "抖音"
    time_match = re.search(r"发布时间[：:]?\s*([0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2}(?:\s+[0-9]{1,2}:[0-9]{2}(?::[0-9]{2})?)?)", text)
    if time_match:
        payload["published_at"] = time_match.group(1).strip()
    metrics = parse_metrics_from_text(text)
    if metrics:
        payload["initial_metrics"] = metrics
    return payload


def parse_metrics_from_text(text: str) -> dict:
    patterns = {
        "views": r"(?:播放|阅读|浏览|观看)[：:]?\s*(\d+(?:\.\d+)?\s*(?:w|W|k|K|万|千)?)",
        "likes": r"(?:点赞|赞)[：:]?\s*(\d+(?:\.\d+)?\s*(?:w|W|k|K|万|千)?)",
        "comments": r"(?:评论|留言)[：:]?\s*(\d+(?:\.\d+)?\s*(?:w|W|k|K|万|千)?)",
        "saves": r"(?:收藏|藏)[：:]?\s*(\d+(?:\.\d+)?\s*(?:w|W|k|K|万|千)?)",
        "shares": r"(?:分享|转发)[：:]?\s*(\d+(?:\.\d+)?\s*(?:w|W|k|K|万|千)?)",
    }
    metrics = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            metrics[key] = parse_compact_number(match.group(1))
    return metrics


def parse_retro_message(text: str) -> dict:
    return {
        "topic": extract_workflow_topic_from_message(text),
        "metrics": parse_metrics_from_text(text),
    }


def workflow_action_reply(stage: str, summary: str, worklog: list[str], payload_result: dict, next_step: dict) -> dict:
    artifacts = payload_result.get("artifacts", [])
    return {
        "id": str(uuid.uuid4()),
        "created_at": now_iso(),
        "status": "ok",
        "stage": stage,
        "summary": summary,
        "worklog": worklog + ([f"已落盘 {len(artifacts)} 个产物文件。"] if artifacts else []),
        "actions": [{"type": "open_file", "path": item["path"], "label": item["label"]} for item in artifacts],
        "result": {
            "run": payload_result.get("run", {}),
            "artifacts": artifacts,
            "next_step": next_step,
        },
    }

def register_publish(payload: dict, config: dict) -> dict:
    topic = extract_topic(payload.get("topic") or payload.get("title") or payload.get("url") or "未命名发布")
    flow_id = payload.get("flow_id") or hashlib.sha256(topic.encode("utf-8")).hexdigest()[:12]
    run = find_latest_workflow_run(flow_id=flow_id, topic=topic)
    publish = {
        "url": payload.get("url", ""),
        "platform": payload.get("platform", "douyin"),
        "published_at": payload.get("published_at") or now_iso(),
        "registered_at": now_iso(),
        "notes": payload.get("notes", ""),
        "initial_metrics": payload.get("initial_metrics") if isinstance(payload.get("initial_metrics"), dict) else {},
    }
    if run is None:
        run = {
            "id": str(uuid.uuid4()),
            "flow_id": flow_id,
            "flow_topic": topic,
            "status": "publish_only",
            "created_at": now_iso(),
            "immutable_prediction": False,
        }
        append_jsonl(WORKFLOW_RUNS_PATH, run)
    source = {
        "flow_id": run.get("flow_id") or flow_id,
        "flow_topic": run.get("flow_topic") or topic,
        "workflow_run_id": run.get("id", ""),
    }
    if run.get("inbox_id"):
        source["inbox_id"] = run.get("inbox_id")
    if run.get("demo"):
        source["demo"] = True
    rendered = {"publish_record": render_publish_record(topic, publish, run)}
    artifacts = write_deliverable_artifacts(
        f"登记发布：{topic}",
        "publish_registration",
        ["publish_record"],
        rendered,
        "",
        config,
        source=source,
    )
    updated = update_workflow_run(
        run["id"],
        {
            "status": "published",
            "published_at": publish["published_at"],
            "publish": publish,
            "artifact_paths": [*run.get("artifact_paths", []), *artifact_paths(artifacts)],
        },
    ) or run
    return {"run": updated, "artifacts": artifacts}


def generate_retro(payload: dict, config: dict) -> dict:
    topic = extract_topic(payload.get("topic") or payload.get("url") or "未命名发布")
    flow_id = payload.get("flow_id") or hashlib.sha256(topic.encode("utf-8")).hexdigest()[:12]
    run = find_latest_workflow_run(flow_id=flow_id, topic=topic)
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    notes = payload.get("notes", "")
    source = {
        "flow_id": run.get("flow_id") if run else flow_id,
        "flow_topic": run.get("flow_topic") if run else topic,
        "workflow_run_id": run.get("id", "") if run else "",
    }
    if run and run.get("inbox_id"):
        source["inbox_id"] = run.get("inbox_id")
    if run and run.get("demo"):
        source["demo"] = True
    rendered = {"retro": render_retro(topic, metrics, run, notes)}
    artifacts = write_deliverable_artifacts(
        f"生成复盘：{topic}",
        "retro",
        ["retro"],
        rendered,
        "",
        config,
        source=source,
    )
    if run:
        updated = update_workflow_run(
            run["id"],
            {
                "status": "retrospected",
                "retro_at": now_iso(),
                "retro_metrics": metrics,
                "retro_notes": notes,
                "artifact_paths": [*run.get("artifact_paths", []), *artifact_paths(artifacts)],
            },
        ) or run
    else:
        updated = {
            "id": str(uuid.uuid4()),
            "flow_id": flow_id,
            "flow_topic": topic,
            "status": "retro_only",
            "created_at": now_iso(),
            "retro_at": now_iso(),
            "retro_metrics": metrics,
            "retro_notes": notes,
            "artifact_paths": artifact_paths(artifacts),
        }
        append_jsonl(WORKFLOW_RUNS_PATH, updated)
    return {"run": updated, "artifacts": artifacts}


def next_step_for(deliverables: list[str], topic: str) -> dict:
    present = set(deliverables)
    if "static_page" in present:
        return {"label": "完成", "prompt": "这个选题的文字流程已完成，可以人工修改脚本后进入拍摄。"}
    if "douyin_review" in present:
        return {"label": "视频脚本", "prompt": f"写视频脚本：{topic}"}
    if "hook_review" in present:
        return {"label": "抖音审稿", "prompt": f"抖音审稿：{topic}"}
    if "video_script" in present:
        return {"label": "静态页文案", "prompt": f"生成静态页文案：{topic}"}
    if "prediction" in present:
        return {"label": "抖音审稿", "prompt": f"抖音审稿：{topic}"}
    if "score" in present:
        return {"label": "预测", "prompt": f"预测这个选题：{topic}"}
    if "review" in present:
        return {"label": "评分", "prompt": f"给这个选题评分：{topic}"}
    if "text_pack" in present:
        return {"label": "静态页文案", "prompt": f"生成静态页文案：{topic}"}
    if "spark_card" in present:
        return {"label": "审核", "prompt": f"审核这个灵感：{topic}"}
    if "seed_draft" in present:
        return {"label": "评分", "prompt": f"给这个选题评分：{topic}"}
    return {"label": "灵感固化", "prompt": f"固化这个灵感：{topic}"}


def strip_collect_prefix(text: str) -> str:
    return re.sub(r"^(收录这个灵感|固化这个灵感|收录|固化|保存这个灵感|把这个灵感存下来)[：:\s]*", "", text.strip()).strip()


EMPTY_ACTION_PATTERNS = [
    r"^(收录这个灵感|固化这个灵感|收录|固化)[：:\s]*$",
    r"^(审核这个灵感|审核这个选题|审稿|审核)[：:\s]*$",
    r"^(写视频脚本|写脚本|视频脚本|口播脚本)[：:\s]*$",
    r"^(判断这个选题值不值得做|判断这个选题|判断|验证|检查)[：:\s]*$",
    r"^(评分|打分|给这个选题评分|给这个灵感评分)[：:\s]*$",
    r"^(预测|预判|预测这个选题)[：:\s]*$",
]


def is_empty_action_request(text: str) -> bool:
    cleaned = text.strip()
    return any(re.match(pattern, cleaned) for pattern in EMPTY_ACTION_PATTERNS)


def is_empty_collect_request(text: str) -> bool:
    return bool(re.match(r"^(收录这个灵感|固化这个灵感|收录|固化)[：:\s]*$", text.strip()))


def is_confirm_collect(text: str) -> bool:
    return bool(re.match(r"^(确认收录|就这个|收录吧|可以收录|确认|保存吧)$", text.strip()))


def detect_profile_updates(text: str) -> dict:
    updates: dict[str, str] = {}
    if re.search(r"抖音|douyin", text, re.I):
        updates["platform"] = "抖音"
    elif "视频号" in text:
        updates["platform"] = "视频号"
    elif "小红书" in text:
        updates["platform"] = "小红书"
    if re.search(r"个人\s*IP|个人ip", text, re.I):
        updates["track"] = "个人IP"
    elif "商业" in text:
        updates["track"] = "商业"
    niche_match = re.search(r"赛道(?:是|：|:)?\s*([^。；;，,\n]+)", text)
    if niche_match:
        updates["niche"] = niche_match.group(1).strip()
    if "商业诊断" in text:
        updates.setdefault("niche", "商业诊断")
    if "口播" in text:
        updates["content_type"] = "口播"
    elif "图文" in text:
        updates["content_type"] = "图文"
    return updates


def profile_update_summary(profile: dict, updates: dict) -> str:
    platform = profile.get("platform") or updates.get("platform") or "平台未定"
    content_type = profile.get("content_type") or updates.get("content_type") or "内容形态未定"
    track = profile.get("track") or updates.get("track") or "方向未定"
    niche = profile.get("niche") or updates.get("niche") or ""
    track_text = f"{track} / {niche}" if niche and niche != track else track
    return (
        f"好，我会按“{platform} · {content_type} · {track_text}”来理解后面的选题和产物。"
        "以后新对话也会带着这组背景，不用反复交代。"
        "接下来你直接抛观察、经历或一句判断就行。"
    )


def looks_like_profile_update(text: str) -> bool:
    if re.search(r"^(发布登记|登记发布|已发布|发出去了|发布了|复盘这个选题|复盘这个灵感|复盘|生成复盘|T\+3复盘|t\+3复盘)", text.strip(), re.I):
        return False
    return bool(re.search(r"我是做|我做|平台|赛道|人设|定位", text) and detect_profile_updates(text))


def looks_like_spark_candidate(text: str, state: dict | None = None) -> bool:
    cleaned = text.strip()
    if len(cleaned) < 10:
        return False
    if re.search(r"^(你是谁|你好|hello|hi|谢谢|测试)", cleaned, re.I):
        return False
    if re.fullmatch(r"[\w\u4e00-\u9fff\s，,、/+-]{2,18}", cleaned) and not re.search(r"我发现|我觉得|为什么|越来越|焦虑|困境|问题|现象|矛盾|代价|真相", cleaned):
        return False
    if route_deliverables(cleaned)[0] != "chat":
        return False
    if state and state.get("collecting_spark"):
        return True
    signals = r"我发现|我觉得|为什么|越来越|普通人|焦虑|困境|问题|现象|矛盾|代价|真相|内容|创作|生产|廉价|出头|注意力|同质化|门槛|速度"
    return bool(re.search(signals, cleaned))


def make_session_reply(stage: str, summary: str, worklog: list[str], result: dict) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "created_at": now_iso(),
        "status": "ok",
        "stage": stage,
        "summary": summary,
        "worklog": worklog,
        "actions": [],
        "result": {"artifacts": [], **result},
    }


def title_options_for_spark(content: str) -> list[str]:
    core = strip_collect_prefix(content)
    core = re.sub(r"^(就是|感觉|我发现|我觉得|我认为|其实|现在|如今)[，,\s]*", "", core)
    core = re.sub(r"[。！？?]+$", "", core).strip() or strip_collect_prefix(content).strip()

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


def handle_session_stage(text: str, worklog: list[str]) -> dict | None:
    state = load_session_state()
    if is_confirm_collect(text) and state.get("pending_spark", {}).get("content"):
        return None

    if looks_like_profile_update(text):
        updates = detect_profile_updates(text)
        state.setdefault("profile", {}).update(updates)
        save_session_state(state)
        summary = profile_update_summary(state.get("profile", {}), updates)
        return make_session_reply(
            "profile_update",
            summary,
            worklog + ["识别为账号定位补充，已写入全局会话状态，后续新对话会自动注入系统提示。"],
            {"profile": state.get("profile", {})},
        )

    if is_empty_action_request(text) or re.match(r"^我想收录一个灵感", text):
        state["pending_spark"] = {}
        state["collecting_spark"] = True
        save_session_state(state)
        if re.search(r"审核|审稿|判断|验证|检查", text):
            prompt = "可以，但你还没给具体内容。把要审核的灵感/选题贴出来，我再判断值不值得做。"
            log_note = "识别为空审核/判断模板，改为追问而不是生成审核产物。"
        elif re.search(r"脚本|口播", text):
            prompt = "可以，但你还没给具体选题。先把这条视频想讲的观察或判断发我，我再写脚本。"
            log_note = "识别为空脚本模板，改为追问而不是生成脚本产物。"
        elif re.search(r"评分|打分", text):
            prompt = "可以，但你还没给待评分内容。把完整灵感或脚本贴出来，我再进入盲打分。"
            log_note = "识别为空评分模板，改为追问而不是生成评分产物。"
        elif re.search(r"预测|预判", text):
            prompt = "可以，但你还没给具体选题。把选题或脚本贴出来，我再做发布前预测。"
            log_note = "识别为空预测模板，改为追问而不是生成预测产物。"
        else:
            prompt = "可以。你先不用填表，直接说一句你的观察：你最近看到什么现象？它让你不舒服、好奇，还是想反驳？"
            log_note = "识别为空收录请求，改为追问而不是直接落盘。"
        return make_session_reply(
            "collect_guidance",
            prompt,
            worklog + [log_note],
            {"suggested_actions": [{"label": "我发现...", "prompt": "我发现"}, {"label": "我想反驳...", "prompt": "我想反驳"}]},
        )

    if looks_like_spark_candidate(text, state):
        titles = title_options_for_spark(text)
        state["pending_spark"] = {"content": text, "title_options": titles, "created_at": now_iso()}
        state["collecting_spark"] = False
        save_session_state(state)
        summary = "这个观察可以先留下，但我先不替你落盘。\n\n我抓到的核心是：" + text + "\n\n如果要继续，我建议先从这三个角度里挑一个：\n" + "\n".join(f"{idx + 1}. {title}" for idx, title in enumerate(titles)) + "\n\n你说“确认收录”我再写入；也可以直接回数字或让我改标题。"
        return make_session_reply(
            "spark_candidate",
            summary,
            worklog + ["识别为候选火花，已暂存到会话状态，等待确认。"],
            {"pending_spark": state["pending_spark"], "suggested_actions": [{"label": "确认收录", "prompt": "确认收录"}, {"label": "判断选题", "prompt": f"判断这个选题值不值得做：{text}"}]},
        )

    return None


def local_agent_reply(message: str, config: dict, source: dict | None = None, conversation_history: list[dict] | None = None) -> dict:
    text = message.strip()
    initial_stage, initial_deliverables = route_deliverables(text)
    worklog = [
        "读取当前创作者配置。",
        "按内容生产入口规则判断用户阶段。",
        "确认这次应该走聊天还是内容生产动作。",
    ]

    session_reply = handle_session_stage(text, worklog)
    if session_reply:
        return session_reply

    state = load_session_state()
    pending_spark = state.get("pending_spark", {}) if isinstance(state.get("pending_spark"), dict) else {}
    confirmed_pending = is_confirm_collect(text) and bool(pending_spark.get("content"))
    if confirmed_pending:
        text = f"固化这个灵感：{pending_spark['content']}"

    stage, deliverables = route_deliverables(text)
    topic = extract_topic(text)

    if stage == "publish_registration":
        payload = parse_publish_message(text)
        published = register_publish(payload, config)
        return workflow_action_reply(
            "publish_registration",
            "发布登记已写入，这个选题下一步进入 T+3 复盘。",
            worklog,
            published,
            {"label": "T+3 复盘", "prompt": f"复盘这个选题：{payload.get('topic', topic)}"},
        )

    if stage == "retro":
        payload = parse_retro_message(text)
        retro = generate_retro(payload, config)
        return workflow_action_reply(
            "retro",
            "复盘已写入，预测记录保持锁定不改。",
            worklog,
            retro,
            {"label": "更新评分规则", "prompt": "升级评分规则"},
        )

    if stage == "chat":
        content, llm_note = call_chat_provider(text, config, conversation_history=conversation_history)
        worklog.append(llm_note)
        answer_source = "model" if content else "local_fallback"
        if not content:
            if "未配置 API Key" in llm_note:
                content = "我是 PenMoji 的内容工作台助手。现在模型还没连上，我只能先用本地规则回答。你可以在设置里配置 API Base URL、API Key 和模型名，然后点“测试模型”。"
            elif "未配置 API Base URL" in llm_note:
                content = "我是 PenMoji 的内容工作台助手。现在缺 API Base URL，模型还没连上。先去设置里补接口地址，再点“测试模型”。"
            else:
                content = f"我是 PenMoji 的内容工作台助手。模型调用失败，所以这次没有生成式回答。错误：{llm_note}"
        return {
            "id": str(uuid.uuid4()),
            "created_at": now_iso(),
            "status": "ok",
            "stage": stage,
            "summary": content,
            "worklog": worklog,
            "actions": [],
            "result": {
                "llm_used": answer_source == "model",
                "llm_note": llm_note,
                "answer_source": answer_source,
                "answer": content,
                "artifacts": [],
                "suggested_actions": [
                    {"label": "收录一个灵感", "prompt": "我想收录一个灵感，请引导我说清楚。"},
                    {"label": "判断选题", "prompt": "判断这个选题值不值得做："},
                    {"label": "写脚本", "prompt": "写视频脚本："},
                ],
            },
        }

    llm_text = ""
    llm_note = "未请求 LLM。"
    if deliverables:
        llm_text, llm_note = call_model_provider(build_llm_prompt(text, deliverables, config), config)
        worklog.append(llm_note)

    rendered = render_deliverables(topic, deliverables, config)
    skill_meta = execute_skill_deliverables(topic, rendered, deliverables, config)
    source_for_artifacts = dict(source or {})
    if confirmed_pending:
        source_for_artifacts["flow_topic"] = topic
        source_for_artifacts["flow_id"] = hashlib.sha256(topic.encode("utf-8")).hexdigest()[:12]
    if "score" in deliverables:
        score_data = isolated_blind_score(topic, config)
        source_for_artifacts["score_skill_route"] = score_data.get("skill_route", {})
        rendered["score"] = render_score(topic, score_data)
    artifacts = write_deliverable_artifacts(text, stage, deliverables, rendered, llm_text, config, source_for_artifacts, skill_meta)
    if artifacts:
        worklog.append(f"已落盘 {len(artifacts)} 个产物文件。")
    spark_item = None
    if confirmed_pending:
        spark_item = confirmed_spark_item(topic, pending_spark, artifacts, config)
        state["pending_spark"] = {}
        state["collecting_spark"] = False
        save_session_state(state)
        worklog.append("已写入火花列表，并清空待确认火花。")
    if "prediction" in deliverables and rendered.get("prediction"):
        run = lock_prediction_run(topic, rendered["prediction"], artifacts, source)
        worklog.append(f"已锁定发布预测记录：{run['id']}。")

    next_step = next_step_for(deliverables, topic)

    if stage == "guided_workflow":
        summary = "已把这个火花放进选题档案。下一步可以做盲打分或先写口播稿。"
    elif deliverables:
        labels = "、".join(DELIVERABLE_LABELS[key] for key in deliverables)
        summary = f"{labels}已生成，文件已经更新到这个选题的固定目录。"
    else:
        summary = "你可以直接丢一个观察、经历或一句判断，我会先帮你整理成候选火花。"

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
        if skill_meta:
            result["skill_meta"] = skill_meta
            result["skill_routes"] = {key: meta.get("skill_route", {}) for key, meta in skill_meta.items()}
        if spark_item:
            result["spark_item"] = spark_item
        if "score" in deliverables:
            result["skill_route"] = score_data.get("skill_route", {})
            result["score_meta"] = {
                "score_source": score_data.get("score_source", ""),
                "hidden_agent_run_consumed": bool(score_data.get("hidden_agent_run_consumed")),
                "hidden_agent_score_used": bool(score_data.get("hidden_agent_score_used")),
                "score_input_policy": score_data.get("score_input_policy", ""),
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
        elif path == "/api/topic":
            config = load_config(include_secret=False)
            query = {key: values[-1] for key, values in parse_qs(parsed.query).items()}
            self.send_json(topic_panel_payload(config, flow_id=query.get("flow_id", ""), topic=query.get("topic", "")))
        elif path == "/api/conversations":
            self.send_json({"items": list_conversations()})
        elif path.startswith("/api/conversations/"):
            conversation_id = unquote(path.removeprefix("/api/conversations/"))
            conversation = load_conversation(conversation_id)
            if not conversation:
                self.send_json({"error": "conversation not found"}, HTTPStatus.NOT_FOUND)
                return
            self.send_json({"conversation": conversation})
        elif path == "/api/workflow/runs":
            self.send_json({"items": read_workflow_runs()})
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
        elif path == "/api/cloud/link-status":
            config = load_config(include_secret=True)
            try:
                link = read_cloud_link_status(config)
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError) as exc:
                self.send_json({"error": f"device link status failed: {exc}"}, HTTPStatus.BAD_GATEWAY)
                return
            self.send_json({"status": "ok", "link": link, "cloud": load_config(include_secret=False).get("cloud", {})})
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/conversations/"):
            conversation_id = unquote(path.removeprefix("/api/conversations/"))
            deleted = delete_conversation(conversation_id)
            self.send_json({"status": "ok", "deleted": deleted})
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_PATCH(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            payload = self.read_json_body()
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if path.startswith("/api/conversations/"):
            conversation_id = unquote(path.removeprefix("/api/conversations/"))
            conversation = rename_conversation(conversation_id, payload.get("title", ""))
            if not conversation:
                self.send_json({"error": "conversation not found"}, HTTPStatus.NOT_FOUND)
                return
            self.send_json({"status": "ok", "conversation": conversation})
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
        elif path == "/api/conversations":
            conversation = create_conversation(payload.get("title", "新对话"))
            self.send_json({"status": "ok", "conversation": conversation}, HTTPStatus.CREATED)
        elif path == "/api/chat":
            config = load_config(include_secret=True)
            if payload.get("force_local"):
                config["api_key"] = ""
            message = payload.get("message", "")
            topic = extract_topic(message)
            source = {
                "flow_topic": payload.get("flow_topic") or topic,
                "flow_id": payload.get("flow_id") or hashlib.sha256(topic.encode("utf-8")).hexdigest()[:12],
            }
            if payload.get("inbox_id"):
                source["inbox_id"] = payload.get("inbox_id")
            if payload.get("demo"):
                source["demo"] = True
            conversation_id = payload.get("conversation_id") or ""
            conversation = load_conversation(conversation_id) if conversation_id else create_conversation(conversation_title_from_message(message))
            conversation_id = conversation.get("id") or conversation_id
            history = conversation_history(conversation)
            reply = local_agent_reply(message, config, source=source, conversation_history=history)
            conversation = append_conversation_turn(conversation_id, message, reply)
            reply["conversation"] = {"id": conversation.get("id"), "title": conversation.get("title"), "updated_at": conversation.get("updated_at")}
            self.send_json(reply)
        elif path == "/api/llm/test":
            config = load_config(include_secret=True)
            result = test_model_provider(config)
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
        elif path == "/api/workflow/publish":
            config = load_config(include_secret=False)
            result = register_publish(payload, config)
            self.send_json({"status": "ok", **result})
        elif path == "/api/workflow/retro":
            config = load_config(include_secret=False)
            result = generate_retro(payload, config)
            self.send_json({"status": "ok", **result})
        elif path == "/api/inbox":
            item = normalize_inspiration(payload)
            append_jsonl(INBOX_PATH, item)
            self.send_json({"status": "ok", "item": item}, HTTPStatus.CREATED)
        elif path in {"/api/spark/score", LEGACY_SCORE_ROUTE}:
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
                        "flow_id": payload.get("flow_id", ""),
                        "flow_topic": payload.get("flow_topic", ""),
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
            try:
                link = begin_cloud_device_link(config, payload)
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError) as exc:
                self.send_json({"error": f"device link failed: {exc}"}, HTTPStatus.BAD_GATEWAY)
                return
            self.send_json({"status": "ok", "link": link, "cloud": load_config(include_secret=False).get("cloud", {})})
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

    def is_client_disconnect(self, exc: BaseException) -> bool:
        return isinstance(exc, (BrokenPipeError, ConnectionAbortedError, ConnectionResetError)) or getattr(exc, "winerror", None) in {10053, 10054}

    def safe_write(self, data: bytes) -> bool:
        try:
            self.wfile.write(data)
            return True
        except OSError as exc:
            if self.is_client_disconnect(exc):
                return False
            raise

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
        except OSError:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "Could not read file")
            return
        try:
            self.send_response(HTTPStatus.OK)
            self.send_cors_headers()
            self.send_header("Content-Type", content_type + "; charset=utf-8" if content_type.startswith("text/") else content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.safe_write(data)
        except OSError as exc:
            if not self.is_client_disconnect(exc):
                raise

    def send_json(self, data: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        try:
            self.send_response(status)
            self.send_cors_headers()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.safe_write(body)
        except OSError as exc:
            if not self.is_client_disconnect(exc):
                raise

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
