# Task Plan: Content Creator Agent Productization

## Goal
Turn the existing Content Creator Pipeline skill bundle into a beginner-friendly local script workflow assistant for inspiration capture, spark solidification, review, scoring, prediction, video-script writing, and text/static-page material generation.

## Current Phase
Publish Retro Loop Complete

## Phases

### Phase 1: Product Direction & Scope
- [x] Lock product shape: desktop local agent workbench plus mini-program inspiration entry.
- [x] Define mini-program boundary: quick inspiration capture and sync only, not full AI workbench.
- [x] Define cloud boundary: account, subscription/license, inspiration queue, version metadata.
- [x] Define v1 model-cost boundary: BYOK by default.
- [x] Define production boundary: no video rendering/export; the core output is video scripts plus text/static-page materials.
- **Status:** complete

### Phase 2: Local Desktop Workbench
- [x] Create `content-workbench/`.
- [x] Add a local HTTP service on `127.0.0.1:7870`.
- [x] Add browser UI for chat, config, inbox, files, sync, and license status.
- [x] Persist config, conversations, inbox data, and content projects under `%USERPROFILE%\.content-workbench`.
- [x] Preserve existing secrets when the UI posts masked values.
- **Status:** complete

### Phase 3: Mobile & Cloud Sync MVP
- [x] Define the mini-program inspiration item schema.
- [x] Add a minimal WeChat Mini Program project for mobile inspiration capture.
- [x] Define mobile/cloud API contracts.
- [x] Add a local cloud mock for mobile submission, desktop pull, ack, device binding, and subscription status.
- [x] Add desktop cloud pull from `cloud.base_url`.
- [x] Add `run-mvp.bat` to launch the local desktop workbench and cloud mock together.
- **Status:** complete

### Phase 4: Agent Production MVP
- [x] Add guided workflow routing for spark solidification, review, score, prediction, script, and static-page materials.
- [x] Add OpenAI-compatible LLM orchestration path using saved `api_base_url`, `api_key`, and `model`.
- [x] Keep deterministic local fallback when no API key is configured.
- [x] Generate markdown artifacts for spark cards, review, score, prediction, video scripts, title/publish text, and static-page copy.
- [x] Add inbox-to-workflow action so synced mobile inspirations start at spark solidification.
- [x] Prevent generic ideas and "full package" language from producing all materials at once.
- **Status:** complete

### Phase 5: MVP Verification
- [x] Syntax-check Python services.
- [x] Start desktop and cloud mock services.
- [x] Verify desktop core API endpoints.
- [x] Verify mobile cloud submission -> desktop pull -> cloud ack -> local inbox.
- [x] Verify chat and inbox production create artifact files.
- [x] Verify cloud-backed license status and device binding.
- **Status:** complete

### Phase 6: Beginner Workflow Simplification
- [x] Simplify the UI around "灵感到脚本" instead of a developer-style control console.
- [x] Rename visible workspace concepts to beginner-facing labels: 引导流程、灵感、手机同步、产物.
- [x] Hide developer debug tab from the default UI.
- [x] Show Chinese workflow stage labels instead of raw route ids.
- [x] Add a "继续：下一步" action after each workflow response.
- [x] Ensure explicit review/score/prediction/script requests each produce only that current step.
- **Status:** complete

### Phase 7: Message/UI Cleanup
- [x] Inspect the in-app browser for misleading old MVP/test messages.
- [x] Hide processed inbox history from the default inspiration list.
- [x] Move the guided workflow to the first visible surface in the local browser.
- [x] Strip workflow command prefixes from generated artifact folder names.
- [x] Verify "full package" wording only starts the guided workflow and does not generate all outputs.
- **Status:** complete

### Phase 8: UI Direction Correction
- [x] Revert the mistaken three-column Notion/Taskade workflow-board UI.
- [x] Restore the previous function-block layout: guided workflow, materials/products panel, and settings sidebar.
- [x] Keep the beginner-facing labels and step-by-step reply actions from Phase 6/7.
- [x] Preserve the backend route-priority bug fix so explicit workflow actions are not hijacked by topic keywords.
- [x] Verify the served HTML contains `引导流程`, `素材与产物`, and `基础设置`, and no longer contains `6 步内容流程`, `灵感库`, or `nextCard`.
- **Status:** complete

### Phase 9: Layout Position Adjustment
- [x] Create a Git baseline commit before changing layout.
- [x] Move `基础设置/授权` to the left sidebar.
- [x] Keep `引导流程` in the middle.
- [x] Keep `素材与产物` on the right.
- [x] Verify the actual browser element order is left settings -> middle guide -> right materials.
- **Status:** complete

### Phase 10: Clean Entry UI
- [x] Create rollback tag `before-clean-ui-entry-rework` before the larger UI entry redesign.
- [x] Move one-time settings and authorization behind a top-right gear button.
- [x] Remove persistent content-shape/platform/niche form fields from the visible UI; these are now handled in the guided dialogue copy/chips.
- [x] Replace the left settings rail with a `火花看板` showing incoming sparks with preliminary scores.
- [x] Make the center `引导对话` a fixed full conversation panel.
- [x] Replace the old tabbed materials panel with a `素材选择` list where clicked materials enter the dialogue box.
- [x] Add a right-side `产出看板` for generated local files.
- [x] Verify desktop and mobile UI with Playwright.
- **Status:** complete

### Phase 11: Post-MVP Hardening
- [ ] Replace the local cloud mock with a deployed queue/subscription service.
- [ ] Verify live LLM calls against the user's selected OpenAI-compatible provider and document provider quirks.
- [ ] Add Windows service/installer packaging with upgrade-safe data preservation.
- [ ] Add production license verification, offline token signing, and renewal behavior.
- [ ] Expand router fidelity for blind scoring, prediction immutability, publish registration, and retro flows.
- **Status:** pending

### Phase 12: Spark Blind-Score Demo Flow
- [x] Create rollback tag `before-spark-blind-score-flow`.
- [x] Let each `待盲评` spark be clickable for blind scoring.
- [x] Write `skill_score`, `score_breakdown`, and `score_source` back to inbox/local spark state.
- [x] Sort the spark board by scored items and score.
- [x] Add a demonstrable flow: spark -> blind score -> review -> video script -> publish copy/static copy.
- [x] Verify the browser path and commit only workbench/planning files.
- **Status:** complete

### Phase 13: Demo Mode Polish
- [x] Create rollback tag `before-demo-mode-polish`.
- [x] Make spark cards default to compact ranking rows so more inspirations are visible on first glance.
- [x] Keep score dimensions and title candidates behind a `详情` toggle, with newly scored sparks auto-expanded once.
- [x] Restyle the demo entry as a clear `生成演示样本` action with in-progress and completion feedback.
- [x] Verify compact ranking, detail expansion, blind-score auto expansion, demo flow completion, and browser console health.
- **Status:** complete

### Phase 14: Formal Demo Mode
- [x] Create rollback tag `before-demo-mode-formalize`.
- [x] Move demo generation into the top bar as a formal `演示模式` action.
- [x] Add `清理演示` so demo sparks and demo deliverables can be removed after presentation.
- [x] Mark demo inbox items and demo artifacts with structured metadata.
- [x] Verify demo generation, demo cleanup, output board refresh, service status, and browser console health.
- **Status:** complete

### Phase 15: Adaptive Chat Composer
- [x] Create rollback tag `before-adaptive-composer`.
- [x] Make the chat composer compact by default while browsing.
- [x] Expand the composer on focus, draft input, or selected material.
- [x] Auto-resize the textarea up to a maximum height.
- [x] Collapse the composer after sending or when empty and unfocused.
- [x] Verify focus, typing, blur, send, and console health in the browser.
- **Status:** complete

### Phase 16: Demo Readiness Hardening
- [x] Create rollback tag `before-demo-readiness-hardening`.
- [x] Add artifact flow metadata so generated files can be grouped by demo run or selected spark.
- [x] Keep demo mode visually isolated from old runtime/test artifacts.
- [x] Focus the output board on the selected spark when a fire card is clicked.
- [x] Label local-compatible scoring honestly instead of implying a production blind-score provider.
- [x] Improve title candidates to avoid duplicated "为什么/总是卡住" templates.
- [x] Verify syntax, diff hygiene, browser demo flow, reset safety, and unchanged mini-program dirty files.
- **Status:** complete

### Phase 17: Publish Retro Loop
- [x] Create rollback tag `before-publish-retro-loop`.
- [x] Add local workflow run records for locked predictions.
- [x] Add publish registration API and generated `发布登记` artifacts.
- [x] Add retro API and generated `复盘结果` artifacts.
- [x] Add output-board actions for `发布预测 -> 登记发布 -> 生成复盘`.
- [x] Verify syntax, diff hygiene, API flow, and unchanged mini-program dirty files.
- **Status:** complete

## Key Questions
1. Should the mini-program be a full AI workbench? Answer: no, it is only a quick inspiration capture and sync entry.
2. Should v1 be SaaS-first? Answer: no, v1 is local-first with light cloud for sync and subscription.
3. Who pays LLM inference costs? Answer: v1 defaults to BYOK, so users provide their own OpenAI-compatible API key.
4. Where should user data live? Answer: outside the app folder, under `%USERPROFILE%\.content-workbench`, so upgrades can preserve it.
5. Does the product generate finished video? Answer: no, it stops at video script and text/static-page materials.

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| Local Windows-first script workflow assistant | Matches the desired lightweight local product without taking on heavy SaaS inference cost. |
| Mini-program as inspiration inbox only | Avoids remote-control complexity and keeps mobile UX simple. |
| Light cloud layer only | Keeps operating cost low while still supporting login, subscription, sync, and versioning. |
| BYOK for v1 LLM calls | Avoids taking on model inference cost before the product is validated. |
| Standard-library Python services for MVP | Keeps the local MVP runnable without dependency installation. |
| Store app data in `%USERPROFILE%\.content-workbench` | Keeps user data outside the install directory and safer across upgrades. |
| Default content project under `%USERPROFILE%\.content-workbench\projects` | Keeps user-generated inbox/archive data out of the source skill bundle. |
| Guided workflow instead of multi-button production | The target user is a beginner who needs step-by-step guidance, not a Hermes-style command surface. |
| Video script only, no video rendering/export | The core business is content decisioning and script/static-text production, not finished video generation. |

## Product Risks
| Risk | Mitigation |
|------|------------|
| Live LLM provider behavior is unverified without a real user API key | The OpenAI-compatible code path exists; verify with the user's selected provider during provider setup. |
| Cloud sync currently uses a local mock | Replace it with a deployed queue/subscription service after MVP acceptance. |
| Mini-program has only static/devtool validation | Import `mobile-miniapp/` in WeChat DevTools for real device/devtool acceptance. |
| License behavior is mock-backed | Next pass connects to a production subscription/license backend. |
| Desktop packaging is not implemented | Next pass adds Windows service and installer work. |
| Publish/retro loop is local-only | Keep it local for MVP credibility; later connect metrics import and real platform data. |

## Notes
- The current workbench is an executable local MVP for guided script workflow, not the full commercial product.
- Future work should keep the desktop app as the heavy workflow surface and the mini-program as the light capture surface.
- Do not expand v1 into video rendering/export or a heavy SaaS generation backend unless the product direction changes explicitly.
