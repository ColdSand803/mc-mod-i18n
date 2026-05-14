from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable

from .translator import TranslationItem, Translator


@dataclass(frozen=True)
class DeepFreeLocaleSupport:
    minecraft_locale: str
    google: str | None
    mymemory: str | None
    status: str
    note: str = ""


@dataclass(frozen=True)
class DeepFreeLocalePair:
    source: DeepFreeLocaleSupport
    target: DeepFreeLocaleSupport


_SPECIAL_LOCALE_MAP: dict[str, tuple[str | None, str | None, str, str]] = {
    "zh_cn": ("zh-CN", "zh-CN", "supported", ""),
    "zh_tw": ("zh-TW", "zh-TW", "supported", ""),
    "zh_hk": ("zh-TW", "zh-HK", "supported", "mapped to traditional Chinese"),
    "he_il": ("iw", "he-IL", "supported", "legacy Hebrew code"),
    "fil_ph": ("tl", "fil-PH", "supported", "mapped to Filipino"),
    "nn_no": ("no", "nn-NO", "supported", "mapped to Norwegian Nynorsk"),
}

_MYMEMORY_LANGUAGE_MAP: dict[str, str] = {
    "en": "en-GB",
    "fr": "fr-FR",
    "de": "de-DE",
    "pt": "pt-PT",
    "es": "es-ES",
    "ja": "ja-JP",
    "ko": "ko-KR",
    "ru": "ru-RU",
    "uk": "uk-UA",
    "it": "it-IT",
    "nl": "nl-NL",
    "pl": "pl-PL",
    "tr": "tr-TR",
    "ar": "ar-SA",
    "tl": "tl-PH",
    "fil": "fil-PH",
    "no": "nb-NO",
    "nb": "nb-NO",
    "nn": "nn-NO",
}

_FALLBACK_GOOGLE_PREFIXES: set[str] = {
    "ar", "de", "en", "es", "fil", "fr", "he", "it", "iw", "ja", "ko", "nb", "nl", "nn", "no", "pl", "pt", "ru", "tl", "tr", "uk", "zh",
}

_FALLBACK_MYMEMORY_PREFIXES: set[str] = {
    "ar", "de", "en", "es", "fil", "fr", "he", "it", "nl", "nn", "nb", "no", "pl", "pt", "ru", "tl", "tr", "uk", "zh",
}

_UNSUPPORTED_LOCALES: set[str] = {
    "ast_es",
    "ba_ru",
    "bar",
    "br_fr",
    "brb",
    "en_pt",
    "en_ud",
    "enp",
    "enws",
    "fo_fo",
    "fra_de",
    "gv_im",
    "io_en",
    "isv",
    "jbo_en",
    "ksh",
    "kw_gb",
    "li_li",
    "lol_us",
    "lzh",
    "moh_us",
    "nah",
    "nds_de",
    "oc_fr",
    "ovd",
    "qya_aa",
    "rpr",
    "ry_ua",
    "sah_sah",
    "se_no",
    "swg",
    "sxu",
    "szl",
    "tlh_aa",
    "tok",
    "val_es",
    "vec_it",
    "zlm_arab",
}


def deep_free_locale_support(source_locale: str, target_locale: str) -> DeepFreeLocalePair:
    return DeepFreeLocalePair(
        source=resolve_deep_free_locale(source_locale),
        target=resolve_deep_free_locale(target_locale),
    )


def resolve_deep_free_locale(locale: str) -> DeepFreeLocaleSupport:
    normalized = str(locale or "").strip().lower()
    if normalized in _SPECIAL_LOCALE_MAP:
        google, mymemory, status, note = _SPECIAL_LOCALE_MAP[normalized]
        return DeepFreeLocaleSupport(
            minecraft_locale=normalized,
            google=google,
            mymemory=mymemory,
            status=status,
            note=note,
        )
    if normalized in _UNSUPPORTED_LOCALES or "_" not in normalized:
        return DeepFreeLocaleSupport(
            minecraft_locale=normalized,
            google=None,
            mymemory=None,
            status="fallback-copy",
            note="unsupported locale mapping",
        )
    language = normalized.split("_", 1)[0].strip()
    if not language:
        return DeepFreeLocaleSupport(
            minecraft_locale=normalized,
            google=None,
            mymemory=None,
            status="fallback-copy",
            note="unsupported locale mapping",
        )
    if language not in _supported_google_prefixes() and language not in _supported_mymemory_prefixes():
        return DeepFreeLocaleSupport(
            minecraft_locale=normalized,
            google=None,
            mymemory=None,
            status="fallback-copy",
            note="unsupported locale mapping",
        )
    mymemory = _mymemory_locale_for(normalized, language)
    return DeepFreeLocaleSupport(
        minecraft_locale=normalized,
        google=language,
        mymemory=mymemory,
        status="supported",
        note="",
    )


@lru_cache(maxsize=1)
def _supported_google_prefixes() -> set[str]:
    try:
        from deep_translator import GoogleTranslator  # type: ignore

        codes = GoogleTranslator(source="auto", target="en").get_supported_languages(as_dict=True).values()
        return {str(code).split("-", 1)[0].lower() for code in codes if str(code).strip()}
    except Exception:  # noqa: BLE001
        return set(_FALLBACK_GOOGLE_PREFIXES)


@lru_cache(maxsize=1)
def _supported_mymemory_prefixes() -> set[str]:
    try:
        from deep_translator import MyMemoryTranslator  # type: ignore

        codes = MyMemoryTranslator(source="english us", target="chinese simplified").get_supported_languages(as_dict=True).values()
        return {str(code).split("-", 1)[0].lower() for code in codes if str(code).strip()}
    except Exception:  # noqa: BLE001
        return set(_FALLBACK_MYMEMORY_PREFIXES)


def _mymemory_locale_for(normalized: str, language: str) -> str:
    if normalized == "en_us":
        return "en-US"
    if normalized == "en_gb":
        return "en-GB"
    if normalized == "en_ca":
        return "en-CA"
    if normalized == "en_au":
        return "en-AU"
    if normalized == "fr_ca":
        return "fr-CA"
    if normalized == "fr_fr":
        return "fr-FR"
    if normalized == "de_de":
        return "de-DE"
    if normalized == "pt_br":
        return "pt-BR"
    if normalized == "pt_pt":
        return "pt-PT"
    if normalized == "es_mx":
        return "es-MX"
    if normalized == "es_es":
        return "es-ES"
    if normalized == "ja_jp":
        return "ja-JP"
    if normalized == "ko_kr":
        return "ko-KR"
    if normalized == "ru_ru":
        return "ru-RU"
    if normalized == "uk_ua":
        return "uk-UA"
    if normalized == "it_it":
        return "it-IT"
    if normalized == "nl_nl":
        return "nl-NL"
    if normalized == "pl_pl":
        return "pl-PL"
    if normalized == "tr_tr":
        return "tr-TR"
    if normalized == "ar_sa":
        return "ar-SA"
    return _MYMEMORY_LANGUAGE_MAP.get(language, language)


class DeepFreeTranslator(Translator):
    def __init__(
        self,
        source_locale: str,
        target_locale: str,
        engine_order: list[str] | None = None,
        unsupported_mode: str = "copy",
        request_timeout: float = 10.0,
        engine_factories: dict[str, Callable[[str, str, float], Any]] | None = None,
    ) -> None:
        if unsupported_mode != "copy":
            raise ValueError("deep-free currently supports unsupported_mode='copy' only")
        self.source_locale = str(source_locale or "en_us").strip().lower()
        self.target_locale = str(target_locale or "zh_cn").strip().lower()
        self.engine_order = [engine for engine in (engine_order or ["google", "mymemory"]) if engine in {"google", "mymemory"}]
        if not self.engine_order:
            raise ValueError("deep-free requires at least one engine")
        self.request_timeout = max(1.0, float(request_timeout or 10.0))
        self.support = deep_free_locale_support(self.source_locale, self.target_locale)
        self.engine_factories = dict(engine_factories or {})
        self.failed_items: dict[str, str] = {}
        self._engine_cache: dict[str, Any] = {}
        self._engine_build_count: dict[str, int] = {}

    def translate_batch(self, items: list[TranslationItem]) -> dict[str, str]:
        translations, failed = self.translate_batch_with_failures(items)
        self.failed_items = failed
        return translations

    def translate_batch_with_failures(self, items: list[TranslationItem]) -> tuple[dict[str, str], dict[str, str]]:
        translations: dict[str, str] = {}
        failures: dict[str, str] = {}
        if not items:
            return translations, failures
        if self.support.source.status != "supported":
            message = f"unsupported source locale: {self.source_locale}"
            for item in items:
                translations[item.id] = item.text
                failures[item.id] = message
            return translations, failures
        if self.support.target.status != "supported":
            message = f"unsupported target locale: {self.target_locale}"
            for item in items:
                translations[item.id] = item.text
                failures[item.id] = message
            return translations, failures
        remaining_items = list(items)
        item_errors: dict[str, list[str]] = {item.id: [] for item in items}

        for engine_name in self.engine_order:
            if not remaining_items:
                break
            source_engine_locale = self._source_engine_locale(engine_name)
            target_engine_locale = self._target_engine_locale(engine_name)
            if not source_engine_locale or not target_engine_locale:
                for item in remaining_items:
                    item_errors[item.id].append(f"{engine_name}: unsupported locale mapping")
                continue
            try:
                engine = self._get_engine(engine_name, source_engine_locale, target_engine_locale)
                batch_result = self._translate_with_engine(engine, remaining_items)
            except Exception as exc:  # noqa: BLE001
                for item in remaining_items:
                    item_errors[item.id].append(f"{engine_name}: {exc}")
                continue

            next_remaining: list[TranslationItem] = []
            for item in remaining_items:
                translated = batch_result.get(item.id)
                if translated is None:
                    item_errors[item.id].append(f"{engine_name}: empty result")
                    next_remaining.append(item)
                    continue
                translations[item.id] = translated
            remaining_items = next_remaining

        for item in remaining_items:
            translations[item.id] = item.text
            failures[item.id] = "; ".join(item_errors[item.id]) if item_errors[item.id] else "deep-free: no engine available"
        return translations, failures

    def _source_engine_locale(self, engine_name: str) -> str | None:
        return self.support.source.google if engine_name == "google" else self.support.source.mymemory

    def _target_engine_locale(self, engine_name: str) -> str | None:
        return self.support.target.google if engine_name == "google" else self.support.target.mymemory

    def _get_engine(self, engine_name: str, source_locale: str, target_locale: str) -> Any:
        if engine_name in self._engine_cache:
            return self._engine_cache[engine_name]
        engine = self._build_engine(engine_name, source_locale, target_locale)
        self._engine_cache[engine_name] = engine
        self._engine_build_count[engine_name] = self._engine_build_count.get(engine_name, 0) + 1
        return engine

    def _translate_with_engine(self, engine: Any, items: list[TranslationItem]) -> dict[str, str]:
        texts = [item.text for item in items]
        translate_batch = getattr(engine, "translate_batch", None)
        if callable(translate_batch):
            results = translate_batch(texts)
            if len(results) != len(items):
                raise RuntimeError("translate_batch returned unexpected result count")
            return {item.id: str(result) for item, result in zip(items, results, strict=False)}
        return {item.id: str(engine.translate(item.text)) for item in items}

    def _build_engine(self, engine_name: str, source_locale: str, target_locale: str) -> Any:
        factory = self.engine_factories.get(engine_name)
        if factory:
            return factory(source_locale, target_locale, self.request_timeout)
        if engine_name == "google":
            try:
                from deep_translator import GoogleTranslator  # type: ignore
            except ModuleNotFoundError as exc:
                raise RuntimeError("deep-translator dependency is not installed") from exc
            return GoogleTranslator(source=source_locale, target=target_locale)
        if engine_name == "mymemory":
            try:
                from deep_translator import MyMemoryTranslator  # type: ignore
            except ModuleNotFoundError as exc:
                raise RuntimeError("deep-translator dependency is not installed") from exc
            return MyMemoryTranslator(source=source_locale, target=target_locale)
        raise ValueError(f"unsupported deep-free engine: {engine_name}")
