# Mobile and Cloud Sync Contract

## Purpose

The mini-program is a quick PenMoji inspiration capture surface. It is not the full AI workbench.

Data flow:

```text
Mini-program -> lightweight cloud queue -> desktop workbench -> local inbox/project archive
```

## Inspiration Item

```json
{
  "id": "uuid",
  "user_id": "user-id",
  "type": "text",
  "content": "raw inspiration text",
  "media_url": "",
  "tags": ["topic", "draft"],
  "capture_intent": "collect",
  "target_device_id": "desktop-device-id",
  "created_at": "2026-06-18T12:00:00+08:00",
  "client_created_at": "2026-06-18T12:00:00+08:00",
  "sync_status": "pending",
  "local_path": "",
  "source_url": ""
}
```

Allowed `type` values:

- `text`
- `voice`
- `image`
- `link`
- `video_link`

Allowed `capture_intent` values:

- `collect`: only save it into the desktop inbox.
- `score`: user wants the desktop workbench to score it first.
- `review`: user wants content review first.
- `script`: user likely wants a script next.
- `publish_copy`: user likely wants publish copy next.

Allowed `sync_status` values:

- `pending`: created in mobile/cloud, not pulled by desktop.
- `pulled`: desktop has pulled it into local inbox.
- `archived`: desktop has moved or copied it into a content project archive.
- `processed`: desktop has generated at least one deliverable from it.

Recommended user-facing labels:

- `pending`: 已提交
- `pulled`: 电脑已接收
- `archived`: 已进入项目
- `processed`: 已生成产物

## Cloud API v1

### `POST /api/mobile/inspirations`

Create an inspiration from the mini-program.

Required fields:

- `type`
- `content` or `media_url`

Optional fields:

- `tags`
- `source_url`
- `client_created_at`
- `capture_intent`
- `target_device_id`

### Device binding

The normal user path should be device-code binding, not manual Cloud Base URL editing.

### `POST /api/device/link-code`

Desktop creates a short-lived binding code.

Request:

```json
{
  "device_id": "desktop-device-id",
  "device_name": "desktop-workbench",
  "cloud_base_url": "https://sync.example.com"
}
```

Response includes:

- `link.code`: short code shown on desktop.
- `link.desktop_device_id`: device ID saved by desktop.
- `link.link_url`: QR/deep-link payload for future scan flow.
- `link.expires_at`
- `link.status`: `pending`

### `POST /api/device/link`

Mini-program binds by code.

Request:

```json
{
  "code": "A1B2C3",
  "mobile_device_id": "mobile-device-id",
  "mobile_device_name": "penmoji-miniapp"
}
```

Response includes `desktop_device_id`. The mini-program stores it and sends it as `target_device_id` on future inspirations.

Error responses:

- `404`: device code not found.
- `410`: device code expired.
- `409`: device code exists but is not bindable.

### `GET /api/device/link-status`

Desktop polls by `device_id` or `code` to see whether the mini-program has bound the code.
`link.status` can be `pending`, `linked`, or `expired`.

### `GET /api/mobile/inspirations/status`

Returns recent submitted inspirations and sync status.

### `GET /api/desktop/inspirations/pending`

Desktop client pulls pending inspirations from the cloud queue.

### `POST /api/desktop/inspirations/ack`

Desktop client acknowledges pulled items.

Request:

```json
{
  "ids": ["uuid"]
}
```

### `POST /api/device/link`

Binds a desktop client to the user's account.

### `GET /api/account/subscription`

Returns subscription status for UI display.

## Desktop API v1

### `POST /api/sync/inspirations`

Desktop pulls pending inspirations. In the local scaffold, this endpoint accepts `items` in the request body so the flow can be tested before cloud exists.

Example request:

```json
{
  "items": [
    {
      "type": "text",
      "content": "今天想到一个关于普通人做副业的选题",
      "tags": ["副业", "选题"]
    }
  ]
}
```

The workbench writes pulled items to:

- `%USERPROFILE%\.content-workbench\inbox.jsonl`
- `<content_project_path>\archive\inbox.jsonl` when a project path is configured and writable
