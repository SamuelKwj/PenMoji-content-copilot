from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


REPO_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = REPO_ROOT / "content-workbench"
MAIN_PATH = APP_ROOT / "main.py"


def load_workbench():
    temp_root = Path(tempfile.mkdtemp(prefix="mosmori-capability-compliance-"))
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


class FailingModelHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return

    def do_POST(self) -> None:
        body = b'{"error":{"message":"bad model id"}}'
        self.send_response(400)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


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
            ("升级评分规则：检查权重", "score_rules_bump", "score-rules-bump.md"),
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

        server = ThreadingHTTPServer(("127.0.0.1", 0), FailingModelHandler)
        try:
            port = server.server_address[1]
            import threading

            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            content, note = wb.call_openai_chat(
                [{"role": "user", "content": "ping"}],
                {"api_key": "test-key", "api_base_url": f"http://127.0.0.1:{port}", "model": "bad-model"},
                timeout=5,
            )
            results.append(expect(not content and "HTTP 400" in note and "bad model id" in note, "llm-test:surfaces-http-error", note))
        finally:
            server.shutdown()
            server.server_close()

        humanized = wb.render_humanized_copy("综上所述，因此我们要赋能用户")
        rewrite_section = humanized.split("改写：", 1)[-1].split("处理说明：", 1)[0]
        results.append(expect("综上所述" not in rewrite_section, "humanizer:remove-summary-phrase", rewrite_section))
        results.append(expect("赋能" not in rewrite_section, "humanizer:remove-ai-ism", rewrite_section))

        contaminated = wb.mosmori_score_spark("这条脚本已经播放量10万，评论很多：普通人为什么半途而废", config=config, prefer_model=False)
        self_check = contaminated.get("self_check", {})
        results.append(
            expect(
                bool(self_check.get("any_contamination_signal")),
                "score:contamination-detected",
                json.dumps(self_check, ensure_ascii=False),
            )
        )

        chat_reply = wb.local_agent_reply("你是谁？", config)
        results.append(expect(chat_reply.get("stage") == "chat", "chat:casual-stage", str(chat_reply)))
        results.append(expect(not chat_reply.get("result", {}).get("artifacts"), "chat:no-artifacts", str(chat_reply)))
        results.append(expect(not wb.read_jsonl(wb.INBOX_PATH), "chat:no-inbox-write", str(wb.read_jsonl(wb.INBOX_PATH))))
        results.append(expect(chat_reply.get("result", {}).get("answer_source") in {"model", "local_fallback"}, "chat:answer-source", str(chat_reply)))

        material_chat_reply = wb.local_agent_reply("你是谁？\n\n火花：普通人为什么做个人IP总是半途而废", config)
        results.append(expect(material_chat_reply.get("stage") == "chat", "chat:material-label-does-not-force-spark", str(material_chat_reply)))
        results.append(expect(not material_chat_reply.get("result", {}).get("artifacts"), "chat:material-label-no-artifacts", str(material_chat_reply)))

        topic_advice_reply = wb.local_agent_reply("话题建议：帮我配几个话题", config)
        results.append(expect(topic_advice_reply.get("stage") == "chat", "chat:topic-advice-is-casual-chat", str(topic_advice_reply)))
        results.append(expect(not topic_advice_reply.get("result", {}).get("artifacts"), "chat:topic-advice-no-artifacts", str(topic_advice_reply)))
        timing_advice_reply = wb.local_agent_reply("发布时间建议：这条几点发", config)
        results.append(expect(timing_advice_reply.get("stage") == "chat", "chat:timing-advice-is-casual-chat", str(timing_advice_reply)))
        results.append(expect(not timing_advice_reply.get("result", {}).get("artifacts"), "chat:timing-advice-no-artifacts", str(timing_advice_reply)))

        short_label_reply = wb.local_agent_reply("个人ip，抖音创作者", config)
        results.append(expect(short_label_reply.get("stage") != "spark_candidate", "intent:short-label-not-spark-candidate", str(short_label_reply)))
        results.append(expect(not short_label_reply.get("result", {}).get("artifacts"), "intent:short-label-no-artifacts", str(short_label_reply)))

        profile_reply = wb.local_agent_reply("我是做个人IP口播，平台抖音，赛道是商业诊断。请先记住这个定位。", config)
        results.append(expect(profile_reply.get("stage") == "profile_update", "session:profile-update-stage", str(profile_reply)))
        session_state = wb.load_session_state()
        results.append(expect(session_state.get("profile", {}).get("platform") == "抖音", "session:profile-platform", str(session_state)))
        results.append(expect("个人IP" in session_state.get("profile", {}).get("track", ""), "session:profile-track", str(session_state)))
        results.append(expect(session_state.get("profile", {}).get("content_type") == "口播", "session:profile-content-type", str(session_state)))
        results.append(expect(session_state.get("profile", {}).get("niche") == "商业诊断", "session:profile-niche", str(session_state)))
        results.append(expect(not profile_reply.get("result", {}).get("artifacts"), "session:profile-no-artifacts", str(profile_reply)))
        fixed_profile_phrases = ["已记住你的定位", "你接下来可以直接说一个观察或灵感", "我会先帮你整理成候选火花"]
        results.append(expect(not any(phrase in profile_reply.get("summary", "") for phrase in fixed_profile_phrases), "session:profile-reply-not-fixed-template", profile_reply.get("summary", "")))
        system_prompt_after_profile = wb.build_workflow_system_prompt(config)
        for token in ["口播", "抖音", "个人IP", "商业诊断"]:
            results.append(expect(token in system_prompt_after_profile, f"prompt:profile-persists:{token}", system_prompt_after_profile[-500:]))

        empty_collect = wb.local_agent_reply("收录这个灵感：", config)
        results.append(expect(empty_collect.get("stage") == "collect_guidance", "session:empty-collect-guidance", str(empty_collect)))
        results.append(expect(not empty_collect.get("result", {}).get("artifacts"), "session:empty-collect-no-artifacts", str(empty_collect)))
        guided_observation = wb.local_agent_reply("就是，感觉现在生产内容的速度空前，但是我能如此，别人自然也可以如此，那么内容生成不就廉价了？", config)
        results.append(expect(guided_observation.get("stage") == "spark_candidate", "session:guided-observation-candidate", str(guided_observation)))
        results.append(expect(not guided_observation.get("result", {}).get("artifacts"), "session:guided-observation-no-artifacts", str(guided_observation)))
        results.append(expect("确认收录" in guided_observation.get("summary", ""), "session:guided-observation-asks-confirm", guided_observation.get("summary", "")))

        spark_candidate = wb.local_agent_reply("我发现普通人学AI为什么越学越焦虑", config)
        session_state = wb.load_session_state()
        title_options = session_state.get("pending_spark", {}).get("title_options", [])
        results.append(expect(spark_candidate.get("stage") == "spark_candidate", "session:spark-candidate-stage", str(spark_candidate)))
        results.append(expect(bool(session_state.get("pending_spark", {}).get("content")), "session:pending-spark-saved", str(session_state)))
        results.append(expect(not spark_candidate.get("result", {}).get("artifacts"), "session:spark-candidate-no-artifacts", str(spark_candidate)))
        results.append(expect(len(title_options) == 3, "spark:title-options-count", str(title_options)))
        empty_view_titles = [title for title in title_options if "到底卡在哪" in title or title.endswith("？")]
        results.append(expect(not empty_view_titles, "spark:title-options-have-viewpoint", str(title_options)))

        confirm_collect = wb.local_agent_reply("确认收录", config)
        results.append(expect(confirm_collect.get("stage") == "spark_solidify", "session:confirm-collect-solidifies", str(confirm_collect)))
        results.append(expect(bool(confirm_collect.get("result", {}).get("artifacts")), "session:confirm-collect-artifacts", str(confirm_collect)))

        conversation = wb.create_conversation("测试对话")
        reply_one = wb.local_agent_reply("你好", config, conversation_history=[])
        wb.append_conversation_turn(conversation["id"], "你好", reply_one)
        renamed_conversation = wb.rename_conversation(conversation["id"], "重命名后的对话")
        results.append(expect(renamed_conversation.get("title") == "重命名后的对话", "conversation:rename-title", str(renamed_conversation)))
        loaded_conversation = wb.load_conversation(conversation["id"])
        results.append(expect(loaded_conversation.get("id") == conversation["id"], "conversation:load-by-id", str(loaded_conversation)))
        results.append(expect(len(loaded_conversation.get("messages", [])) == 2, "conversation:persist-turn", str(loaded_conversation)))
        conversations = wb.list_conversations()
        results.append(expect(any(item.get("id") == conversation["id"] for item in conversations), "conversation:list-includes-created", str(conversations)))
        wb.delete_conversation(conversation["id"])
        results.append(expect(not wb.load_conversation(conversation["id"]).get("messages"), "conversation:delete-clears-messages", str(wb.load_conversation(conversation["id"]))))

        model_status = wb.test_model_provider({"api_key": "", "api_base_url": "", "model": "bad-model"})
        results.append(expect(model_status.get("status") == "failed" and model_status.get("tested_at"), "llm-test:status-shape", str(model_status)))

        results.append(expect(hasattr(wb.WorkbenchHandler, "safe_write"), "server:safe-write-helper-exists", "WorkbenchHandler.safe_write"))
        results.append(expect("ConnectionAbortedError" in MAIN_PATH.read_text(encoding="utf-8") and "BrokenPipeError" in MAIN_PATH.read_text(encoding="utf-8"), "server:client-disconnect-handled", "send_json/serve_file should tolerate aborted browser connections"))

        prediction = wb.local_agent_reply("预测这个选题：普通人做内容前如何判断入口", config)
        prediction_artifacts = prediction.get("result", {}).get("artifacts", [])
        results.append(expect(bool(prediction_artifacts), "artifacts:prediction-written", str(prediction)))
        readable_prediction_artifacts = []
        for artifact in prediction_artifacts:
            artifact_path = Path(artifact.get("path", ""))
            if artifact_path.exists() and artifact_path.read_text(encoding="utf-8").strip():
                readable_prediction_artifacts.append(artifact_path.name)
        results.append(expect(bool(readable_prediction_artifacts), "artifacts:prediction-readable", str(prediction_artifacts)))
        def topic_dir_from_artifacts(items):
            for artifact in items:
                path = Path(artifact.get("path", ""))
                if path.name == "manifest.json":
                    return path.parent
                for parent in [path.parent, *path.parents]:
                    if parent.parent.name == "topics":
                        return parent
            return Path()

        review_same_topic = wb.local_agent_reply("审核这个选题：普通人做内容前如何判断入口", config)
        review_artifacts = review_same_topic.get("result", {}).get("artifacts", [])
        score_same_topic = wb.local_agent_reply("打分这个选题：普通人做内容前如何判断入口", config, conversation_history=[{"role": "user", "content": "历史里有播放量 10 万，不能给盲打分看"}])
        score_artifacts = score_same_topic.get("result", {}).get("artifacts", [])
        prediction_topic_dir = topic_dir_from_artifacts(prediction_artifacts)
        review_topic_dir = topic_dir_from_artifacts(review_artifacts)
        score_topic_dir = topic_dir_from_artifacts(score_artifacts)
        expected_topic_dir_name = f"{wb.hashlib.sha256('普通人做内容前如何判断入口'.encode('utf-8')).hexdigest()[:12]}_{wb.safe_slug('普通人做内容前如何判断入口')}"
        expected_topic_dir = wb.project_path_from_config(config) / "topics" / expected_topic_dir_name
        results.append(expect(
            prediction_topic_dir == review_topic_dir == score_topic_dir == expected_topic_dir and expected_topic_dir.exists(),
            "artifacts:one-topic-one-folder",
            f"expected={expected_topic_dir}; prediction={prediction_topic_dir}; review={review_topic_dir}; score={score_topic_dir}",
        ))
        fixed_paths = {
            "manifest": expected_topic_dir / "manifest.json",
            "script": expected_topic_dir / "script" / "script.md",
            "prediction": expected_topic_dir / "prediction" / "prediction.md",
            "publish": expected_topic_dir / "publish" / "publish.md",
            "retro": expected_topic_dir / "retro" / "retro.md",
        }
        results.append(expect(all(path.exists() for path in fixed_paths.values()), "artifacts:topic-fixed-paths", str(fixed_paths)))
        llm_artifacts = [Path(item.get("path", "")) for item in [*prediction_artifacts, *review_artifacts, *score_artifacts] if item.get("type") == "llm_output"]
        results.append(expect(all(path.parent.name == "llm-output" for path in llm_artifacts), "artifacts:llm-output-history-subdir", str(llm_artifacts)))
        forbidden_reply_tokens = ["当前阶段", "当前步骤", "本次阶段", "stage:", "stage："]
        business_summaries = [prediction.get("summary", ""), review_same_topic.get("summary", ""), score_same_topic.get("summary", "")]
        results.append(expect(not any(token in summary for summary in business_summaries for token in forbidden_reply_tokens), "formatter:no-mechanical-stage-summary", str(business_summaries)))
        score_route = score_same_topic.get("result", {}).get("skill_route", {})
        results.append(expect(score_route.get("skill") == "blind_score" and score_route.get("isolated_agent") is True and score_route.get("conversation_history_used") is False, "skill-route:blind-score-isolated-agent", str(score_route)))
        results.append(expect(score_route.get("prompt_file") == "blind-score.md" and score_route.get("agent_mode") == "hidden" and bool(score_route.get("hidden_agent_run_id")), "skill-route:blind-score-real-hidden-agent", str(score_route)))
        hidden_run_path = Path(score_route.get("hidden_agent_run_path", ""))
        hidden_run = json.loads(hidden_run_path.read_text(encoding="utf-8")) if hidden_run_path.exists() else {}
        hidden_run_text = json.dumps(hidden_run, ensure_ascii=False)
        results.append(expect(hidden_run.get("llm_call", {}).get("attempted") is True and hidden_run.get("llm_call", {}).get("message_count") == 2, "hidden-agent:isolated-llm-call-attempted", hidden_run_text[:800]))
        results.append(expect("blind-score.md" in hidden_run_text and "盲打分" in hidden_run_text and "评分规则" in hidden_run_text, "hidden-agent:skill-prompt-in-run", hidden_run_text[:800]))
        hidden_input_text = json.dumps(hidden_run.get("input", {}), ensure_ascii=False)
        results.append(expect("10 万" not in hidden_input_text and "api_key" not in hidden_run_text and "api_base_url" not in hidden_run_text, "hidden-agent:no-history-or-secret-leak", hidden_run_text[:800]))
        results.append(expect("score_from_hidden_agent_run" in MAIN_PATH.read_text(encoding="utf-8") and "hidden_agent_run_consumed" in json.dumps(score_same_topic, ensure_ascii=False), "hidden-agent:score-parser-integrated", json.dumps(score_same_topic, ensure_ascii=False)[:800]))
        results.append(expect("10 万" not in json.dumps(score_same_topic, ensure_ascii=False), "skill-route:blind-score-no-history-leak", json.dumps(score_same_topic, ensure_ascii=False)[:500]))
        topic_panel = wb.topic_panel_payload(config, flow_id=score_route.get("flow_id", ""), topic="普通人做内容前如何判断入口")
        panel_sections = topic_panel.get("sections", {})
        results.append(expect(topic_panel.get("status") == "ok" and all(key in panel_sections for key in ["script", "prediction", "publish", "retro"]), "topic-panel:fixed-sections", str(topic_panel)[:800]))
        results.append(expect("普通人做内容前如何判断入口" in panel_sections.get("prediction", {}).get("content", ""), "topic-panel:prediction-bound-to-file", panel_sections.get("prediction", {})))
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

        static_text = (APP_ROOT / "static" / "index.html").read_text(encoding="utf-8")
        for token in ["modelStatusText", "modelTestResult", "answer_source", "demoView = false", "stage === \"chat\"", "conversationList", "newConversation", "deleteConversation", "renameConversation", "data-rename-conversation", "activeConversationId", "loadConversations", "leftWorkflowPanel", "spark-row", "spark-index", "spark-title-marquee", "spark-title-track", "spark-title-marquee-scroll", "spark-score-fixed", "topicPanel", "topicScriptContent", "topicPredictionContent", "topicPublishContent", "topicRetroContent", "loadTopicPanel", "/api/topic"]:
            results.append(expect(token in static_text, f"frontend:{token}", token))
        results.append(expect("当前阶段：" not in static_text, "frontend:no-mechanical-stage-label", "当前阶段 should not be rendered in replies"))
        results.append(expect("conversation-panel" not in static_text, "frontend:no-center-conversation-panel", "conversation management should live in the left sidebar"))
        left_anchor = static_text.find('id="leftWorkflowPanel"')
        spark_anchor = static_text.find('id="sparkBoard"')
        chat_anchor = static_text.find('class="panel chat-panel"')
        results.append(expect(left_anchor >= 0 and spark_anchor > left_anchor and chat_anchor > spark_anchor, "frontend:left-sidebar-conversation-before-chat", f"left={left_anchor}; spark={spark_anchor}; chat={chat_anchor}"))
        results.append(expect("composerFocused = true;" in static_text and "blur();" not in static_text, "frontend:composer-stays-expanded", "composer should stay open after send"))

        prompt_path = APP_ROOT / "prompts" / "content_creator_workflow.md"
        results.append(expect(prompt_path.exists(), "prompt:generic-workflow-file-exists", str(prompt_path)))
        if prompt_path.exists():
            prompt_text = prompt_path.read_text(encoding="utf-8")
            for token in ["需求分类", "火花/灵感", "盲打分", "预测", "拍摄", "发布", "复盘", "不要一条路走到黑", "只执行当前一步"]:
                results.append(expect(token in prompt_text, f"prompt:contains:{token}", token))
            forbidden_tokens = ["KK", "奉孝", "大王", "samue", "C:\\Users\\samue", "cheat-content"]
            leaked = [token for token in forbidden_tokens if token in prompt_text]
            results.append(expect(not leaked, "prompt:no-user-specific-leaks", str(leaked)))
            system_prompt = wb.build_workflow_system_prompt(config)
            results.append(expect("内容创作助理" in system_prompt and "需求分类" in system_prompt and "不要一条路走到黑" in system_prompt, "prompt:loaded-into-system-prompt", system_prompt[:400]))
            removed_update_pack_features = ["话题建议", "发布时间建议"]
            leaked_update_pack_features = [token for token in removed_update_pack_features if token in prompt_text or token in static_text or token in system_prompt]
            results.append(expect(not leaked_update_pack_features, "update-pack:no-topic-or-timing-features", str(leaked_update_pack_features)))

        skill_prompt_dir = APP_ROOT / "prompts" / "skills"
        skill_prompts = {
            "blind-score.md": ["盲打分", "只能看待评分内容", "评分规则"],
            "douyin-content-review.md": ["限流", "姜胡说", "三步法"],
            "humanizer.md": ["去AI味", "AI味", "像人写"],
            "hook-review.md": ["前三秒", "开头", "冲突"],
        }
        for filename, tokens in skill_prompts.items():
            path = skill_prompt_dir / filename
            results.append(expect(path.exists(), f"skill-prompt:exists:{filename}", str(path)))
            if path.exists():
                prompt_body = path.read_text(encoding="utf-8")
                results.append(expect(all(token in prompt_body for token in tokens), f"skill-prompt:contains:{filename}", prompt_body[:500]))

        route_cases = {
            "score": ("blind_score", "blind-score.md"),
            "douyin_review": ("douyin_content_review", "douyin-content-review.md"),
            "humanized_copy": ("humanizer", "humanizer.md"),
            "hook_review": ("hook_review", "hook-review.md"),
        }
        for deliverable, expected in route_cases.items():
            route = wb.skill_route_for_deliverable(deliverable)
            results.append(expect((route.get("skill"), route.get("prompt_file")) == expected, f"skill-registry:route:{deliverable}", str(route)))

        main_text = MAIN_PATH.read_text(encoding="utf-8")
        architecture_modules = [
            APP_ROOT / "agent" / "intent.py",
            APP_ROOT / "agent" / "state.py",
            APP_ROOT / "agent" / "prompt_builder.py",
            APP_ROOT / "agent" / "skill_registry.py",
            APP_ROOT / "agent" / "hidden_agent.py",
            APP_ROOT / "model" / "llm.py",
            APP_ROOT / "storage" / "conversations.py",
            APP_ROOT / "workflow" / "spark.py",
            APP_ROOT / "workflow" / "predict.py",
            APP_ROOT / "workflow" / "review.py",
            APP_ROOT / "workflow" / "publish.py",
            APP_ROOT / "workflow" / "retro.py",
        ]
        missing_architecture_modules = [str(path.relative_to(APP_ROOT)) for path in architecture_modules if not path.exists()]
        results.append(expect(not missing_architecture_modules, "architecture:layer-modules-exist", str(missing_architecture_modules)))
        for token in ["from agent.prompt_builder", "from agent.state", "from model.llm", "from storage.conversations", "from workflow.spark"]:
            results.append(expect(token in main_text, f"architecture:main-imports:{token}", token))

        audit_path = APP_ROOT / "docs" / "capability-coverage-audit.md"
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
