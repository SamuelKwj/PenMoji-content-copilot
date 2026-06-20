# Findings & Decisions

## Product
- Company name: Mosmori.
- Product name: PenMoji.
- PenMoji is a local-first content workbench for creators.
- The desktop workbench is the primary surface for scoring, guided dialogue, scripts, copy, publish registration, and review loops.
- The mini-program remains a lightweight mobile inspiration capture entry.
- Runtime data stays under `%USERPROFILE%\.content-workbench` so upgrades do not overwrite user data.

## Layout
- Keep the accepted three-area workspace:
  - Left: spark board and ranking.
  - Center: guided dialogue.
  - Right: material selection and output board.
- Settings stay behind the top-right gear.
- Material chips must still enter the dialogue and be removable inside the composer.
- Spark and material/output rails remain collapsible and persisted.

## Brand Cleanup
- Public files should use Mosmori only.
- Public docs should describe product capabilities, not source prompt packs.
- Retired source prompt material should not ship in the customer-facing repository surface.
- Internal compatibility shims may read old runtime field names, but new UI, docs, artifacts, and preferred APIs should use Mosmori wording.

## Open-Source Exposure Audit
- No package manager dependency manifest was found for the workbench itself.
- One license file existed only inside the retired source prompt bundle; removing that bundle removes the customer-facing open-source exposure surface from this repo.
- Current workbench runtime uses Python standard library plus browser-native HTML/CSS/JS.

## Theme
- Mosmori now includes a persisted light/dark theme switch.
- The dark theme uses restrained dark surfaces, warm orange action color, and blue service accents.
- The theme switch does not change the accepted left/center/right workbench layout.

## Next Verification
- Run the Mosmori compliance harness.
- Run Python syntax checks.
- Run a full text scan for retired brand/source terms.
- Run browser smoke checks for the light and dark themes.

## PenMoji Mobile Capture
- The mini-program has been polished into a PenMoji quick-capture surface.
- Cloud URL is hidden behind settings, but still exists for local development.
- Mobile submissions can carry `capture_intent` values: `collect`, `score`, `review`, `script`, `publish_copy`.
- `capture_intent` and `client_created_at` are now part of the sync contract and must be preserved by cloud and desktop normalization.

## Operations Update Package Decision
- Newly created Hermes skills such as `douyin-hashtag-advisor` and `douyin-publish-timing-advisor` are operations-oriented capabilities.
- Do not wire these into the base PenMoji workbench yet.
- Treat them as future sellable update packages for operations/growth workflows.

## Next Phase Findings
- The current cloud service is still a local file-backed scaffold, but it can be made more product-like by adding device-code binding and link status.
- The desired user path is desktop shows a binding code/QR-style entry, mobile enters or scans it, and normal users no longer edit Cloud Base URL.

## Device Binding
- Desktop generates a short-lived device code through the sync service.
- Mini-program binding by code stores the desktop device ID locally and attaches it as `target_device_id` on future submissions.
- Desktop cloud pulls filter pending inspirations by `target_device_id`.
- Empty `target_device_id` remains visible to all desktops as a compatibility path for older or unbound mobile submissions.
- Link-code states are `pending`, `linked`, and `expired`; invalid or expired codes should not fall back to direct device registration.
