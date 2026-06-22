from __future__ import annotations

from pathlib import Path


SKILL_ROUTES = {
    "score": {
        "skill": "blind_score",
        "prompt_file": "blind-score.md",
        "agent_mode": "hidden",
        "input_policy": "topic-title-rubric-only",
        "conversation_history_used": False,
    },
    "douyin_review": {
        "skill": "douyin_content_review",
        "prompt_file": "douyin-content-review.md",
        "agent_mode": "inline",
        "input_policy": "topic-and-script-only",
        "conversation_history_used": False,
    },
    "humanized_copy": {
        "skill": "humanizer",
        "prompt_file": "humanizer.md",
        "agent_mode": "inline",
        "input_policy": "text-only",
        "conversation_history_used": False,
    },
    "hook_review": {
        "skill": "hook_review",
        "prompt_file": "hook-review.md",
        "agent_mode": "inline",
        "input_policy": "opening-or-topic-only",
        "conversation_history_used": False,
    },
}


def skill_prompt_root(app_root: Path) -> Path:
    return app_root / "prompts" / "skills"


def skill_route_for_deliverable(deliverable: str) -> dict:
    route = SKILL_ROUTES.get(deliverable, {})
    return dict(route) if route else {}


def load_skill_prompt(app_root: Path, prompt_file: str) -> str:
    if not prompt_file:
        return ""
    path = skill_prompt_root(app_root) / prompt_file
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def skill_route_with_prompt(app_root: Path, deliverable: str) -> dict:
    route = skill_route_for_deliverable(deliverable)
    if route:
        route["prompt"] = load_skill_prompt(app_root, route.get("prompt_file", ""))
    return route
