from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Callable
import urllib.error
import urllib.request

from .translator import TranslationItem, Translator


@dataclass(frozen=True)
class AzureTranslatorLocaleSupport:
    minecraft_locale: str
    azure: str | None
    status: str
    note: str = ""


@dataclass(frozen=True)
class AzureTranslatorLocalePair:
    source: AzureTranslatorLocaleSupport
    target: AzureTranslatorLocaleSupport


_SPECIAL_LOCALE_MAP: dict[str, tuple[str | None, str, str]] = {
    "zh_cn": ("zh-Hans", "supported", ""),
    "zh_tw": ("zh-Hant", "supported", "mapped to traditional Chinese"),
    "zh_hk": ("zh-Hant", "supported", "mapped to traditional Chinese"),
    "pt_br": ("pt", "supported", "mapped to Portuguese"),
    "pt_pt": ("pt-pt", "supported", "mapped to Portuguese (Portugal)"),
}

_UNSUPPORTED_LOCALES: set[str] = {
    "bar",
    "brb",
    "en_ud",
    "enws",
    "fra_de",
    "isv",
    "jbo_en",
    "lol_us",
    "lzh",
    "nah",
    "ovd",
    "qya_aa",
    "rpr",
    "sah_sah",
    "swg",
    "szl",
    "tlh_aa",
    "tok",
    "zlm_arab",
}

_SUPPORTED_LANGUAGE_PREFIXES: set[str] = {
    "ar", "de", "en", "es", "fr", "he", "it", "ja", "ko", "nl", "pl", "pt", "ru", "tr", "uk", "zh",
}


def normalize_azure_base_url(value: str) -> str:
    base = str(value or "").strip().rstrip("/")
    if not base:
        return "https://api.cognitive.microsofttranslator.com"
    if base.endswith("/translate"):
        return base[: -len("/translate")]
    return base


def azure_translator_locale_support(source_locale: str, target_locale: str) -> AzureTranslatorLocalePair:
    return AzureTranslatorLocalePair(
        source=resolve_azure_locale(source_locale),
        target=resolve_azure_locale(target_locale),
    )


def resolve_azure_locale(locale: str) -> AzureTranslatorLocaleSupport:
    normalized = str(locale or "").strip().lower()
    if normalized in _SPECIAL_LOCALE_MAP:
        code, status, note = _SPECIAL_LOCALE_MAP[normalized]
        return AzureTranslatorLocaleSupport(minecraft_locale=normalized, azure=code, status=status, note=note)
    if normalized in _UNSUPPORTED_LOCALES or "_" not in normalized:
        return AzureTranslatorLocaleSupport(minecraft_locale=normalized, azure=None, status="fallback-copy", note="unsupported locale mapping")
    language = normalized.split("_", 1)[0].strip()
    if not language or language not in _SUPPORTED_LANGUAGE_PREFIXES:
        return AzureTranslatorLocaleSupport(minecraft_locale=normalized, azure=None, status="fallback-copy", note="unsupported locale mapping")
    return AzureTranslatorLocaleSupport(minecraft_locale=normalized, azure=language, status="supported", note="")


class AzureTranslatorTranslator(Translator):
    def __init__(
        self,
        source_locale: str,
        target_locale: str,
        api_url: str = "https://api.cognitive.microsofttranslator.com",
        api_key: str = "",
        api_region: str = "",
        request_timeout: float = 10.0,
        request_func: Callable[[str, str, dict[str, str], object, float], Any] | None = None,
    ) -> None:
        self.source_locale = str(source_locale or "en_us").strip().lower()
        self.target_locale = str(target_locale or "zh_cn").strip().lower()
        self.base_url = normalize_azure_base_url(api_url)
        self.api_key = str(api_key or "").strip()
        self.api_region = str(api_region or "").strip()
        self.request_timeout = max(1.0, float(request_timeout or 10.0))
        self.support = azure_translator_locale_support(self.source_locale, self.target_locale)
        self.request_func = request_func or _default_request
        self.failed_items: dict[str, str] = {}

    def translate_batch(self, items: list[TranslationItem]) -> dict[str, str]:
        translations, failed = self.translate_batch_with_failures(items)
        self.failed_items = failed
        return translations

    def translate_batch_with_failures(self, items: list[TranslationItem]) -> tuple[dict[str, str], dict[str, str]]:
        translations: dict[str, str] = {}
        failures: dict[str, str] = {}
        if not items:
            return translations, failures
        if self.support.source.status != "supported" or not self.support.source.azure:
            message = f"unsupported source locale: {self.source_locale}"
            for item in items:
                translations[item.id] = item.text
                failures[item.id] = message
            return translations, failures
        if self.support.target.status != "supported" or not self.support.target.azure:
            message = f"unsupported target locale: {self.target_locale}"
            for item in items:
                translations[item.id] = item.text
                failures[item.id] = message
            return translations, failures
        if not self.api_key:
            message = "API key is required for Azure Translator"
            for item in items:
                translations[item.id] = item.text
                failures[item.id] = message
            return translations, failures

        url = f"{self.base_url}/translate?api-version=3.0&from={self.support.source.azure}&to={self.support.target.azure}"
        headers = {
            "Content-Type": "application/json",
            "Ocp-Apim-Subscription-Key": self.api_key,
        }
        if self.api_region:
            headers["Ocp-Apim-Subscription-Region"] = self.api_region
        payload = [{"Text": item.text} for item in items]
        try:
            data = self.request_func("POST", url, headers, payload, self.request_timeout)
            results = self._extract_translations(data, len(items))
            for item, translated in zip(items, results, strict=False):
                translations[item.id] = translated
        except Exception as exc:  # noqa: BLE001
            message = str(exc)
            for item in items:
                translations[item.id] = item.text
                failures[item.id] = message
        return translations, failures

    def _extract_translations(self, data: Any, expected_count: int) -> list[str]:
        if not isinstance(data, list) or len(data) != expected_count:
            raise RuntimeError("Azure Translator response is invalid")
        results: list[str] = []
        for item in data:
            if not isinstance(item, dict):
                raise RuntimeError("Azure Translator response is invalid")
            translations = item.get("translations")
            if not isinstance(translations, list) or not translations:
                raise RuntimeError("Azure Translator response is invalid")
            first = translations[0]
            if not isinstance(first, dict) or "text" not in first:
                raise RuntimeError("Azure Translator response is invalid")
            results.append(str(first["text"]))
        return results


def _default_request(method: str, url: str, headers: dict[str, str], payload: object, timeout: float) -> Any:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{exc.code} {exc.reason}: {body}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        raise RuntimeError(f"Azure Translator connection failed: {reason}") from exc
