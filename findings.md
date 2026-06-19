# Findings & Decisions

## Requirements
- Productize the existing `Content Creator Pipeline` as a local-first desktop agent.
- Keep the desktop workbench responsible for heavy workflows:选题验证, 标题, 脚本, 打分, 预测, 发布, 复盘, 文件管理.
- Keep the mini-program narrow: quick inspiration capture and sync to desktop.
- Keep cloud scope light: account, subscription/license, inspiration queue, version metadata.
- Avoid full SaaS generation cost in v1; users bring their own LLM API key.
- Preserve user data across app upgrades.

## Research Findings
- The workspace currently contains `Content Creator Pipeline`, an integrated skill bundle with `SKILL.md`, `README.md`, references, and child skills.
- The bundle documents an independent desktop workbench idea, but there was no actual `main.py`, `static/index.html`, installer, or runnable local service before this pass.
- The product should treat `Content Creator Pipeline` as the source workflow bundle and keep runtime code in a separate `content-workbench/` directory.
- The mini-program should not try to remote-control the computer. A safer v1 flow is: mini-program writes inspiration to cloud queue, desktop pulls it into local inbox.
- The desktop should show real generated file paths whenever pipeline actions create artifacts, because the existing pipeline warns that invented paths are a common failure mode.
- The local MVP now supports artifact-producing chat and inbox flows, not only conversational scaffolding.
- The local cloud mock validates the intended mini-program path without needing a deployed backend yet.
- The target user is a beginner, so the visible desktop surface should feel like a guided script workflow rather than a Hermes-style or developer-style command workbench.
- The product should not offer finished-video generation/export in v1. It should stop at video script, text packs, and static-page copy.
- Generic ideas and "full package" wording should begin at spark solidification only. The assistant should guide the user step by step through review, score, prediction, script, and static/text materials.
- Some old MVP verification records under the runtime data directory still contain phrases like "电脑生成全套". They are historical test data, not current product behavior.
- A Notion/Taskade-style structural redesign was attempted, but the user clarified they wanted UI color/visual/interaction polish, not a functional-block restructure.
- Future UI passes should preserve the current function blocks and improve palette, spacing, visual hierarchy, hover/active states, motion/feedback, and perceived polish.
- Topic text can contain workflow-like words such as `验证`; route intent must prioritize the explicit command prefix (`固化这个灵感`, `审核这个灵感`, etc.) over keywords inside the topic.
- The current accepted UI direction is "fewer entrances, cleaner page": one-time settings live behind a gear button; content positioning is captured through dialogue; the left rail is a scored spark board; the right rail is material selection plus output board.
- Bare content-shape words such as `口播内容` should not route to script generation. Only explicit script intent such as `写视频脚本`, `口播脚本`, or `口播稿` should trigger the video-script step.
- `Content Creator Pipeline/skill` contains 19 child skills. Before Phase 19, several were documented but not exposed in the workbench product flow, including `douyin-content-review`, `dbs-hook`, `humanizer`, `douyin-safe-overlay`, `cheat-shoot`, `cheat-status`, `cheat-trends`, `cheat-recommend`, `cheat-learn-from`, `cheat-persona`, `cheat-bump`, `cheat-init`, and `cheat-migrate`.

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| Use `content-workbench/` for runtime scaffold | Keeps runtime separate from the source skill bundle. |
| Use Python standard library HTTP server for v1 scaffold | Avoids dependency installation and makes first launch easy on Windows. |
| Store runtime data under `%USERPROFILE%\.content-workbench` | Preserves user data across upgrades and avoids writing secrets into repo files. |
| Default content project under `%USERPROFILE%\.content-workbench\projects` | Prevents mobile sync test data from polluting the source skill bundle. |
| Mask API keys on read and preserve existing key when masked value is posted | Prevents UI config saves from overwriting secrets with `********`. |
| Implement mini-program sync as a local API contract plus simulated sync endpoint | Lets desktop flow be tested before real cloud infrastructure exists. |
| Add `cloud_mock.py` for MVP cloud behavior | Proves the mobile queue, desktop pull, ack, device bind, and subscription shape before deploying cloud infrastructure. |
| Persist deliverables under the default content project | Gives users real files to inspect and keeps generated content out of the source skill bundle. |
| Route explicit workflow verbs before generic "灵感" matching | Prevents prompts like "审核这个灵感" from creating both a spark card and review, then looping back to audit. |
| Show Chinese stage labels and next-step buttons in the UI | Keeps the interaction approachable and moves users through the business process without exposing route ids. |
| Hide processed inbox records by default | Prevents old test/history entries from confusing new users on the first screen. |
| Put the guided workflow before settings in the visible layout | Keeps the first interaction focused on business progress rather than configuration. |
| Preserve existing function-block layout for UI polish | The user asked for color/interaction/visual improvements, not structural reorganization. |
| Match explicit route prefixes before generic keyword scanning | Prevents topic content from hijacking the user's selected workflow step. |
| Hide settings behind a gear entry | Model, sync, storage, and license settings are configured rarely and should not occupy constant page space. |
| Move creator positioning into dialogue | Content form, platform, niche, and persona are part of guided context capture, not persistent form fields. |
| Use a scored spark board for the left rail | New inspirations are recurring work items and need quick triage rather than a static settings/sidebar. |
| Use material selection plus output board on the right | Materials can be clicked into the dialogue, while outputs are kept visible as generated assets. |
| Store spark scores in inbox fields | The UI should read `skill_score`, `score_breakdown`, and `score_source`; it should not invent frontend-only scores. |
| Use a local blind-score-compatible adapter for the desktop MVP | The Python workbench cannot spawn Codex Task sub-agents, so v1 writes the same fields with `cheat-score-blind-compatible/local-v0`; a real provider can replace it later. |
| Use flow metadata for demo and spark output grouping | Runtime history is preserved, while the output board can show only the active demo run or selected spark chain. |
| Add a local workflow run ledger before cloud/platform integrations | Prediction, publish registration, and retro can be credible in the MVP without waiting for deployed cloud metrics imports. |
| Treat prediction artifacts as immutable once generated | Publish and retro records reference prediction hashes/paths instead of rewriting prediction content. |
| Use prompt-limited model blind scoring before full sub-agent integration | The product can send only title/body/rubric to an OpenAI-compatible model now, while future Codex Task sub-agent isolation remains the stricter version. |
| Expose every packaged child skill as a workbench route | Prevents bundled skills from becoming dead documentation and keeps product behavior aligned with the integrated pipeline. |
| Add executable compliance tests for skill contracts | Skills are prompt/procedure contracts, so golden and red-team tests are needed to prove the product follows them. |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| Existing pipeline bundle had only documentation for a desktop workbench | Added an executable scaffold under `content-workbench/`. |
| The product scope could drift into heavy SaaS | Locked v1 to local desktop plus light cloud. |
| Mobile scope could drift into full AI workbench | Locked mini-program to inspiration capture and sync. |
| MVP needed real outputs, not only chat replies | Added deliverable markdown generation and manifest files. |
| UI still felt like a developer console after the first MVP | Renamed the product surface to "灵感到脚本", removed the visible Debug tab, changed workspace labels, and added a continue-next-step action. |
| "审核这个灵感" matched both review and spark-card keywords | Changed routing so explicit review/score/prediction/script/static-page requests each produce only the requested current step. |
| Old processed inbox messages still showed "全套" test language | Hid processed inbox items by default and kept only pending/unprocessed inspirations in the main list. |
| Artifact folder names could inherit command prefixes like "全套物料" | Added topic prefix stripping before artifact directory creation. |
| A topic containing `验证` caused the `灵感固化` button to route to review in the old backend | Updated `route_deliverables` so explicit command prefixes choose the step first, restarted the local service, and verified the running API/browser path. |
| UI work drifted into changing the product's functional blocks | Reverted `static/index.html` to the prior function-block layout and documented that future UI work should stay visual/interaction-focused unless structure changes are explicitly requested. |
| Dialogue text containing `口播内容` was routed to video script | Removed bare `口播` from generic script keywords; explicit `口播脚本` and `口播稿` still route to video script. |
| Spark board scores looked like real skill scores even when they were frontend heuristics | Replaced frontend scoring with clickable `待盲评`; scores now come from backend-written score fields. |
| Demo flow could hang when a configured model endpoint was unreachable | Added `force_local` for demo chat calls so presentations use deterministic fallback and finish quickly. |
| Spark score details made the first view too sparse for demos | Changed sparks to compact ranked rows by default, with dimensions and title candidates behind `详情`. |
| Demo data needs to be disposable for repeated presentations | Demo items and artifacts now carry metadata and can be removed with `清理演示`. |
| Old runtime artifacts can pollute a pitch demo | Added demo-view and selected-spark filtering so right-side outputs can stay focused without deleting user history. |
| The workflow previously stopped at generated copy/scripts | Added local publish registration and retro artifacts so a content idea can be followed through after publishing. |
| Local spark scoring did not use a model even when configured | Added a prompt blind-score runner with strict JSON parsing and local fallback. |
| The packaged `douyin-content-review` skill was missed in the product flow | Added `抖音审稿` route and artifact generation, including limit/violation risk checks and playback diagnosis prompts. |
| Local blind-score fallback did not flag contaminated inputs | Compliance harness caught this; blind-score self-check now detects playback/comment/retro signals in both model and fallback paths. |

## Resources
- Existing pipeline root: `C:\Users\samue\Documents\内容生产agent\Content Creator Pipeline`
- Workbench scaffold: `C:\Users\samue\Documents\内容生产agent\content-workbench`
- Cloud mock: `C:\Users\samue\Documents\内容生产agent\content-workbench\cloud_mock.py`
- Mobile/cloud contract: `C:\Users\samue\Documents\内容生产agent\content-workbench\docs\mobile-cloud-contract.md`
- Runtime data root: `%USERPROFILE%\.content-workbench`
- Default content project: `%USERPROFILE%\.content-workbench\projects\default-content-project`

## Visual/Browser Findings
- HTTP check for `http://127.0.0.1:7870/` confirms the page now includes `灵感到脚本`, `引导流程`, and the next-step button code.
- The served page no longer exposes `Agent Chat`, a visible `Debug` tab, `全套物料`, `生成视频`, `导出视频`, or `成片` text in the beginner UI.
- Final runtime check after restarting `7870` confirmed clicking the first workflow step on a topic containing `验证` returns `灵感固化卡` and next step `审核`.
- Restore check confirmed the served HTML contains `引导流程`, `素材与产物`, and `基础设置`, and no longer contains `6 步内容流程`, `灵感库`, or `nextCard`.
- Final clean-entry UI check confirmed `火花看板`, `引导对话`, `素材选择`, `产出看板`, gear settings, Escape close, and material-to-dialogue insertion render/work on desktop/mobile with no console errors.
- Runtime route check confirmed `测试灵感...平台抖音，口播内容` routes to spark solidification, while `写视频脚本...` still routes to video script.
- Spark blind-score check confirmed clicking `待盲评` writes `skill_score`, displays dimension chips, keeps service status untouched, and sorts scored sparks above pending sparks.
- Demo-flow check confirmed one click can produce `灵感固化卡`, `审核结果`, `视频脚本`, `发布文案`, and `静态页文案` in the output board with no browser console errors.
- Demo-polish check confirmed the first view shows more ranked sparks, details are collapsed by default, newly scored sparks auto-expand, and `生成演示样本` provides in-progress/completion feedback.
- Formal demo check confirmed top-bar `演示模式` and `清理演示` can generate and remove demo sparks/artifacts while preserving normal service status.
- Demo-readiness hardening stores manifest summaries in `/api/files`, uses `flow_id`/`flow_topic`/`inbox_id` to group outputs, and labels local-compatible scores as `本地兼容评分`.
- Publish-retro loop check confirmed a single chain can generate `发布预测`, `发布登记`, and `复盘结果` artifacts under one `flow_id`, while the prediction remains hash-locked in `workflow_runs.jsonl`.
- Prompt blind-score runner check confirmed no-key fallback stays local, while an OpenAI-compatible scorer writes `cheat-score-blind-prompt/openai-compatible-v0` with clean rubric dimensions and minimal-input policy metadata.
- Skill coverage integration check confirmed 16 representative missing-skill trigger phrases all route to expected deliverable types and markdown artifacts; the full 19-child-skill coverage table is recorded in `content-workbench/docs/skill-coverage-audit.md`.
- Skill compliance harness now runs 27 checks. It caught and verified the fix for blind-score contamination detection.
