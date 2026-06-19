from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = REPO_ROOT / "content-workbench"
MAIN_PATH = APP_ROOT / "main.py"


def load_workbench():
    temp_root = Path(tempfile.mkdtemp(prefix="biemuoji-skill-compliance-"))
    os.environ["CONTENT_WORKBENCH_HOME"] = str(temp_root)
    spec = importlib.util.spec_from_file_location("content_workbench_main", MAIN_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {MAIN_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module, temp_root


def expect(condition: bool, name: str, detail: str = "") -> dict:
    return {"name": name, "pass": bool(condition), "detail": detail}


def deliverable_types(reply: dict) -> list[str]:
    return [item.get("type") for item in reply.get("result", {}).get("deliverables", [])]


def artifact_names(reply: dict) -> list[str]:
    names = []
    for item in reply.get("result", {}).get("artifacts", []):
        if item.get("type") == "manifest":
            continue
        names.append(Path(item.get("path", "")).name)
    return names


def run() -> dict:
    wb, temp_root = load_workbench()
    results: list[dict] = []
    config = wb.load_config(include_secret=True)
    try:
        route_cases = [
            ("初始化：我是新用户", "init_state", "init-state.md"),
            ("迁移：检查旧状态", "migration_report", "migration-report.md"),
            ("状态", "status_report", "status-report.md"),
            ("抓热点：普通人内容创作", "trend_candidates", "trend-candidates.md"),
            ("推荐选题", "topic_recommendation", "topic-recommendation.md"),
            ("学这个账号：个人IP对标账号", "benchmark_analysis", "benchmark-analysis.md"),
            ("更新受众画像：根据最近评论", "persona_report", "persona-report.md"),
            ("升级评分规则：检查权重", "rubric_bump", "score-rules-bump.md"),
            ("我想做一条普通人做内容前如何判断入口", "seed_draft", "seed-draft.md"),
            ("抖音审稿：保证你一定月入十万，加我微信", "douyin_review", "douyin-review.md"),
            ("优化开头：普通人做个人IP为什么半途而废", "hook_review", "hook-review.md"),
            ("去AI味：综上所述，因此我们要赋能用户", "humanized_copy", "humanized-copy.md"),
            ("金句卡：你不是不努力，是入口选错了", "overlay_card", "overlay-card.md"),
            ("拍了：普通人做内容前如何判断入口", "shoot_record", "shoot-record.md"),
            ("投流：这条视频要不要投", "promotion_plan", "promotion-plan.md"),
            ("分析好文：一篇关于普通人成长的文章", "good_article_analysis", "good-article-analysis.md"),
        ]
        for message, expected_type, expected_file in route_cases:
            reply = wb.local_agent_reply(message, config)
            types = deliverable_types(reply)
            files = artifact_names(reply)
            results.append(
                expect(
                    expected_type in types and expected_file in files,
                    f"route:{expected_type}",
                    f"types={types}; files={files}",
                )
            )

        douyin = wb.render_douyin_review("保证你一定月入十万，加我微信，扫码进群", config)
        results.append(expect("高风险" in douyin, "douyin-review:hard-risk", douyin))
        for token in ["联系方式/私域导流", "利益诱惑", "绝对化承诺", "必须修改后再发"]:
            results.append(expect(token in douyin, f"douyin-review:{token}", douyin))

        humanized = wb.render_humanized_copy("综上所述，因此我们要赋能用户")
        rewrite_section = humanized.split("改写：", 1)[-1].split("处理说明：", 1)[0]
        results.append(expect("综上所述" not in rewrite_section, "humanizer:remove-summary-phrase", rewrite_section))
        results.append(expect("赋能" not in rewrite_section, "humanizer:remove-ai-ism", rewrite_section))

        contaminated = wb.blind_score_spark("这条脚本已经播放量10万，评论很多：普通人为什么半途而废", config=config, prefer_model=False)
        self_check = contaminated.get("self_check", {})
        results.append(
            expect(
                bool(self_check.get("any_contamination_signal")),
                "blind-score:contamination-detected",
                json.dumps(self_check, ensure_ascii=False),
            )
        )

        prediction = wb.local_agent_reply("预测这个选题：普通人做内容前如何判断入口", config)
        run_items = wb.read_workflow_runs()
        prediction_run = run_items[-1] if run_items else {}
        results.append(expect(bool(prediction_run.get("immutable_prediction")), "predict:immutable-run", str(prediction_run)))
        before_hash = prediction_run.get("prediction_hash")
        wb.generate_retro(
            {
                "flow_id": prediction_run.get("flow_id"),
                "topic": prediction_run.get("flow_topic"),
                "metrics": {"views": 10000, "likes": 500, "comments": 80},
            },
            config,
        )
        after_run = wb.find_latest_workflow_run(flow_id=prediction_run.get("flow_id"))
        results.append(expect(after_run.get("prediction_hash") == before_hash, "retro:does-not-mutate-prediction", str(after_run)))

        audit_path = APP_ROOT / "docs" / "skill-coverage-audit.md"
        audit_text = audit_path.read_text(encoding="utf-8")
        covered = [
            line for line in audit_text.splitlines()
            if line.startswith("| ") and "已覆盖" in line and "`" in line
        ]
        results.append(expect(len(covered) >= 19, "coverage-audit:all-capabilities-listed", f"covered_rows={len(covered)}"))

        failed = [item for item in results if not item["pass"]]
        return {
            "status": "pass" if not failed else "fail",
            "total": len(results),
            "passed": len(results) - len(failed),
            "failed": failed,
            "temp_root": str(temp_root),
        }
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "pass" else 1)
