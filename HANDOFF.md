# Mosmori Handoff

## Current Goal
Prepare Mosmori for customer-facing local testing: clean brand surface, remove retired source material from the repository, preserve the accepted workbench layout, and add a polished dark theme.

## Current State
- Branch: `end`
- Rollback tag: `before-mosmori-full-clean-dark-theme`
- Last stable commit before this pass: `729b27e brand: clean Mosmori product wording`
- Main app: `content-workbench/`
- Mobile capture entry: `mobile-miniapp/`

## Workbench Flow
- Left: spark board.
- Center: guided dialogue.
- Right: material selection and output board.
- Settings: top-right gear.
- Demo mode and cleanup remain in the top bar.

## Verification Checklist
- Start workbench: `python content-workbench\main.py --host 127.0.0.1 --port 7870`
- Open: `http://127.0.0.1:7870`
- Validate:
  - Mosmori brand visible in title/header.
  - Spark scoring works.
  - Material tags can be added and removed.
  - Composer expands while typing and collapses after send.
  - Left and right rails collapse and restore.
  - Dark theme renders cleanly after theme switch.
  - Demo mode still produces the sample chain.

## Data Safety
- Runtime data is stored under `%USERPROFILE%\.content-workbench`.
- Source code changes should not delete user runtime data.
- The rollback tag can restore the pre-cleanup repository state.
