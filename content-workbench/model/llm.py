from __future__ import annotations

import json
import urllib.error
import urllib.request


def call_openai_chat_completion(messages: list[dict], config: dict, temperature: float = 0.7, timeout: int = 60) -> tuple[str, str]:
    api_key = config.get("api_key", "")
    if not api_key:
        return "", "未配置 API Key，使用 Mosmori 本地生成。"
    base_url = (config.get("api_base_url") or "").rstrip("/")
    model = config.get("model") or "gpt-4.1-mini"
    if not base_url:
        return "", "未配置 API Base URL，使用 Mosmori 本地生成。"

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
        return content.strip(), "LLM 调用成功。"
    except urllib.error.HTTPError as exc:
        error_body = ""
        try:
            error_body = exc.read().decode("utf-8", errors="replace").strip()
        except OSError:
            error_body = ""
        detail = f"HTTP {exc.code}"
        if error_body:
            detail += f" {error_body[:300]}"
        return "", f"LLM 调用失败：{detail}。"
    except (urllib.error.URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError) as exc:
        return "", f"LLM 调用失败：{exc}。"
