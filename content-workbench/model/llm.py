from __future__ import annotations

import json
import socket
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
        return "", f"模型接口返回错误：{detail}。请检查模型名、API Key、额度或服务商地址。"
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        reason_text = str(reason)
        if "10061" in reason_text or "actively refused" in reason_text.lower() or "积极拒绝" in reason_text:
            return "", f"模型接口连不上：{base_url} 没有可用服务在响应。通常是本地模型/代理服务没启动，或 API Base URL 端口填错。"
        if isinstance(reason, TimeoutError) or "timed out" in reason_text.lower():
            return "", f"模型接口连接超时：{base_url} 响应太慢或网络不可达。请检查网络、代理和 API Base URL。"
        return "", f"模型接口连不上：{reason_text}。请检查 API Base URL、网络或本地模型服务。"
    except socket.timeout:
        return "", f"模型接口连接超时：{base_url} 响应太慢或网络不可达。"
    except (TimeoutError, KeyError, IndexError, json.JSONDecodeError) as exc:
        return "", f"模型返回内容不可用：{exc}。请检查模型是否兼容 OpenAI chat/completions 格式。"
