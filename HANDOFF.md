# Handoff: Content Creator Agent Productization

## Current Goal
Build a beginner-friendly local-first content creator agent product from the existing `Content Creator Pipeline` skill bundle.

## Current State
- Project planning files live in `C:\Users\samue\Documents\内容生产agent`.
- A runnable local MVP lives in `content-workbench/`.
- The local desktop workbench is running at `http://127.0.0.1:7870`.
- The local cloud mock is running at `http://127.0.0.1:8787`.
- The default content project path is `%USERPROFILE%\.content-workbench\projects\default-content-project`, not the source skill bundle.
- The first visible desktop/browser surface is now the clean-entry layout: left `火花看板`, center fixed `引导对话`, right `素材选择` plus `产出看板`, with settings hidden behind the top-right gear.
- `content-workbench/main.py` has explicit route-priority handling, and the running `7870` Python process has been restarted so the backend change is live.

## Product Decisions
- Desktop app is the main workflow surface.
- Mini-program is only for quick inspiration capture and sync.
- The product does not render/export finished video.
- The core output is video scripts plus text/static-page materials.
- The desktop conversation should guide beginners step by step: inspiration solidification -> review -> score -> prediction -> video script -> static-page/text materials.
- Cloud is intentionally light: account, subscription/license, inspiration queue, version metadata.
- V1 is BYOK for LLM usage; users provide their own OpenAI-compatible API key.
- Do not build a heavy SaaS generation backend in v1.

## Important Files
- `task_plan.md`: pure product plan and phase status.
- `findings.md`: product facts, decisions, and risks.
- `progress.md`: session log and verification results.
- `content-workbench/main.py`: local desktop HTTP service.
- `content-workbench/cloud_mock.py`: local cloud queue/subscription mock for MVP testing.
- `content-workbench/static/index.html`: browser UI.
- `content-workbench/docs/mobile-cloud-contract.md`: mini-program/cloud sync contract.
- `content-workbench/run-mvp.bat`: one-click local MVP launcher.
- `mobile-miniapp/`: minimal WeChat Mini Program inspiration capture client.

## Implemented MVP
- Desktop workbench with settings, guided workflow, inspiration inbox, artifact files, phone sync, device binding, and license status.
- OpenAI-compatible chat path using saved provider config, with deterministic fallback when no key is configured.
- Workflow router for spark cards, review, score, prediction, video scripts, title/publish text, and static-page copy.
- Local artifact persistence under `%USERPROFILE%\.content-workbench\projects\default-content-project\deliverables`.
- Inbox-to-workflow endpoint and UI action starts at spark solidification instead of producing all materials.
- Generic ideas and "full package" wording now start at spark solidification only; users continue step by step with a `继续：下一步` action.
- Explicit review/score/prediction/script/static-page requests now produce only that current step.
- Visible UI labels are beginner-facing: `灵感到脚本`, `引导流程`, `灵感`, `手机同步`, and `产物`; the default UI no longer shows `Agent Chat` or a visible `Debug` tab.
- The attempted Notion/Taskade six-step workflow-board restructure was reverted after user correction.
- Current accepted direction is fewer entrances and a cleaner page: settings are a gear modal, creator positioning is captured in dialogue, the left rail is a scored spark board, and the right rail is material selection plus output board.
- Default inbox view hides processed items so old test records do not suggest the product still generates "full package" outputs.
- Workflow command prefixes such as `全套物料：` are stripped from generated artifact folder names; artifact paths should name the real topic.
- Backend route priority now treats explicit prompts such as `固化这个灵感：...` as the intended step even when the topic text contains words like `验证`.
- Backend routing no longer treats bare `口播`/`口播内容` as a script request; explicit `写视频脚本`, `口播脚本`, or `口播稿` still route to video script.
- Local cloud mock with mobile submit, desktop pull, ack, device link, and subscription status.
- Minimal WeChat Mini Program client for submitting inspiration and viewing sync status.

## Known Caveats
- Live LLM provider behavior still needs verification with a real user API key.
- The cloud layer is a local mock for MVP validation, not a deployed service.
- The mini-program files passed static checks, but still need import/run acceptance in WeChat DevTools.
- License status can be read from the cloud mock, but no production license server exists yet.
- The router covers MVP script workflow; deeper pipeline operations like blind scoring, prediction immutability, publish registration, and retro still need full integration.

## Verification
- Python syntax check passed for `content-workbench/main.py` and `content-workbench/cloud_mock.py`.
- `GET /api/status` returned `status=ok`, version `0.1.0`, and the configured project path.
- `POST /api/chat` now starts generic ideas at spark solidification and does not directly generate video/export assets.
- `POST /api/chat` with `全套物料：普通人为什么做个人IP总是半途而废` returns only `spark_card`, next step `审核`, and the generated path no longer contains `全套物料`.
- Route matrix passed: generic/full/review/score/prediction/script/static-page requests each advance one workflow step at a time.
- `POST /api/inbox/produce` with `固化灵感` processed an inbox item at `spark_solidify` only, created artifact files, and returned next step `审核`.
- Cloud mock flow passed: mobile submit -> desktop pull -> cloud ack -> local inbox -> local deliverable.
- `GET /api/license/status` returned `active` from the cloud mock.
- `POST /api/cloud/link-device` saved the returned `device_id` into desktop config.
- `GET /` returned status `200` and the expected `灵感到脚本` title.
- Served HTML contains `灵感到脚本`, `引导流程`, and next-step button code; it does not expose visible `Agent Chat`, `Debug`, `全套物料`, `生成视频`, `导出视频`, or `成片` text.
- Restore check confirmed the served HTML contains `引导流程`, `素材与产物`, and `基础设置`, and no longer contains `6 步内容流程`, `灵感库`, or `nextCard`.
- Direct Python route verification confirmed `固化这个灵感：验证选题...` returns `spark_solidify`/`spark_card`, while review/score/full-package prompts route correctly.
- Runtime HTTP route verification confirmed the running `7870` service routes `固化这个灵感：验证选题...` to `spark_solidify`/`spark_card`, and the browser click path returns `灵感固化卡` with next step `审核`.
- Clean-entry UI verification confirmed `火花看板`, `引导对话`, `素材选择`, `产出看板`, gear settings, Escape close, and material-to-dialogue insertion render/work on desktop/mobile with no console errors.
- Runtime HTTP route verification confirmed `测试灵感...平台抖音，口播内容` routes to `spark_solidify`/`spark_card`, while `写视频脚本...` routes to `video_script`.
- Playwright verified clicking a material card inserts that material into the dialogue input.
- Mini-program JSON parsed successfully and mini-program JS passed `node --check`.

## Next Steps
1. Test the OpenAI-compatible LLM path with the user's real provider/API key.
2. Import `mobile-miniapp/` in WeChat DevTools and test against the local cloud mock or a deployed HTTPS endpoint.
3. Replace `cloud_mock.py` with a deployed queue/subscription service.
4. Add production subscription/license token verification and renewal.
5. Add Windows service/installer packaging and upgrade-safe data preservation.
6. Expand router fidelity for blind scoring, prediction immutability, publish registration, and retro.

## Tooling Note
- `planning-with-files` is installed at `C:\Users\samue\.codex\skills\planning-with-files`, but it is environment tooling only and not part of the product plan.
- Restart Codex if the skill is not visible in the active skill list.
