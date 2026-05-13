from __future__ import annotations

from dataclasses import dataclass
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
    "zh_hk": ("zh-TW", "zh-TW", "supported", "mapped to traditional Chinese"),
    "he_il": ("iw", "iw", "supported", "legacy Hebrew code"),
    "fil_ph": ("tl", "tl", "supported", "mapped to Tagalog"),
    "nn_no": ("no", "no", "supported", "mapped to Norwegian"),
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
    return DeepFreeLocaleSupport(
        minecraft_locale=normalized,
        google=language,
        mymemory=language,
        status="supported",
        note="",
    )


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

        for item in items:
            translated = None
            engine_errors: list[str] = []
            for engine_name in self.engine_order:
                source_engine_locale = self._source_engine_locale(engine_name)
                target_engine_locale = self._target_engine_locale(engine_name)
                if not source_engine_locale or not target_engine_locale:
                    engine_errors.append(f"{engine_name}: unsupported locale mapping")
                    continue
                try:
                    engine = self._build_engine(engine_name, source_engine_locale, target_engine_locale)
                    translated = str(engine.translate(item.text))
                    break
                except Exception as exc:  # noqa: BLE001
                    engine_errors.append(f"{engine_name}: {exc}")
            if translated is None:
                translations[item.id] = item.text
                failures[item.id] = "; ".join(engine_errors) if engine_errors else "deep-free: no engine available"
            else:
                translations[item.id] = translated
        return translations, failures

    def _source_engine_locale(self, engine_name: str) -> str | None:
        return self.support.source.google if engine_name == "google" else self.support.source.mymemory

    def _target_engine_locale(self, engine_name: str) -> str | None:
        return self.support.target.google if engine_name == "google" else self.support.target.mymemory

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
