# Content Workbench

Local desktop scaffold for the Content Creator Pipeline product.

This is a Windows-first, local-first workbench. It starts a small HTTP service on `127.0.0.1:7870` and opens a browser UI for:

- Agent chat entry
- API/model configuration
- Inspiration inbox
- Mobile inspiration sync simulation
- Local project file listing
- License status scaffold

## Start

```powershell
cd C:\Users\samue\Documents\内容生产agent\content-workbench
python main.py --host 127.0.0.1 --port 7870
```

Or double-click `run.bat`.

For the full local MVP, including the cloud mock, double-click `run-mvp.bat`.

Then open:

```text
http://127.0.0.1:7870
```

## Optional Cloud Mock

For local MVP testing of the mini-program/cloud queue:

```powershell
python cloud_mock.py --host 127.0.0.1 --port 8787
```

In the workbench config, set:

```text
Cloud Base URL = http://127.0.0.1:8787
```

Then submit mobile-style inspirations to `POST http://127.0.0.1:8787/api/mobile/inspirations` and pull them from the desktop UI.

## Data Location

Runtime data is stored outside this folder:

```text
%USERPROFILE%\.content-workbench
```

This keeps user config, secrets, conversations, and inbox data separate from the installed app so upgrades can preserve them.

The default content project is:

```text
%USERPROFILE%\.content-workbench\projects\default-content-project
```

## Current Scope

This scaffold is intentionally small. It proves the product shell and local data flow before adding:

- Real LLM orchestration
- Real cloud inspiration queue
- Production license server
- Windows service and installer packaging

## API Key Handling

`GET /api/config` returns a masked API key. If the UI posts `********`, the service preserves the existing secret instead of overwriting it.
