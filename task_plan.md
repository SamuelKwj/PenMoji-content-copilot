# Task Plan: PenMoji Workbench

## Goal
Build PenMoji by Mosmori as a clean local-first content workbench for inspiration capture, scoring, guided dialogue, material selection, output generation, publish registration, and review loops.

## Current Phase
PenMoji Three-End Sync And Device Binding Complete

## Phases

### Phase 1: Local Workbench
- [x] Build the Windows-local browser workbench.
- [x] Keep settings behind the gear entry.
- [x] Keep the accepted layout: left spark board, center dialogue, right materials and output board.
- [x] Preserve material tags, tag deletion, adaptive composer, collapsible rails, demo mode, and output actions.
- **Status:** complete

### Phase 2: Mosmori Business Flow
- [x] Support spark capture, title candidates, scoring, review, video script, publish copy, static-page copy, publish registration, and review results.
- [x] Keep the phone-side mini-program as a lightweight inspiration capture entry.
- [x] Keep the local sync service for end-to-end flow validation.
- [x] Keep BYOK model-provider configuration.
- **Status:** complete

### Phase 3: Mosmori Brand Cleanup
- [x] Create rollback tag `before-mosmori-brand-cleanup`.
- [x] Replace customer-facing product wording with Mosmori.
- [x] Clean README and capability audit docs so they describe product abilities rather than source prompt packs.
- [x] Add branded spark scoring API alias `/api/spark/score`.
- [x] Verify syntax, capability harness, and diff hygiene.
- **Status:** complete

### Phase 4: Full Repository Clean
- [x] Create rollback tag `before-mosmori-full-clean-dark-theme`.
- [x] Scan the full repository for old product names, source-bundle wording, internal prompt-pack names, and open-source exposure.
- [x] Remove the source prompt bundle from the customer-facing repository surface.
- [x] Rename remaining public docs, test harnesses, asset names, and app prefixes to Mosmori wording.
- [x] Keep only compatibility shims where legacy runtime data requires old field names.
- **Status:** complete

### Phase 5: Dark Theme
- [x] Add a polished dark theme for the Mosmori workbench.
- [x] Keep the existing layout and workflow interactions unchanged.
- [x] Persist the selected theme locally.
- [x] Verify desktop and mobile viewports.
- **Status:** complete

### Phase 6: Final Verification
- [x] Run the Mosmori compliance harness.
- [x] Run Python syntax checks.
- [x] Run full brand/source exposure scans.
- [x] Run browser smoke checks.
- [x] Commit only relevant files.
- **Status:** complete

### Phase 7: PenMoji Mobile Capture Polish
- [x] Rename the visible mobile product surface to PenMoji.
- [x] Replace the debug-style form with a quick capture experience.
- [x] Hide Cloud Base URL behind settings.
- [x] Add local draft queue, retry, edit, delete, link detection, tags, and desktop processing intent.
- [x] Preserve `capture_intent` and `client_created_at` through cloud mock and desktop inbox.
- [x] Verify syntax, JSON, compliance harness, and diff hygiene.
- **Status:** complete

### Phase 8: Three-End Sync And Device Binding
- [x] Create rollback tag `before-penmoji-device-binding`.
- [x] Upgrade the local cloud scaffold from a raw mock into a file-backed sync service shape with device binding state.
- [x] Add desktop-side device code / QR-style binding entry and link-status visibility.
- [x] Add mini-program device-code binding so Cloud Base URL is no longer the normal user path.
- [x] Keep the new operations skills out of the main workflow for now; document them as future paid operations update packages.
- [x] Verify Python syntax, mini-program JS/JSON syntax, compliance harness, sync field preservation, and Git diff hygiene.
- **Status:** complete

## Boundaries
- Current product remains local-first; cloud sync and authorization are still simulated locally.
- The workbench does not generate finished video files; it produces scripts, copy, scoring, registration, and review artifacts.
- User data stays outside the install directory under `%USERPROFILE%\.content-workbench`.
- Operations skills such as Douyin hashtag and publish timing advisors are future monetizable update packages, not part of the base workflow in this phase.
