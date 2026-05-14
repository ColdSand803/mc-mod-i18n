from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .translator import TranslationItem, Translator


@dataclass(frozen=True)
class ArgosLocaleSupport:
    minecraft_locale: str
    argos: str | None
    status: str
    note: str = ""


@dataclass(frozen=True)
class ArgosLocalePair:
    source: ArgosLocaleSupport
    target: ArgosLocaleSupport


_SPECIAL_LOCALE_MAP: dict[str, tuple[str | None, str, str]] = {
    "zh_cn": ("zh", "supported", ""),
    "zh_tw": ("zh", "supported", "mapped to Chinese"),
    "zh_hk": ("zh", "supported", "mapped to Chinese"),
    "pt_br": ("pt", "supported", "mapped to Portuguese"),
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
    "ar", "de", "en", "es", "fr", "it", "ja", "ko", "nl", "pl", "pt", "ru", "tr", "uk", "zh",
}


class ArgosBackend(Protocol):
    def is_available(self) -> bool: ...

    def has_language(self, code: str) -> bool: ...

    def translate_batch(self, source_code: str, target_code: str, texts: list[str]) -> list[str]: ...


def argos_locale_support(source_locale: str, target_locale: str) -> ArgosLocalePair:
    return ArgosLocalePair(
        source=resolve_argos_locale(source_locale),
        target=resolve_argos_locale(target_locale),
    )


def resolve_argos_locale(locale: str) -> ArgosLocaleSupport:
    normalized = str(locale or "").strip().lower()
    if normalized in _SPECIAL_LOCALE_MAP:
        code, status, note = _SPECIAL_LOCALE_MAP[normalized]
        return ArgosLocaleSupport(minecraft_locale=normalized, argos=code, status=status, note=note)
    if normalized in _UNSUPPORTED_LOCALES or "_" not in normalized:
        return ArgosLocaleSupport(minecraft_locale=normalized, argos=None, status="fallback-copy", note="unsupported locale mapping")
    language = normalized.split("_", 1)[0].strip()
    if not language or language not in _SUPPORTED_LANGUAGE_PREFIXES:
        return ArgosLocaleSupport(minecraft_locale=normalized, argos=None, status="fallback-copy", note="unsupported locale mapping")
    return ArgosLocaleSupport(minecraft_locale=normalized, argos=language, status="supported", note="")


class ArgosTranslator(Translator):
    def __init__(
        self,
        source_locale: str,
        target_locale: str,
        backend: ArgosBackend | None = None,
    ) -> None:
        self.source_locale = str(source_locale or "en_us").strip().lower()
        self.target_locale = str(target_locale or "zh_cn").strip().lower()
        self.support = argos_locale_support(self.source_locale, self.target_locale)
        self.backend = backend or ImportArgosBackend()
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
        if self.support.source.status != "supported" or not self.support.source.argos:
            message = f"unsupported source locale: {self.source_locale}"
            for item in items:
                translations[item.id] = item.text
                failures[item.id] = message
            return translations, failures
        if self.support.target.status != "supported" or not self.support.target.argos:
            message = f"unsupported target locale: {self.target_locale}"
            for item in items:
                translations[item.id] = item.text
                failures[item.id] = message
            return translations, failures
        if not self.backend.is_available():
            message = "argostranslate dependency is not installed"
            for item in items:
                translations[item.id] = item.text
                failures[item.id] = message
            return translations, failures
        if not self.backend.has_language(self.support.source.argos):
            message = f"missing Argos language package: {self.support.source.argos}"
            for item in items:
                translations[item.id] = item.text
                failures[item.id] = message
            return translations, failures
        if not self.backend.has_language(self.support.target.argos):
            message = f"missing Argos language package: {self.support.target.argos}"
            for item in items:
                translations[item.id] = item.text
                failures[item.id] = message
            return translations, failures
        try:
            results = self.backend.translate_batch(self.support.source.argos, self.support.target.argos, [item.text for item in items])
            for item, translated in zip(items, results, strict=False):
                translations[item.id] = str(translated)
        except Exception as exc:  # noqa: BLE001
            message = str(exc)
            for item in items:
                translations[item.id] = item.text
                failures[item.id] = message
        return translations, failures


class ImportArgosBackend:
    def __init__(self) -> None:
        try:
            import argostranslate.translate as argos_translate  # type: ignore
        except ModuleNotFoundError:
            self._translate = None
        else:
            self._translate = argos_translate

    def is_available(self) -> bool:
        return self._translate is not None

    def has_language(self, code: str) -> bool:
        if not self._translate:
            return False
        installed = self._translate.get_installed_languages()
        return any(getattr(language, "code", "") == code for language in installed)

    def translate_batch(self, source_code: str, target_code: str, texts: list[str]) -> list[str]:
        if not self._translate:
            raise RuntimeError("argostranslate dependency is not installed")
        installed = self._translate.get_installed_languages()
        source = next((language for language in installed if getattr(language, "code", "") == source_code), None)
        target = next((language for language in installed if getattr(language, "code", "") == target_code), None)
        if source is None or target is None:
            raise RuntimeError("missing Argos language package")
        translation = source.get_translation(target)
        return [str(translation.translate(text)) for text in texts]
