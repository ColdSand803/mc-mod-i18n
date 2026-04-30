from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
import urllib.error
import urllib.request


@dataclass(frozen=True)
class TranslationItem:
    id: str
    key: str
    text: str
    mod_id: str


class Translator:
    def translate_batch(self, items: list[TranslationItem]) -> dict[str, str]:
        raise NotImplementedError


class CopyTranslator(Translator):
    def translate_batch(self, items: list[TranslationItem]) -> dict[str, str]:
        return {item.id: item.text for item in items}


class GlossaryTranslator(Translator):
    BUILTIN_GLOSSARY = {
        "Advanced": "高级",
        "Amethyst": "紫水晶",
        "Armor": "盔甲",
        "Axe": "斧",
        "Block": "方块",
        "Boots": "靴子",
        "Bronze": "青铜",
        "Chestplate": "胸甲",
        "Copper": "铜",
        "Crystal": "水晶",
        "Diamond": "钻石",
        "Dust": "粉",
        "Emerald": "绿宝石",
        "Energy": "能量",
        "Essence": "精华",
        "Gem": "宝石",
        "Gold": "金",
        "Hammer": "锤",
        "Helmet": "头盔",
        "Ingot": "锭",
        "Iron": "铁",
        "Leggings": "护腿",
        "Magic": "魔法",
        "Mana": "魔力",
        "Nugget": "粒",
        "Ore": "矿石",
        "Pickaxe": "镐",
        "Plate": "板",
        "Raw": "粗",
        "Shard": "碎片",
        "Shovel": "锹",
        "Silver": "银",
        "Steel": "钢",
        "Stone": "石头",
        "Sword": "剑",
        "Tin": "锡",
        "Wand": "法杖",
        "Wooden": "木",
    }

    def __init__(self, glossary: dict[str, str] | None = None) -> None:
        merged = dict(self.BUILTIN_GLOSSARY)
        if glossary:
            merged.update({str(key): str(value) for key, value in glossary.items()})
        self.glossary = sorted(merged.items(), key=lambda item: len(item[0]), reverse=True)

    def translate_batch(self, items: list[TranslationItem]) -> dict[str, str]:
        return {item.id: self._translate_text(item.text) for item in items}

    def _translate_text(self, text: str) -> str:
        translated = text
        for source, target in self.glossary:
            translated = re.sub(rf"\b{re.escape(source)}\b", target, translated, flags=re.IGNORECASE)
        translated = re.sub(r"\s+", " ", translated).strip()
        translated = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", translated)
        return translated or text


class OpenAICompatibleTranslator(Translator):
    def __init__(
        self,
        api_url: str,
        api_key_env: str,
        model: str,
        batch_size: int = 40,
    ) -> None:
        self.api_url = api_url
        self.api_key_env = api_key_env
        self.model = model
        self.batch_size = batch_size

    def translate_batch(self, items: list[TranslationItem]) -> dict[str, str]:
        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            raise RuntimeError(f"environment variable {self.api_key_env} is not set")

        result: dict[str, str] = {}
        for start in range(0, len(items), self.batch_size):
            chunk = items[start : start + self.batch_size]
            result.update(self._translate_chunk(chunk, api_key))
        return result

    def _translate_chunk(self, items: list[TranslationItem], api_key: str) -> dict[str, str]:
        payload = {
            "model": self.model,
            "temperature": 0.2,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是 Minecraft Mod 汉化助手。把英文游戏文本翻译成简体中文。"
                        "必须保留所有 printf 占位符、花括号占位符、Minecraft § 格式代码、换行和专有 ID。"
                        "只输出 JSON 数组，数组项包含 id 和 text。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        [{"id": item.id, "key": item.key, "text": item.text, "mod_id": item.mod_id} for item in items],
                        ensure_ascii=False,
                    ),
                },
            ],
        }

        request = urllib.request.Request(
            self.api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"translation API failed: HTTP {exc.code}: {body}") from exc

        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(_strip_json_fence(content))
        if not isinstance(parsed, list):
            raise RuntimeError("translation API returned non-list JSON")

        translations: dict[str, str] = {}
        source_ids = {item.id for item in items}
        for row in parsed:
            if isinstance(row, dict) and row.get("id") in source_ids and isinstance(row.get("text"), str):
                translations[str(row["id"])] = row["text"]

        missing = source_ids - translations.keys()
        if missing:
            raise RuntimeError(f"translation API missed {len(missing)} entries")

        return translations


def _strip_json_fence(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def load_glossary(path: str | None) -> dict[str, str]:
    if not path:
        return {}
    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError("glossary file must contain a JSON object")
    return {str(key): str(value) for key, value in data.items()}
