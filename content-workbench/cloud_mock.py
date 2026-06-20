from __future__ import annotations

import argparse
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


CLOUD_VERSION = "0.1.0"
DATA_ROOT = Path(os.environ.get("CONTENT_WORKBENCH_CLOUD_HOME", Path.home() / ".content-workbench-cloud"))
QUEUE_PATH = DATA_ROOT / "inspiration_queue.jsonl"
DEVICES_PATH = DATA_ROOT / "devices.jsonl"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def ensure_data_dir() -> None:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    items = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return items


def append_jsonl(path: Path, item: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item, ensure_ascii=False) + "\n")


def rewrite_jsonl(path: Path, items: list[dict]) -> None:
    atomic_write_text(path, "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in items))


def normalize_inspiration(payload: dict) -> dict:
    allowed_types = {"text", "voice", "image", "link", "video_link"}
    item_type = payload.get("type") if payload.get("type") in allowed_types else "text"
    tags = payload.get("tags") if isinstance(payload.get("tags"), list) else []
    return {
        "id": payload.get("id") or str(uuid.uuid4()),
        "user_id": payload.get("user_id") or "demo-user",
        "type": item_type,
        "content": payload.get("content", ""),
        "media_url": payload.get("media_url", ""),
        "tags": tags,
        "created_at": payload.get("created_at") or payload.get("client_created_at") or now_iso(),
        "client_created_at": payload.get("client_created_at", ""),
        "sync_status": "pending",
        "local_path": "",
        "source_url": payload.get("source_url", ""),
        "capture_intent": payload.get("capture_intent", "collect"),
    }


class CloudMockHandler(BaseHTTPRequestHandler):
    server_version = "ContentWorkbenchCloudMock/0.1"

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/status":
            self.send_json({"status": "ok", "version": CLOUD_VERSION, "data_root": str(DATA_ROOT)})
        elif path == "/api/mobile/inspirations/status":
            self.send_json({"items": read_jsonl(QUEUE_PATH)})
        elif path == "/api/desktop/inspirations/pending":
            items = [item for item in read_jsonl(QUEUE_PATH) if item.get("sync_status") == "pending"]
            self.send_json({"items": items})
        elif path == "/api/account/subscription":
            expires_at = (datetime.now(timezone.utc) + timedelta(days=14)).astimezone().isoformat(timespec="seconds")
            self.send_json(
                {
                    "status": "active",
                    "plan": "mvp-trial",
                    "expires_at": expires_at,
                    "offline_grace_days": 7,
                    "last_checked_at": now_iso(),
                }
            )
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            payload = self.read_json_body()
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if path == "/api/mobile/inspirations":
            item = normalize_inspiration(payload)
            if not item.get("content") and not item.get("media_url"):
                self.send_json({"error": "content or media_url is required"}, HTTPStatus.BAD_REQUEST)
                return
            append_jsonl(QUEUE_PATH, item)
            self.send_json({"status": "ok", "item": item}, HTTPStatus.CREATED)
        elif path == "/api/desktop/inspirations/ack":
            ids = set(payload.get("ids") if isinstance(payload.get("ids"), list) else [])
            items = read_jsonl(QUEUE_PATH)
            for item in items:
                if item.get("id") in ids:
                    item["sync_status"] = "pulled"
                    item["pulled_at"] = now_iso()
            rewrite_jsonl(QUEUE_PATH, items)
            self.send_json({"status": "ok", "acked": len(ids)})
        elif path == "/api/device/link":
            device = {
                "device_id": payload.get("device_id") or str(uuid.uuid4()),
                "device_name": payload.get("device_name") or "desktop",
                "linked_at": now_iso(),
            }
            append_jsonl(DEVICES_PATH, device)
            self.send_json({"status": "ok", **device}, HTTPStatus.CREATED)
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON body") from exc
        if not isinstance(data, dict):
            raise ValueError("JSON body must be an object")
        return data

    def send_json(self, data: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, fmt: str, *args: object) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {self.address_string()} {fmt % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Content Workbench cloud mock")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    ensure_data_dir()
    server = ThreadingHTTPServer((args.host, args.port), CloudMockHandler)
    print(f"Content Workbench Cloud Mock {CLOUD_VERSION} running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
