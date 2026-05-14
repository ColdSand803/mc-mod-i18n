from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Callable
import urllib.error
import urllib.request

from .translator import TranslationItem, Translator


@dataclass(frozen=True)
class LibreTranslateLocaleSupport:
    minecraft_locale: str
    libre: str | None
    status: str
    note: str = ""


@dataclass(frozen=True)
class LibreTranslateLocalePair:
    source: LibreTranslateLocaleSupport
    target: LibreTranslateLocaleSupport


_SPECIAL_LOCALE_MAP: dict[str, tuple[str | None, str, str]] = {
    "zh_cn": ("zh", "supported", ""),
    "zh_tw": ("zt", "supported", "mapped to traditional Chinese"),
    "zh_hk": ("zt", "supported", "mapped to traditional Chinese"),
    "pt_br": ("pb", "supported", "mapped to Brazilian Portuguese"),
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
    "ar", "de", "en", "es", "fr", "ga", "he", "hi", "it", "ja", "ko", "nl", "pl", "pt", "ru", "tr", "uk", "zh",
}


def normalize_libretranslate_base_url(value: str) -> str:
    base = str(value or "").strip().rstrip("/")
    if not base:
        return "http://127.0.0.1:5000"
    if base.endswith("/translate"):
        return base[: -len("/translate")]
    if base.endswith("/languages"):
        return base[: -len("/languages")]
    return base


def libretranslate_locale_support(source_locale: str, target_locale: str) -> LibreTranslateLocalePair:
    return LibreTranslateLocalePair(
        source=resolve_libretranslate_locale(source_locale),
        target=resolve_libretranslate_locale(target_locale),
    )


def resolve_libretranslate_locale(locale: str) -> LibreTranslateLocaleSupport:
    normalized = str(locale or "").strip().lower()
    if normalized in _SPECIAL_LOCALE_MAP:
        libre, status, note = _SPECIAL_LOCALE_MAP[normalized]
        return LibreTranslateLocaleSupport(minecraft_locale=normalized, libre=libre, status=status, note=note)
    if normalized in _UNSUPPORTED_LOCALES or "_" not in normalized:
        return LibreTranslateLocaleSupport(minecraft_locale=normalized, libre=None, status="fallback-copy", note="unsupported locale mapping")
    language = normalized.split("_", 1)[0].strip()
    if not language or language not in _SUPPORTED_LANGUAGE_PREFIXES:
        return LibreTranslateLocaleSupport(minecraft_locale=normalized, libre=None, status="fallback-copy", note="unsupported locale mapping")
    return LibreTranslateLocaleSupport(minecraft_locale=normalized, libre=language, status="supported", note="")


class LibreTranslateTranslator(Translator):
    def __init__(
        self,
        source_locale: str,
        target_locale: str,
        api_url: str = "http://127.0.0.1:5000",
        api_key: str = "",
        request_timeout: float = 10.0,
        request_func: Callable[[str, str, dict[str, object], float], Any] | None = None,
    ) -> None:
        self.source_locale = str(source_locale or "en_us").strip().lower()
        self.target_locale = str(target_locale or "zh_cn").strip().lower()
        self.base_url = normalize_libretranslate_base_url(api_url)
        self.api_key = str(api_key or "").strip()
        self.request_timeout = max(1.0, float(request_timeout or 10.0))
        self.support = libretranslate_locale_support(self.source_locale, self.target_locale)
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
        if self.support.source.status != "supported" or not self.support.source.libre:
            message = f"unsupported source locale: {self.source_locale}"
            for item in items:
                translations[item.id] = item.text
                failures[item.id] = message
            return translations, failures
        if self.support.target.status != "supported" or not self.support.target.libre:
            message = f"unsupported target locale: {self.target_locale}"
            for item in items:
                translations[item.id] = item.text
                failures[item.id] = message
            return translations, failures

        try:
            languages = self._fetch_languages()
        except Exception as exc:  # noqa: BLE001
            message = str(exc)
            for item in items:
                translations[item.id] = item.text
                failures[item.id] = message
            return translations, failures
        if not self._language_pair_supported(languages):
            message = f"unsupported target locale: {self.target_locale}"
            for item in items:
                translations[item.id] = item.text
                failures[item.id] = message
            return translations, failures

        payload: dict[str, object] = {
            "q": [item.text for item in items],
            "source": self.support.source.libre,
            "target": self.support.target.libre,
            "format": "text",
        }
        if self.api_key:
            payload["api_key"] = self.api_key
        try:
            data = self.request_func("POST", f"{self.base_url}/translate", payload, self.request_timeout)
            results = self._extract_translations(data, len(items))
            for item, translated in zip(items, results, strict=False):
                translations[item.id] = translated
        except Exception as exc:  # noqa: BLE001
            message = str(exc)
            for item in items:
                translations[item.id] = item.text
                failures[item.id] = message
        return translations, failures

    def _fetch_languages(self) -> list[dict[str, object]]:
        data = self.request_func("GET", f"{self.base_url}/languages", {}, self.request_timeout)
        if not isinstance(data, list):
            raise RuntimeError("LibreTranslate /languages response is invalid")
        return [item for item in data if isinstance(item, dict)]

    def _language_pair_supported(self, languages: list[dict[str, object]]) -> bool:
        source = self.support.source.libre
        target = self.support.target.libre
        for item in languages:
            code = str(item.get("code", "")).strip()
            if code != source:
                continue
            targets = item.get("targets")
            if isinstance(targets, list) and targets:
                return target in {str(value).strip() for value in targets}
            return True
        return False

    def _extract_translations(self, data: Any, expected_count: int) -> list[str]:
        if isinstance(data, dict) and data.get("error"):
            raise RuntimeError(str(data.get("error")))
        if isinstance(data, dict):
            translated = data.get("translatedText")
            if isinstance(translated, list) and len(translated) == expected_count:
                return [str(item) for item in translated]
            if isinstance(translated, str) and expected_count == 1:
                return [translated]
        raise RuntimeError("LibreTranslate translate response is invalid")


def _default_request(method: str, url: str, payload: dict[str, object], timeout: float) -> Any:
    headers = {"Content-Type": "application/json"}
    data = None if method == "GET" else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            raise RuntimeError(f"LibreTranslate HTTP {exc.code}: {body}") from exc
        raise RuntimeError(str(data.get("error") or f"LibreTranslate HTTP {exc.code}")) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        raise RuntimeError(f"LibreTranslate connection failed: {reason}") from exc
