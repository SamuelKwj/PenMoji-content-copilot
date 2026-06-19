# Findings & Decisions

## Product
- Product name: Mosmori.
- Mosmori is a local-first content workbench for creators.
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
