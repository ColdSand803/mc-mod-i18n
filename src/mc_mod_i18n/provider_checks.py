from __future__ import annotations

import json
import os
import re
import time
from typing import Any
import urllib.error
from urllib.parse import urlparse
import urllib.request

from .argos_adapter import ArgosTranslator
from .azure_translator_adapter import AzureTranslatorTranslator
from .deep_translator_adapter import DeepFreeTranslator
from .libretranslate_adapter import LibreTranslateTranslator
from .translator import TranslationItem, get_provider_preset


def normalize_models_url(base_url: str, provider: str) -> str:
    preset = get_provider_preset(provider)
    raw = str(base_url or preset.api_url).strip() or preset.api_url
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("BaseURL 必须是 http 或 https URL")
    path = parsed.path.rstrip("/")
    for suffix in ("/chat/completions", "/responses", "/messages"):
        if path.endswith(suffix):
            path = path[: -len(suffix)]
            break
    if path.endswith("/models"):
        models_path = path
    elif path in ("", "/"):
        models_path = "/v1/models"
    else:
        models_path = f"{path}/models"
    return parsed._replace(path=models_path, params="", query="", fragment="").geturl()


def fetch_provider_models(provider: str, base_url: str, api_key: str, api_key_env: str, timeout: float) -> list[dict[str, str]]:
    key = api_key or os.environ.get(api_key_env, "")
    if not key:
        raise RuntimeError(f"API Key 未填写，且环境变量 {api_key_env} 未设置")
    models_url = normalize_models_url(base_url, provider)
    headers = {"Content-Type": "application/json"}
    if provider == "anthropic-compatible":
        headers.update({"x-api-key": key, "anthropic-version": "2023-06-01"})
    else:
        headers["Authorization"] = f"Bearer {key}"
    request = urllib.request.Request(models_url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_text = response.read().decode("utf-8")
    except urllib.error.HTTPError:
        raise
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        raise RuntimeError(f"模型列表连接失败：{reason}") from exc
    return parse_models_response(response_text)


def deep_free_smoke_test(timeout: float = 10.0) -> dict[str, Any]:
    started_at = time.perf_counter()
    translator = DeepFreeTranslator(
        source_locale="en_us",
        target_locale="zh_cn",
        request_timeout=max(1.0, min(60.0, float(timeout or 10.0))),
    )
    item = TranslationItem(id="probe", key="probe", text="Hello world", mod_id="system")
    translations, failures = translator.translate_batch_with_failures([item])
    message = failures.get("probe")
    translated = translations.get("probe", "")
    if not message and translated:
        return {
            "ok": True,
            "provider": "deep-free",
            "model": "deep-free",
            "latency_ms": elapsed_ms(started_at),
            "message": "连接正常",
        }
    return {
        "ok": False,
        "provider": "deep-free",
        "model": "deep-free",
        "error_type": "network" if message else "unknown",
        "latency_ms": elapsed_ms(started_at),
        "message": message or "deep-free smoke test failed",
    }


def argos_smoke_test(timeout: float = 10.0) -> dict[str, Any]:
    started_at = time.perf_counter()
    translator = ArgosTranslator(
        source_locale="en_us",
        target_locale="zh_cn",
    )
    item = TranslationItem(id="probe", key="probe", text="Hello world", mod_id="system")
    translations, failures = translator.translate_batch_with_failures([item])
    message = failures.get("probe")
    translated = translations.get("probe", "")
    if not message and translated:
        return {
            "ok": True,
            "provider": "argos",
            "model": "argos",
            "latency_ms": elapsed_ms(started_at),
            "message": "连接正常",
        }
    lowered = str(message or "").lower()
    error_type = "runtime"
    if "dependency is not installed" in lowered:
        error_type = "missing_dependency"
    elif "missing argos language package" in lowered:
        error_type = "missing_package"
    return {
        "ok": False,
        "provider": "argos",
        "model": "argos",
        "error_type": error_type,
        "latency_ms": elapsed_ms(started_at),
        "message": message or "argos smoke test failed",
    }


def libretranslate_smoke_test(base_url: str, api_key: str, timeout: float = 10.0) -> dict[str, Any]:
    started_at = time.perf_counter()
    translator = LibreTranslateTranslator(
        source_locale="en_us",
        target_locale="zh_cn",
        api_url=base_url or "http://127.0.0.1:5000",
        api_key=api_key,
        request_timeout=max(1.0, min(60.0, float(timeout or 10.0))),
    )
    item = TranslationItem(id="probe", key="probe", text="Hello world", mod_id="system")
    translations, failures = translator.translate_batch_with_failures([item])
    message = failures.get("probe")
    translated = translations.get("probe", "")
    if not message and translated:
        return {
            "ok": True,
            "provider": "libretranslate",
            "model": "libretranslate",
            "latency_ms": elapsed_ms(started_at),
            "message": "连接正常",
        }
    failure_message = message or "libretranslate smoke test failed"
    lowered = failure_message.lower()
    error_type = "network"
    if "unauthorized" in lowered or "forbidden" in lowered or "api key" in lowered:
        error_type = "auth"
    return {
        "ok": False,
        "provider": "libretranslate",
        "model": "libretranslate",
        "error_type": error_type,
        "latency_ms": elapsed_ms(started_at),
        "message": failure_message,
    }


def azure_translator_smoke_test(base_url: str, api_key: str, api_region: str, timeout: float = 10.0) -> dict[str, Any]:
    started_at = time.perf_counter()
    translator = AzureTranslatorTranslator(
        source_locale="en_us",
        target_locale="zh_cn",
        api_url=base_url or "https://api.cognitive.microsofttranslator.com",
        api_key=api_key,
        api_region=api_region,
        request_timeout=max(1.0, min(60.0, float(timeout or 10.0))),
    )
    item = TranslationItem(id="probe", key="probe", text="Hello world", mod_id="system")
    translations, failures = translator.translate_batch_with_failures([item])
    message = failures.get("probe")
    translated = translations.get("probe", "")
    if not message and translated:
        return {
            "ok": True,
            "provider": "azure-translator",
            "model": "azure-translator",
            "latency_ms": elapsed_ms(started_at),
            "message": "连接正常",
        }
    lowered = str(message or "").lower()
    error_type = "runtime"
    if "api key is required" in lowered or "401" in lowered or "403" in lowered:
        error_type = "auth"
    return {
        "ok": False,
        "provider": "azure-translator",
        "model": "azure-translator",
        "error_type": error_type,
        "latency_ms": elapsed_ms(started_at),
        "message": message or "azure translator smoke test failed",
    }


def provider_test_error(
    provider: str,
    model: str,
    error_type: str,
    message: str,
    started_at: float,
    secret: str = "",
    status_code: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "provider": provider,
        "model": model,
        "error_type": error_type,
        "latency_ms": elapsed_ms(started_at),
        "message": redact_secret(message, secret),
    }
    if status_code is not None:
        payload["status_code"] = status_code
    return payload


def elapsed_ms(started_at: float) -> int:
    return max(0, int((time.perf_counter() - started_at) * 1000))


def redact_secret(text: str, secret: str) -> str:
    redacted = str(text or "")
    if secret:
        redacted = redacted.replace(secret, "[redacted]")
    redacted = re.sub(r"sk-[A-Za-z0-9._-]+", "[redacted]", redacted)
    redacted = re.sub(r"sk-ant-[A-Za-z0-9._-]+", "[redacted]", redacted)
    return redacted


def provider_http_error_type(status_code: int) -> str:
    if status_code in {401, 403}:
        return "auth"
    if status_code == 404:
        return "not_found"
    if status_code == 429:
        return "rate_limited"
    return "http_error"


def provider_http_error_message(status_code: int, body: str) -> str:
    if status_code in {401, 403}:
        return f"认证失败：HTTP {status_code}"
    if status_code == 404:
        return f"接口地址不可用：HTTP 404。请检查 BaseURL 路径。"
    if status_code == 429:
        return "请求被限流：HTTP 429。请稍后重试或降低并发。"
    preview = str(body or "").strip()[:180]
    return f"请求失败：HTTP {status_code}" + (f": {preview}" if preview else "")


def provider_runtime_error_type(message: str) -> str:
    if "返回格式无法识别" in message:
        return "bad_response"
    if "API Key 未填写" in message:
        return "missing_key"
    if "连接失败" in message:
        return "network"
    return "request_failed"


def provider_test_help_slug(payload: dict[str, Any]) -> str:
    if not isinstance(payload, dict) or payload.get("ok"):
        return ""
    provider_name = str(payload.get("provider", "") or "")
    error_type = str(payload.get("error_type", "") or "").lower()
    if provider_name == "argos" and error_type in {"missing_dependency", "missing_package"}:
        return "providers"
    if error_type in {"auth", "model_not_found"}:
        return "providers"
    if provider_name == "deep-free" and error_type == "network":
        return "faq"
    if provider_name == "libretranslate" and error_type == "network":
        return "providers"
    if provider_name == "azure-translator" and error_type == "runtime":
        return "providers"
    return "faq"


def parse_models_response(response_text: str) -> list[dict[str, str]]:
    try:
        data = json.loads(response_text)
    except json.JSONDecodeError as exc:
        preview = response_text[:180].replace("\n", "\\n")
        raise RuntimeError(f"模型列表返回格式无法识别：{preview}") from exc
    raw_models: Any
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        raw_models = data["data"]
    elif isinstance(data, dict) and isinstance(data.get("models"), list):
        raw_models = data["models"]
    elif isinstance(data, list):
        raw_models = data
    else:
        raise RuntimeError("模型列表返回格式无法识别")
    models: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in raw_models:
        if isinstance(item, str):
            model_id = item
            label = item
        elif isinstance(item, dict):
            model_id = str(item.get("id") or item.get("name") or "").strip()
            label = str(item.get("display_name") or item.get("label") or model_id).strip()
        else:
            continue
        if not model_id or model_id in seen:
            continue
        seen.add(model_id)
        models.append({"id": model_id, "label": label or model_id})
    return models


def _test_provider_connection(
    provider: str,
    api_url: str,
    api_key: str,
    api_key_env: str,
    model: str,
    timeout: float = 10.0,
    api_region: str = "",
    *,
    azure_smoke_test=None,
    argos_smoke_test_func=None,
    deep_free_smoke_test_func=None,
    libretranslate_smoke_test_func=None,
    fetch_models_func=None,
    provider_test_error_func=None,
    elapsed_ms_func=None,
    provider_http_error_type_func=None,
    provider_http_error_message_func=None,
    provider_runtime_error_type_func=None,
) -> dict[str, Any]:
    azure_smoke_test = azure_smoke_test or azure_translator_smoke_test
    argos_smoke_test_func = argos_smoke_test_func or argos_smoke_test
    deep_free_smoke_test_func = deep_free_smoke_test_func or deep_free_smoke_test
    libretranslate_smoke_test_func = libretranslate_smoke_test_func or libretranslate_smoke_test
    fetch_models_func = fetch_models_func or fetch_provider_models
    provider_test_error_func = provider_test_error_func or provider_test_error
    elapsed_ms_func = elapsed_ms_func or elapsed_ms
    provider_http_error_type_func = provider_http_error_type_func or provider_http_error_type
    provider_http_error_message_func = provider_http_error_message_func or provider_http_error_message
    provider_runtime_error_type_func = provider_runtime_error_type_func or provider_runtime_error_type

    started_at = time.perf_counter()
    if provider == "azure-translator":
        return azure_smoke_test(api_url, api_key, api_region, timeout)
    if provider == "argos":
        return argos_smoke_test_func(timeout)
    if provider == "deep-free":
        return deep_free_smoke_test_func(timeout)
    if provider == "libretranslate":
        return libretranslate_smoke_test_func(api_url, api_key, timeout)
    key = api_key or os.environ.get(api_key_env, "")
    if not key:
        return provider_test_error_func(
            provider=provider,
            model=model,
            error_type="missing_key",
            message=f"API Key 未填写，且环境变量 {api_key_env} 未设置",
            started_at=started_at,
            secret=api_key,
        )
    try:
        models = fetch_models_func(provider, api_url, api_key, api_key_env, timeout)
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
        finally:
            exc.close()
        return provider_test_error_func(
            provider=provider,
            model=model,
            error_type=provider_http_error_type_func(exc.code),
            message=provider_http_error_message_func(exc.code, body),
            started_at=started_at,
            secret=key,
            status_code=exc.code,
        )
    except RuntimeError as exc:
        return provider_test_error_func(
            provider=provider,
            model=model,
            error_type=provider_runtime_error_type_func(str(exc)),
            message=str(exc),
            started_at=started_at,
            secret=key,
        )
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        return provider_test_error_func(
            provider=provider,
            model=model,
            error_type="network",
            message=f"网络连接失败：{reason}",
            started_at=started_at,
            secret=key,
        )
    model_ids = {item["id"] for item in models}
    if model and model_ids and model not in model_ids:
        return provider_test_error_func(
            provider=provider,
            model=model,
            error_type="model_not_found",
            message=f"连接正常，但模型列表中没有 {model}",
            started_at=started_at,
            secret=key,
        )
    return {
        "ok": True,
        "provider": provider,
        "model": model,
        "latency_ms": elapsed_ms_func(started_at),
        "message": "连接正常",
    }


def test_provider_connection(
    provider: str,
    api_url: str,
    api_key: str,
    api_key_env: str,
    model: str,
    timeout: float = 10.0,
    api_region: str = "",
) -> dict[str, Any]:
    return _test_provider_connection(provider, api_url, api_key, api_key_env, model, timeout, api_region)
