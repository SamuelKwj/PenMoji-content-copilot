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


def post_json(handler_cls, path: str, payload: dict) -> dict:
    captured: dict = {}
    handler = object.__new__(handler_cls)
    handler.path = path
    handler.headers = {"Content-Length": str(len(json.dumps(payload, ensure_ascii=False).encode("utf-8")))}
    handler.rfile = None
    handler.send_json = lambda data, status=200: captured.update({"data": data, "status": status})
    handler.send_error = lambda status, message="": captured.update({"error": message, "status": status})
    handler.read_json_body = lambda: payload
    handler.do_POST()
    return captured.get("data", captured)


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
        for casual_message in ["你好", "今天状态如何", "随便聊两句", "你能帮我做什么"]:
            casual_reply = wb.local_agent_reply(casual_message, config)
            results.append(expect(casual_reply.get("stage") == "chat", f"chat:casual-stage:{casual_message}", str(casual_reply)))
            results.append(expect(not casual_reply.get("result", {}).get("artifacts"), f"chat:no-artifacts:{casual_message}", str(casual_reply)))
            results.append(expect("spark_card" not in json.dumps(casual_reply, ensure_ascii=False), f"chat:no-spark-card:{casual_message}", json.dumps(casual_reply, ensure_ascii=False)[:500]))
        results.append(expect(not wb.read_jsonl(wb.INBOX_PATH), "chat:repeated-casual-no-inbox-write", str(wb.read_jsonl(wb.INBOX_PATH))))

        delete_test_item = wb.upsert_inbox_item({"type": "text", "content": "待删除火花", "sync_status": "pulled"})
        deleted_item = wb.delete_inbox_item(delete_test_item.get("id", ""))
        remaining_inbox = wb.read_jsonl(wb.INBOX_PATH)
        results.append(expect(deleted_item and deleted_item.get("content") == "待删除火花", "inbox-delete:returns-deleted-item", str(deleted_item)))
        results.append(expect(not any(item.get("id") == delete_test_item.get("id") for item in remaining_inbox), "inbox-delete:removes-only-inbox-item", str(remaining_inbox)))

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

        revision_history = [
            {"role": "user", "content": "就我觉得很多人使用ai都是不动脑筋"},
            {
                "role": "assistant",
                "content": "标题方向：1. 《用AI越久越笨：90%的人根本不会用AI，只是在给脑子放假》",
            },
        ]
        original_call_chat_provider = wb.call_chat_provider
        wb.call_chat_provider = lambda message, cfg, conversation_history=None: (
            "我明白，这批太像流量模板了。我们换成更克制、更有判断感的一批标题。",
            "测试模型返回",
        )
        revision_reply = wb.local_agent_reply("我不喜欢这种烂大街的标题，换一批。", config, conversation_history=revision_history)
        wb.call_chat_provider = original_call_chat_provider
        results.append(expect(revision_reply.get("stage") == "chat", "chat:title-revision-stays-chat", str(revision_reply)))
        results.append(expect(not revision_reply.get("result", {}).get("artifacts"), "chat:title-revision-no-artifacts", str(revision_reply)))
        results.append(expect("text_pack" not in json.dumps(revision_reply, ensure_ascii=False), "chat:title-revision-no-text-pack", json.dumps(revision_reply, ensure_ascii=False)[:800]))
        option_history = [
            {"role": "user", "content": "就我觉得很多人使用ai都是不动脑筋"},
            {
                "role": "assistant",
                "content": "\n".join(
                    [
                        "这次试试这四个：",
                        "1. 《我观察：大部分人用AI，只是把“自己该想的事”直接扔给AI了》",
                        "2. 用AI帮我写稿→AI帮我想选题→我没什么想法了｜这是不是你？",
                        "3. 我现在用AI的原则：只让它帮我干活，绝不让它帮我想问题",
                        "4. 别骂AI卷了，大部分人本来就懒得动脑筋",
                    ]
                ),
            },
        ]
        selected_reply = wb.local_agent_reply("4", config, conversation_history=option_history)
        selected = selected_reply.get("result", {}).get("selected_option", {})
        selected_spark = selected_reply.get("result", {}).get("spark_item", {})
        results.append(expect(selected_reply.get("stage") == "spark_collected", "spark:numbered-title-choice-collects-after-blind-score", str(selected_reply)))
        results.append(expect(not selected_reply.get("result", {}).get("artifacts"), "spark:numbered-title-choice-no-output-artifact", str(selected_reply)))
        results.append(expect("已保存" not in selected_reply.get("summary", "") and "完整维度" not in selected_reply.get("summary", ""), "spark:numbered-title-choice-no-report-style-summary", selected_reply.get("summary", "")))
        results.append(expect(selected.get("index") == 4 and "别骂AI卷了" in selected.get("content", ""), "chat:numbered-title-choice-selects-fourth", str(selected_reply)))
        results.append(expect(selected_spark.get("content") == selected.get("content") and wb.mosmori_score_value(selected_spark), "spark:numbered-title-choice-enters-inbox-with-score", str(selected_spark)))
        followup_review = wb.local_agent_reply("判断这个选题值不值得做：", config, conversation_history=option_history + [{"role": "user", "content": "4"}, {"role": "assistant", "content": selected_reply.get("summary", "")}])
        results.append(expect(followup_review.get("stage") == "on_demand_production" and "review" in deliverable_types(followup_review), "chat:numbered-title-choice-followup-produces-review", json.dumps(followup_review, ensure_ascii=False)[:800]))
        results.append(expect("别骂AI卷了" in followup_review.get("result", {}).get("topic", "") and "我观察" not in followup_review.get("result", {}).get("topic", ""), "chat:numbered-title-choice-followup-uses-selected-topic", followup_review.get("result", {}).get("topic", "")))

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

        inbox_before_empty_guides = len(wb.read_jsonl(wb.INBOX_PATH))
        empty_collect = wb.local_agent_reply("收录这个灵感：", config)
        results.append(expect(empty_collect.get("stage") == "collect_guidance", "session:empty-collect-guidance", str(empty_collect)))
        results.append(expect(not empty_collect.get("result", {}).get("artifacts"), "session:empty-collect-no-artifacts", str(empty_collect)))
        results.append(expect(len(wb.read_jsonl(wb.INBOX_PATH)) == inbox_before_empty_guides, "session:empty-collect-no-inbox-write", str(wb.read_jsonl(wb.INBOX_PATH))))
        for empty_guide in ["审核这个灵感：", "写视频脚本：", "判断这个选题值不值得做："]:
            guide_reply = wb.local_agent_reply(empty_guide, config)
            results.append(expect(guide_reply.get("stage") in {"collect_guidance", "chat"}, f"guide:empty-template-no-production-stage:{empty_guide}", str(guide_reply)))
            results.append(expect(not guide_reply.get("result", {}).get("artifacts"), f"guide:empty-template-no-artifacts:{empty_guide}", str(guide_reply)))
        results.append(expect(len(wb.read_jsonl(wb.INBOX_PATH)) == inbox_before_empty_guides, "guide:empty-template-no-inbox-write", str(wb.read_jsonl(wb.INBOX_PATH))))

        contextual_history = [
            {"role": "user", "content": "人不可以没有感受"},
            {"role": "assistant", "content": "标题方向：1. 《我发现，大部分人的内耗都来自「不敢有感受」》"},
        ]
        contextual_review = wb.local_agent_reply("判断这个选题值不值得做：", config, conversation_history=contextual_history)
        results.append(expect(contextual_review.get("stage") == "on_demand_production" and "review" in deliverable_types(contextual_review), "guide:empty-template-uses-context-topic", json.dumps(contextual_review, ensure_ascii=False)[:800]))
        results.append(expect(contextual_review.get("result", {}).get("topic") == "我发现，大部分人的内耗都来自「不敢有感受」", "guide:context-topic-normalized", contextual_review.get("result", {}).get("topic", "")))
        low_score_next = wb.next_step_for(["score"], "我发现，大部分人的内耗都来自「不敢有感受」", {"mosmori_score": 42})
        results.append(expect(low_score_next.get("label") == "优化入口" and "预测" not in low_score_next.get("label", ""), "score:low-score-next-step-optimizes-first", str(low_score_next)))
        results.append(expect(wb.normalize_title_text("我发现，大部分人的内耗都来自「不敢有感受") == "我发现，大部分人的内耗都来自「不敢有感受」", "title:normalizes-dangling-quote", wb.normalize_title_text("我发现，大部分人的内耗都来自「不敢有感受")))

        chat_history = [
            {"role": "user", "content": "记录灵感，人类在自寻死路"},
            {"role": "assistant", "content": "标题方向：《我们一边求生，一边亲手挖坟》"},
            {"role": "user", "content": "A"},
            {"role": "assistant", "content": "下面是大纲，口播结构：### 口播大纲：《我们一边求生，一边亲手挖坟》"},
        ]
        original_call_chat_provider = wb.call_chat_provider
        wb.call_chat_provider = lambda message, cfg, conversation_history=None: (
            "## 口播脚本：《我们一边求生，一边亲手挖坟》\n\n【开头】人类一边求生，一边亲手挖坟。",
            "测试模型返回",
        )
        materialized = wb.local_agent_reply(
            "2",
            config,
            source={"flow_topic": "2", "flow_id": "badliteral"},
            conversation_history=chat_history,
        )
        wb.call_chat_provider = original_call_chat_provider
        materialized_item = materialized.get("result", {}).get("spark_item", {})
        materialized_paths = [Path(item.get("path", "")) for item in materialized.get("result", {}).get("artifacts", [])]
        expected_materialized_dir = wb.project_path_from_config(config) / "topics" / f"{wb.hashlib.sha256('我们一边求生，一边亲手挖坟'.encode('utf-8')).hexdigest()[:12]}_{wb.safe_slug('我们一边求生，一边亲手挖坟')}"
        results.append(expect(materialized.get("stage") == "chat_materialized" and "video_script" in [item.get("type") for item in materialized.get("result", {}).get("deliverables", [])], "chat-workflow:number-choice-materializes-artifact", json.dumps(materialized, ensure_ascii=False)[:800]))
        results.append(expect(materialized_item.get("content") == "我们一边求生，一边亲手挖坟" and materialized_item.get("flow_topic") == "我们一边求生，一边亲手挖坟", "chat-workflow:persisted-inbox-real-topic", str(materialized_item)))
        results.append(expect(materialized_paths and all(expected_materialized_dir in path.parents for path in materialized_paths), "chat-workflow:artifacts-under-real-topic-not-literal-choice", f"expected={expected_materialized_dir}; paths={materialized_paths}"))

        backfill_conversation = {
            "id": "backfill-test",
            "title": "记录灵感，人类在自寻死路",
            "messages": [
                {"role": "user", "content": "记录灵感，人类在自寻死路"},
                {"role": "assistant", "content": "标题方向已确认：**《我们一边求生，一边亲手挖坟》**。"},
                {"role": "assistant", "content": "### 口播大纲：《我们一边求生，一边亲手挖坟》\\n\\n**开头钩子**：现在最勤奋的人，反而最可能被淘汰。"},
                {"role": "assistant", "content": "**盲打分结果：**\\n\\n| 维度 | 分数（1-5） | 评语 |\\n|------|------------|------|\\n| 钩子吸引力 | 4 | 有冲击力 |\\n\\n**总分：20/25（B+）**"},
                {"role": "assistant", "content": "## 口播脚本：《我们一边求生，一边亲手挖坟》\\n\\n**【开头 · 钩子 · 15秒】**\\n\\n你可能没意识到——现在最勤奋的人，反而是最容易被淘汰的人。"},
                {"role": "assistant", "content": "## 预测结果\\n\\n| 维度 | 预测值 | 说明 |\\n|------|--------|------|\\n| 播放量（72小时） | 1.5万 - 3万 | 标题冲击力强 |"},
            ],
        }
        backfill = wb.materialize_conversation_artifacts(backfill_conversation, config)
        backfill_item = backfill.get("spark_item", {})
        backfill_paths = [Path(item.get("path", "")) for item in backfill.get("artifacts", [])]
        backfill_types = {item.get("type") for item in backfill.get("artifacts", [])}
        expected_backfill_dir = wb.project_path_from_config(config) / "topics" / f"{wb.hashlib.sha256('我们一边求生，一边亲手挖坟'.encode('utf-8')).hexdigest()[:12]}_{wb.safe_slug('我们一边求生，一边亲手挖坟')}"
        results.append(expect(backfill.get("status") == "ok" and backfill_item.get("content") == "我们一边求生，一边亲手挖坟", "backfill:conversation-materializes-inbox-real-topic", json.dumps(backfill, ensure_ascii=False)[:800]))
        results.append(expect({"seed_draft", "score", "video_script", "prediction"}.issubset(backfill_types), "backfill:conversation-materializes-all-deliverables", str(backfill_types)))
        results.append(expect(backfill_paths and all(expected_backfill_dir in path.parents for path in backfill_paths), "backfill:artifacts-under-topic", f"expected={expected_backfill_dir}; paths={backfill_paths}"))



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
        before_conversation_count = len(wb.list_conversations())
        created_reply = post_json(wb.WorkbenchHandler, "/api/chat", {"message": "连续会话第一句"})
        created_id = created_reply.get("conversation", {}).get("id", "")
        continued_reply = post_json(wb.WorkbenchHandler, "/api/chat", {"message": "连续会话第二句", "conversation_id": created_id})
        after_conversation_count = len(wb.list_conversations())
        continued_loaded = wb.load_conversation(created_id)
        results.append(expect(created_id and continued_reply.get("conversation", {}).get("id") == created_id, "conversation:http-preserves-active-id", str({"created": created_reply.get("conversation"), "continued": continued_reply.get("conversation")})))
        results.append(expect(after_conversation_count == before_conversation_count + 1 and len(continued_loaded.get("messages", [])) == 4, "conversation:http-one-thread-no-extra-conversation", str({"before": before_conversation_count, "after": after_conversation_count, "loaded": continued_loaded})))
        wb.delete_conversation(created_id)
        wb.delete_conversation(conversation["id"])
        results.append(expect(not wb.load_conversation(conversation["id"]).get("messages"), "conversation:delete-clears-messages", str(wb.load_conversation(conversation["id"]))))

        model_status = wb.test_model_provider({"api_key": "", "api_base_url": "", "model": "bad-model"})
        results.append(expect(model_status.get("status") == "failed" and model_status.get("tested_at"), "llm-test:status-shape", str(model_status)))

        original_call_openai_chat = wb.call_openai_chat

        def fake_model_deliverables(messages, cfg, temperature=0.7, timeout=60):
            user_text = "\n".join(str(item.get("content", "")) for item in messages if item.get("role") == "user")
            requested = [key for key in wb.DELIVERABLE_LABELS if key in user_text]
            if not requested:
                requested = ["video_script"]
            payload = {
                "summary": "模型已经根据用户输入自动判断并推进工作流。",
                "deliverables": {
                    key: f"# {wb.DELIVERABLE_LABELS.get(key, key)}\n\n模型驱动产物-{key}-入口判断。\n\n主题来自用户输入，不使用固定模板。"
                    for key in requested
                },
            }
            return json.dumps(payload, ensure_ascii=False), "测试模型返回结构化产物。"

        model_config = {**config, "api_key": "test-key", "api_base_url": "http://model.test/v1", "model": "test-model"}
        wb.call_openai_chat = fake_model_deliverables
        try:
            model_script_reply = wb.local_agent_reply("写视频脚本：普通人做内容前如何判断入口", model_config)
            script_paths = [Path(item.get("path", "")) for item in model_script_reply.get("result", {}).get("artifacts", []) if item.get("type") == "video_script"]
            script_text = script_paths[0].read_text(encoding="utf-8") if script_paths else ""
            results.append(expect("模型驱动产物-video_script-入口判断" in script_text, "model-driven:script-file-uses-model-output", script_text[:800]))
            results.append(expect("今天想讲一个很多人做个人 IP 时都会踩的坑" not in script_text, "model-driven:script-file-not-fixed-template", script_text[:800]))
            generation_meta = model_script_reply.get("result", {}).get("generation_meta", {})
            results.append(expect(generation_meta.get("model_outputs_used") and "video_script" in generation_meta.get("model_outputs_used"), "model-driven:generation-meta-visible", json.dumps(generation_meta, ensure_ascii=False)))

            full_flow_reply = wb.local_agent_reply("完整流程：模型驱动完整链路隔离测试", model_config)
            full_flow_types = deliverable_types(full_flow_reply)
            expected_full_flow = {"spark_card", "seed_draft", "review", "score", "prediction", "video_script", "text_pack", "static_page"}
            results.append(expect(expected_full_flow.issubset(set(full_flow_types)), "autopilot:full-flow-generates-business-chain", str(full_flow_types)))
            full_flow_paths = [Path(item.get("path", "")) for item in full_flow_reply.get("result", {}).get("artifacts", []) if item.get("type") in {"spark_card", "seed_draft", "review", "prediction", "video_script", "text_pack", "static_page"}]
            full_flow_text = "\n".join(path.read_text(encoding="utf-8") for path in full_flow_paths if path.exists())
            results.append(expect("模型驱动产物-video_script-入口判断" in full_flow_text and "模型驱动产物-spark_card-入口判断" in full_flow_text, "autopilot:full-flow-files-use-model-output", full_flow_text[:1000]))

            publish_model_reply = wb.local_agent_reply(
                "发布登记：选题：模型驱动发布登记测试，平台抖音，链接 https://v.douyin.com/model-flow，发布时间 2026-06-26 20:00",
                model_config,
            )
            publish_model_paths = [Path(item.get("path", "")) for item in publish_model_reply.get("result", {}).get("artifacts", []) if item.get("type") == "publish_record"]
            publish_model_text = publish_model_paths[0].read_text(encoding="utf-8") if publish_model_paths else ""
            results.append(expect("模型驱动产物-publish_record-入口判断" in publish_model_text, "model-driven:publish-record-uses-model-output", publish_model_text[:800]))
            results.append(expect("https://v.douyin.com/model-flow" in publish_model_text and "2026-06-26 20:00" in publish_model_text, "model-driven:publish-record-preserves-facts", publish_model_text[:800]))
        finally:
            wb.call_openai_chat = original_call_openai_chat

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
            "ledger": expected_topic_dir / "ledger.json",
            "script": expected_topic_dir / "script" / "script.md",
            "prediction": expected_topic_dir / "prediction" / "prediction.md",
            "publish": expected_topic_dir / "publish" / "publish.md",
            "retro": expected_topic_dir / "retro" / "retro.md",
        }
        results.append(expect(all(path.exists() for path in fixed_paths.values()), "artifacts:topic-fixed-paths", str(fixed_paths)))
        ledger = json.loads(fixed_paths["ledger"].read_text(encoding="utf-8")) if fixed_paths["ledger"].exists() else {}
        ledger_artifacts = ledger.get("artifacts", {})
        results.append(expect(ledger.get("flow_id") == wb.hashlib.sha256("普通人做内容前如何判断入口".encode("utf-8")).hexdigest()[:12] and ledger.get("topic") == "普通人做内容前如何判断入口", "ledger:identity", json.dumps(ledger, ensure_ascii=False)[:800]))
        for key in ["review", "score", "prediction"]:
            results.append(expect(key in ledger_artifacts and Path(ledger_artifacts.get(key, {}).get("path", "")).exists(), f"ledger:artifact:{key}", json.dumps(ledger_artifacts.get(key, {}), ensure_ascii=False)[:500]))
        results.append(expect(ledger.get("status") in {"reviewed", "scored", "predicted", "scripted", "published", "retrospected"} and bool(ledger.get("next_step")), "ledger:status-next-step", json.dumps(ledger, ensure_ascii=False)[:800]))
        results.append(expect(any(event.get("event") == "prediction_generated" for event in ledger.get("history", [])), "ledger:history-prediction-event", json.dumps(ledger.get("history", []), ensure_ascii=False)[:800]))
        llm_artifacts = [Path(item.get("path", "")) for item in [*prediction_artifacts, *review_artifacts, *score_artifacts] if item.get("type") == "llm_output"]
        results.append(expect(all(path.parent.name == "llm-output" for path in llm_artifacts), "artifacts:llm-output-history-subdir", str(llm_artifacts)))
        forbidden_reply_tokens = ["当前阶段", "当前步骤", "本次阶段", "stage:", "stage："]
        business_summaries = [prediction.get("summary", ""), review_same_topic.get("summary", ""), score_same_topic.get("summary", "")]
        results.append(expect(not any(token in summary for summary in business_summaries for token in forbidden_reply_tokens), "formatter:no-mechanical-stage-summary", str(business_summaries)))
        review_briefs = review_same_topic.get("result", {}).get("business_briefs", [])
        score_briefs = score_same_topic.get("result", {}).get("business_briefs", [])
        score_brief = next((item for item in score_briefs if item.get("type") == "score"), {})
        review_brief = next((item for item in review_briefs if item.get("type") == "review"), {})
        results.append(expect(review_brief.get("summary") and (review_brief.get("why") or review_brief.get("risks")), "business-brief:review-explains-value-judgment", json.dumps(review_brief, ensure_ascii=False)[:800]))
        results.append(expect(score_brief.get("score") is not None and score_brief.get("dimensions") and score_brief.get("standards"), "business-brief:score-explains-score-and-standards", json.dumps(score_brief, ensure_ascii=False)[:1000]))
        score_brief_text = json.dumps(score_brief, ensure_ascii=False)
        results.append(expect("综合分" in score_same_topic.get("summary", "") and "钩子强度" in score_brief_text and "情感共鸣" in score_brief_text, "business-brief:score-visible-to-user", score_same_topic.get("summary", "") + score_brief_text[:800]))
        prediction_briefs = prediction.get("result", {}).get("business_briefs", [])
        prediction_brief = next((item for item in prediction_briefs if item.get("deliverable") == "prediction"), {})
        results.append(expect("预测结论" in prediction_brief.get("content", "") and "主要风险" in prediction_brief.get("content", ""), "business-brief:prediction-visible-to-user", json.dumps(prediction_brief, ensure_ascii=False)[:1000]))
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
        panel_ledger = topic_panel.get("ledger", {})
        results.append(expect(panel_ledger.get("flow_id") == score_route.get("flow_id") and "score" in panel_ledger.get("artifacts", {}), "topic-panel:ledger-returned", json.dumps(panel_ledger, ensure_ascii=False)[:800]))
        run_items = wb.read_workflow_runs()
        prediction_run = run_items[-1] if run_items else {}
        results.append(expect(bool(prediction_run.get("immutable_prediction")), "predict:immutable-run", str(prediction_run)))
        before_hash = prediction_run.get("prediction_hash")
        before_prediction_text = fixed_paths["prediction"].read_text(encoding="utf-8") if fixed_paths["prediction"].exists() else ""
        publish_reply = wb.local_agent_reply(
            "发布登记：选题：普通人做内容前如何判断入口，平台抖音，链接 https://v.douyin.com/test123，发布时间 2026-06-22 20:30",
            config,
        )
        publish_artifacts = [Path(item.get("path", "")) for item in publish_reply.get("result", {}).get("artifacts", []) if item.get("type") == "publish_record"]
        publish_ledger = json.loads(fixed_paths["ledger"].read_text(encoding="utf-8")) if fixed_paths["ledger"].exists() else {}
        results.append(expect(publish_reply.get("stage") == "publish_registration" and bool(publish_artifacts) and publish_artifacts[0] == fixed_paths["publish"] and publish_artifacts[0].exists(), "publish:writes-fixed-file", json.dumps(publish_reply, ensure_ascii=False)[:800]))
        results.append(expect(publish_ledger.get("status") == "published" and publish_ledger.get("next_step") == "retro" and "publish_record" in publish_ledger.get("artifacts", {}), "publish:updates-ledger-status", json.dumps(publish_ledger, ensure_ascii=False)[:800]))
        results.append(expect("https://v.douyin.com/test123" in fixed_paths["publish"].read_text(encoding="utf-8") and "2026-06-22 20:30" in fixed_paths["publish"].read_text(encoding="utf-8"), "publish:records-url-time", fixed_paths["publish"].read_text(encoding="utf-8")[:800]))
        retro_reply = wb.local_agent_reply(
            "复盘这个选题：普通人做内容前如何判断入口，播放 10000，点赞 500，评论 80，收藏 120",
            config,
        )
        retro_artifacts = [Path(item.get("path", "")) for item in retro_reply.get("result", {}).get("artifacts", []) if item.get("type") == "retro"]
        after_run = wb.find_latest_workflow_run(flow_id=prediction_run.get("flow_id"))
        retro_ledger = json.loads(fixed_paths["ledger"].read_text(encoding="utf-8")) if fixed_paths["ledger"].exists() else {}
        results.append(expect(after_run.get("prediction_hash") == before_hash and fixed_paths["prediction"].read_text(encoding="utf-8") == before_prediction_text, "retro:does-not-mutate-prediction", str(after_run)))
        results.append(expect(retro_reply.get("stage") == "retro" and bool(retro_artifacts) and retro_artifacts[0] == fixed_paths["retro"] and retro_artifacts[0].exists(), "retro:writes-fixed-file", json.dumps(retro_reply, ensure_ascii=False)[:800]))
        results.append(expect(retro_ledger.get("status") == "retrospected" and retro_ledger.get("next_step") == "review_score_rules" and "retro" in retro_ledger.get("artifacts", {}), "retro:updates-ledger-status", json.dumps(retro_ledger, ensure_ascii=False)[:800]))
        results.append(expect("播放：10000" in fixed_paths["retro"].read_text(encoding="utf-8") and "点赞：500" in fixed_paths["retro"].read_text(encoding="utf-8") and "收藏：120" in fixed_paths["retro"].read_text(encoding="utf-8"), "retro:metrics-recorded", fixed_paths["retro"].read_text(encoding="utf-8")[:800]))
        topic_panel_after_retro = wb.topic_panel_payload(config, flow_id=score_route.get("flow_id", ""), topic="普通人做内容前如何判断入口")
        panel_ledger_after_retro = topic_panel_after_retro.get("ledger", {})
        results.append(expect(panel_ledger_after_retro.get("status") == "retrospected" and panel_ledger_after_retro.get("next_step") == "review_score_rules", "topic-panel:retrospected-status", json.dumps(panel_ledger_after_retro, ensure_ascii=False)[:800]))

        static_text = (APP_ROOT / "static" / "index.html").read_text(encoding="utf-8")
        for token in ["modelStatusText", "modelTestResult", "answer_source", "demoView = false", "stage === \"chat\"", "conversationList", "newConversation", "deleteConversation", "renameConversation", "data-rename-conversation", "activeConversationId", "loadConversations", "leftWorkflowPanel", "spark-row", "spark-index", "spark-title-marquee", "spark-title-track", "spark-title-marquee-scroll", "spark-score-fixed", "spark-delete", "data-delete-spark", "deleteSpark", "/api/inbox/", "topicPanel", "topicStatus", "topicNextStep", "renderTopicLedger", "topicScriptContent", "topicPredictionContent", "topicPublishContent", "topicRetroContent", "loadTopicPanel", "/api/topic"]:
            results.append(expect(token in static_text, f"frontend:{token}", token))
        results.append(expect("当前阶段：" not in static_text, "frontend:no-mechanical-stage-label", "当前阶段 should not be rendered in replies"))
        results.append(expect("模型：" not in static_text and "来源：" not in static_text, "frontend:no-internal-model-note-in-chat", "chat bubbles should not expose llm_note/source diagnostics"))
        results.append(expect('new Set(["manifest", "ledger", "llm_output"])' in static_text, "frontend:hides-technical-artifacts", "chat generated list should hide manifest/ledger/llm_output"))
        for token in ["formatBusinessBriefs", "formatScoreBrief", "formatReviewBrief", "formatPreviewBrief", "business_briefs", "评分标准", "维度分", "发布预测结果", "值得做的理由"]:
            results.append(expect(token in static_text, f"frontend:business-brief:{token}", token))
        results.append(expect("conversation-panel" not in static_text, "frontend:no-center-conversation-panel", "conversation management should live in the left sidebar"))
        left_anchor = static_text.find('id="leftWorkflowPanel"')
        spark_anchor = static_text.find('id="sparkBoard"')
        chat_anchor = static_text.find('class="panel chat-panel"')
        topic_anchor = static_text.find('id="topicPanel"')
        output_anchor = static_text.find('id="outputPanel"')
        results.append(expect(left_anchor >= 0 and spark_anchor > left_anchor and chat_anchor > spark_anchor, "frontend:left-sidebar-conversation-before-chat", f"left={left_anchor}; spark={spark_anchor}; chat={chat_anchor}"))
        results.append(expect(topic_anchor >= 0 and output_anchor > topic_anchor, "frontend:topic-panel-before-output-panel", f"topic={topic_anchor}; output={output_anchor}"))
        removed_subtitles = [
            "别墨迹，把灵感写成可发布内容。",
            "内容形态、平台、赛道、人设都直接在对话里说。",
            "点击素材，会带标签进入对话框。",
            "已生成内容会沉淀在这里。",
            "点选题后显示稿件、预测、发布、复盘。",
            "新建 / 切换 / 删除",
        ]
        leaked_subtitles = [item for item in removed_subtitles if item in static_text]
        results.append(expect(not leaked_subtitles, "frontend:no-extra-subtitle-copy", str(leaked_subtitles)))
        results.append(expect("composerFocused = true;" in static_text and "blur();" not in static_text, "frontend:composer-stays-expanded", "composer should stay open after send"))
        forbidden_frontend_patterns = [
            'if (reply.stage !== "chat") addLocalSpark',
            'addLocalSpark(reply.result.topic',
            '左侧会自动形成火花看板',
        ]
        leaked_frontend_patterns = [item for item in forbidden_frontend_patterns if item in static_text]
        results.append(expect(not leaked_frontend_patterns, "frontend:no-auto-spark-from-chat-or-business-reply", str(leaked_frontend_patterns)))
        results.append(expect('function shouldShowInSparkBoard' in static_text and 'shouldShowInSparkBoard(reply)' in static_text, "frontend:spark-board-explicit-gate", "Spark board writes require explicit gate"))
        results.append(expect('reply.result?.spark_item' in static_text and 'inboxItems = [reply.result.spark_item' in static_text, "frontend:confirmed-spark-item-enters-board", "Confirmed persisted sparks must update inboxItems"))

        prompt_path = APP_ROOT / "prompts" / "content_creator_workflow.md"
        results.append(expect(prompt_path.exists(), "prompt:generic-workflow-file-exists", str(prompt_path)))
        if prompt_path.exists():
            prompt_text = prompt_path.read_text(encoding="utf-8")
            for token in ["需求分类", "火花/灵感", "盲打分", "预测", "拍摄", "发布", "复盘", "不要一条路走到黑", "只执行当前一步"]:
                results.append(expect(token in prompt_text, f"prompt:contains:{token}", token))
            forbidden_tokens = ["C:\\Users\\", "/Users/", "cheat-content"]
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

        executor_config = dict(config)
        executor_config["api_key"] = "SHOULD_NOT_LEAK_EXECUTOR_SECRET"
        executor_config["api_base_url"] = ""
        executor_cases = [
            ("抖音审稿：保证你一定月入十万，加我微信", "douyin_review", "douyin_content_review", "douyin-content-review.md"),
            ("优化开头：普通人做个人IP为什么半途而废", "hook_review", "hook_review", "hook-review.md"),
            ("去AI味：综上所述，因此我们要赋能用户", "humanized_copy", "humanizer", "humanizer.md"),
        ]
        for message, deliverable, skill_name, prompt_file in executor_cases:
            reply = wb.local_agent_reply(message, executor_config)
            meta = reply.get("result", {}).get("skill_meta", {}).get(deliverable, {})
            route = meta.get("skill_route", {})
            run_path_value = meta.get("run_path", "")
            run_path = Path(run_path_value) if run_path_value else Path("__missing_skill_executor_run__")
            run = json.loads(run_path.read_text(encoding="utf-8")) if run_path_value and run_path.exists() and run_path.is_file() else {}
            run_text = json.dumps(run, ensure_ascii=False)
            artifact_paths = [Path(item.get("path", "")) for item in reply.get("result", {}).get("artifacts", []) if item.get("type") == deliverable]
            results.append(expect(route.get("skill") == skill_name and route.get("prompt_file") == prompt_file, f"skill-executor:route:{deliverable}", json.dumps(meta, ensure_ascii=False)[:800]))
            results.append(expect(meta.get("llm_attempted") is True and meta.get("fallback_used") is True and meta.get("output_source") == "local_fallback", f"skill-executor:fallback-visible:{deliverable}", json.dumps(meta, ensure_ascii=False)[:800]))
            results.append(expect(run_path.exists() and run.get("llm_call", {}).get("message_count") == 2 and prompt_file in run_text, f"skill-executor:run-record:{deliverable}", run_text[:800]))
            results.append(expect("SHOULD_NOT_LEAK_EXECUTOR_SECRET" not in run_text and "api_key" not in run_text and "api_base_url" not in run_text, f"skill-executor:no-secret-leak:{deliverable}", run_text[:800]))
            results.append(expect(bool(artifact_paths) and artifact_paths[0].exists() and artifact_paths[0].parent.parent.name.startswith(wb.hashlib.sha256(wb.extract_topic(message).encode("utf-8")).hexdigest()[:12]), f"skill-executor:artifact-written-to-topic:{deliverable}", str(artifact_paths)))

        main_text = MAIN_PATH.read_text(encoding="utf-8")
        architecture_modules = [
            APP_ROOT / "agent" / "intent.py",
            APP_ROOT / "agent" / "state.py",
            APP_ROOT / "agent" / "prompt_builder.py",
            APP_ROOT / "agent" / "skill_registry.py",
            APP_ROOT / "agent" / "skill_executor.py",
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
        for token in ["from agent.prompt_builder", "from agent.state", "from agent.skill_executor", "from model.llm", "from storage.conversations", "from workflow.spark"]:
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
