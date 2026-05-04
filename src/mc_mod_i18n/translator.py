from __future__ import annotations

from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
from queue import Empty, Queue
import random
import re
from threading import Event, Lock
import time
from typing import Any, Callable
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, urlunparse

_BEIJING_TZ = timezone(timedelta(hours=8))


@dataclass(frozen=True)
class TranslationItem:
    id: str
    key: str
    text: str
    mod_id: str


class Translator:
    def translate_batch(self, items: list[TranslationItem]) -> dict[str, str]:
        raise NotImplementedError


@dataclass(frozen=True)
class ProviderPreset:
    label: str
    api_url: str
    model: str
    api_key_env: str
    key_url: str = ""


AI_PROVIDER_PRESETS: dict[str, ProviderPreset] = {
    "openai-compatible": ProviderPreset(
        label="自定义 OpenAI 兼容",
        api_url="https://api.openai.com/v1/chat/completions",
        model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
    ),
    "openai": ProviderPreset(
        label="OpenAI",
        api_url="https://api.openai.com/v1/chat/completions",
        model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
        key_url="https://platform.openai.com/api-keys",
    ),
    "deepseek": ProviderPreset(
        label="DeepSeek",
        api_url="https://api.deepseek.com/chat/completions",
        model="deepseek-chat",
        api_key_env="DEEPSEEK_API_KEY",
        key_url="https://platform.deepseek.com/api_keys",
    ),
    "moonshot": ProviderPreset(
        label="Moonshot",
        api_url="https://api.moonshot.cn/v1/chat/completions",
        model="moonshot-v1-8k",
        api_key_env="MOONSHOT_API_KEY",
        key_url="https://platform.moonshot.cn/console/api-keys",
    ),
    "dashscope": ProviderPreset(
        label="阿里云百炼 DashScope",
        api_url="https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        model="qwen-plus",
        api_key_env="DASHSCOPE_API_KEY",
        key_url="https://bailian.console.aliyun.com/?apiKey=1",
    ),
    "zhipu": ProviderPreset(
        label="智谱 AI",
        api_url="https://open.bigmodel.cn/api/paas/v4/chat/completions",
        model="glm-4-flash",
        api_key_env="ZHIPUAI_API_KEY",
        key_url="https://open.bigmodel.cn/usercenter/apikeys",
    ),
    "siliconflow": ProviderPreset(
        label="硅基流动 SiliconFlow",
        api_url="https://api.siliconflow.cn/v1/chat/completions",
        model="deepseek-ai/DeepSeek-V3",
        api_key_env="SILICONFLOW_API_KEY",
        key_url="https://cloud.siliconflow.cn/account/ak",
    ),
    "gemini": ProviderPreset(
        label="Google Gemini",
        api_url="https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        model="gemini-2.0-flash",
        api_key_env="GEMINI_API_KEY",
        key_url="https://aistudio.google.com/apikey",
    ),
    "groq": ProviderPreset(
        label="Groq",
        api_url="https://api.groq.com/openai/v1/chat/completions",
        model="llama-3.3-70b-versatile",
        api_key_env="GROQ_API_KEY",
        key_url="https://console.groq.com/keys",
    ),
    "mimo": ProviderPreset(
        label="小米 MiMo",
        api_url="https://token-plan-sgp.xiaomimimo.com/v1/chat/completions",
        model="mimo-v2.5-pro",
        api_key_env="MIMO_API_KEY",
        key_url="https://platform.xiaomimimo.com/token-plan",
    ),
}


def is_ai_provider(provider: str) -> bool:
    return provider in AI_PROVIDER_PRESETS


def get_provider_preset(provider: str) -> ProviderPreset:
    return AI_PROVIDER_PRESETS.get(provider, AI_PROVIDER_PRESETS["openai-compatible"])


def normalize_chat_completions_url(api_url: str) -> str:
    url = api_url.strip()
    if not url:
        return url
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    if path.endswith("/chat/completions") or path.endswith("/responses"):
        return url
    if path.endswith("/v1"):
        path = f"{path}/chat/completions"
    elif path in ("", "/"):
        path = "/v1/chat/completions"
    else:
        return url
    return urlunparse(parsed._replace(path=path))


class CopyTranslator(Translator):
    def translate_batch(self, items: list[TranslationItem]) -> dict[str, str]:
        return {item.id: item.text for item in items}


class GlossaryTranslator(Translator):
    BUILTIN_PHRASES = {
        "Create Aeronautics": "机械动力：航空",
        "Create Offroad": "机械动力：越野",
        "Create Simulated": "机械动力：模拟",
        "For Every Action...": "每一个作用力...",
        "Heavier Artillery": "重型火力",
        "High Fashion": "高级时装",
        "Head in the Clouds": "心在云端",
        "In Thrust We Trust": "信赖推力",
        "Now Available in Pink!": "现已推出粉色款！",
        "Song of the Sky": "天空之歌",
        "Unidentified Floating Object": "不明漂浮物",
        "Up Up and Away": "升空远航",
        "Toss a music disc into the clouds to create something new": "把音乐唱片扔进云层，创造新的东西",
        "Hot Air": "热空气",
        "Lifting Gas Data": "升力气体数据",
        "Total Lift": "总升力",
        "Propeller Data": "螺旋桨数据",
        "Pull air when clockwise": "顺时针旋转时吸入空气",
        "Push air when clockwise": "顺时针旋转时推出空气",
        "No suitable balloon found": "未找到合适的气囊",
        "Effect of Air Pressure on Hot Air Burners": "气压对热空气燃烧器的影响",
        "Effect of Air Pressure on Gyroscopic Propeller Bearings": "气压对陀螺螺旋桨轴承的影响",
        "Constructing Balloons": "建造气囊",
        "Generating Lift using the Hot Air Burner": "使用热空气燃烧器产生升力",
        "Levitating contraptions with Levitite": "使用悬浮石让装置升空",
        "Borehead Bearing Efficiency": "钻头轴承效率",
        "Excavating Using Rock Cutting Wheels": "使用岩石切割轮挖掘",
        "Using Borehead Bearings and Rock Cutting Wheels": "使用钻头轴承和岩石切割轮",
        "When Powered From Top": "从顶部供能时",
        "When Powered From Side": "从侧面供能时",
        "When R-Clicked on Wheel Mount": "右键点击车轮安装座时",
        "Suspension Strength": "悬挂强度",
        "Physics Be Upon Ye": "愿物理与你同在",
        "No Pressure": "毫无压力",
        "Speed is Key": "速度是关键",
        "Steamless Engine": "无蒸汽引擎",
        "Stuck Together": "粘在一起",
        "Unpowered Steering": "无动力转向",
        "What Goes Down...": "落下之物...",
        "...Must Come Up": "...必将升起",
    }

    BUILTIN_GLOSSARY = {
        "Advanced": "高级",
        "Advancement": "进度",
        "Aeronautics": "航空",
        "Air": "空气",
        "Airflow": "气流",
        "Airtight": "气密",
        "Altitude": "高度",
        "Analog": "模拟",
        "Assembler": "装配器",
        "Attached": "已连接",
        "Auger": "螺旋钻",
        "Amethyst": "紫水晶",
        "Armor": "盔甲",
        "Aviator": "飞行员",
        "Axe": "斧",
        "Balloon": "气囊",
        "Bearing": "轴承",
        "Block": "方块",
        "Blocks": "方块",
        "Blue": "蓝色",
        "Blend": "混合物",
        "Boiler": "锅炉",
        "Borehead": "钻头",
        "Boots": "靴子",
        "Brakes": "制动",
        "Bronze": "青铜",
        "Brown": "棕色",
        "Burner": "燃烧器",
        "Burners": "燃烧器",
        "Cannon": "炮",
        "Chestplate": "胸甲",
        "Connector": "连接器",
        "Contraption": "装置",
        "Contraptions": "装置",
        "Copper": "铜",
        "Craft": "合成",
        "Cyan": "青色",
        "Crystal": "水晶",
        "Crystallize": "结晶",
        "Diagram": "图纸",
        "Diamond": "钻石",
        "Disc": "唱片",
        "Docking": "对接",
        "Dust": "粉",
        "Emerald": "绿宝石",
        "Energy": "能量",
        "Engine": "引擎",
        "Envelope": "气囊外壳",
        "Excavate": "挖掘",
        "Excavating": "挖掘",
        "Essence": "精华",
        "Force": "力",
        "Friction": "摩擦",
        "Gem": "宝石",
        "Gimbal": "万向节",
        "Glue": "胶水",
        "Gold": "金",
        "Goggles": "护目镜",
        "Grip": "抓握",
        "Generate": "产生",
        "Gyroscopic": "陀螺",
        "Hammer": "锤",
        "Handle": "把手",
        "Helmet": "头盔",
        "Hidden": "隐藏",
        "Honey": "蜂蜜",
        "Hot": "热",
        "Ingot": "锭",
        "Input": "输入",
        "Iron": "铁",
        "Kinematics": "运动学",
        "Large": "大型",
        "Laser": "激光",
        "Leggings": "护腿",
        "Levitite": "悬浮石",
        "Lift": "升力",
        "Lifting": "升力",
        "Linked": "链接",
        "Magic": "魔法",
        "Mana": "魔力",
        "Mechanism": "机构",
        "Mounted": "车载",
        "Mount": "安装座",
        "Music": "音乐",
        "Navigation": "导航",
        "Nameplate": "铭牌",
        "Nugget": "粒",
        "Obtain": "获得",
        "Offroad": "越野",
        "Optical": "光学",
        "Ore": "矿石",
        "Pearlescent": "珠光",
        "Phantom": "幻翼",
        "Physics": "物理",
        "Pickaxe": "镐",
        "Plate": "板",
        "Plunger": "活塞",
        "Portable": "便携式",
        "Potato": "土豆",
        "Pressure": "气压",
        "Propeller": "螺旋桨",
        "Raw": "粗",
        "Redstone": "红石",
        "Rock": "岩石",
        "Rockcutting": "岩石切割",
        "Rope": "绳索",
        "Rotation": "旋转",
        "Rotational": "旋转",
        "Shard": "碎片",
        "Shaft": "传动杆",
        "Shovel": "锹",
        "Silver": "银",
        "Simulated": "模拟",
        "Small": "小型",
        "Sensor": "传感器",
        "Speed": "速度",
        "Spring": "弹簧",
        "Steel": "钢",
        "Stone": "石头",
        "Storage": "存储",
        "Structure": "结构",
        "Super": "强力",
        "Suspension": "悬挂",
        "Sail": "帆",
        "Symmetric": "对称",
        "Sword": "剑",
        "Table": "台",
        "Thrust": "推力",
        "Tin": "锡",
        "Tire": "轮胎",
        "Torsion": "扭力",
        "Transmission": "传动",
        "Typewriter": "打字机",
        "Vegetable": "蔬菜",
        "Velocity": "速度",
        "Vent": "通风口",
        "Vents": "通风口",
        "Volume": "体积",
        "Weight": "重量",
        "Wheel": "车轮",
        "Wheels": "车轮",
        "Wand": "法杖",
        "Wooden": "木",
        "Black": "黑色",
        "White": "白色",
        "Gray": "灰色",
        "Light Gray": "淡灰色",
        "Red": "红色",
        "Orange": "橙色",
        "Yellow": "黄色",
        "Lime": "黄绿色",
        "Green": "绿色",
        "Pink": "粉色",
        "Magenta": "品红色",
        "Purple": "紫色",
    }

    def __init__(self, glossary: dict[str, str] | None = None) -> None:
        merged = dict(self.BUILTIN_GLOSSARY)
        if glossary:
            merged.update({str(key): str(value) for key, value in glossary.items()})
        self.glossary = sorted(merged.items(), key=lambda item: len(item[0]), reverse=True)

    def translate_batch(self, items: list[TranslationItem]) -> dict[str, str]:
        return {item.id: self._translate_text(item.text) for item in items}

    def _translate_text(self, text: str) -> str:
        if "\n" in text:
            return "\n".join(self._translate_text(line) for line in text.split("\n"))
        phrase = self.BUILTIN_PHRASES.get(text)
        if phrase:
            return phrase
        patterned = self._translate_pattern(text)
        if patterned:
            return patterned
        translated = text
        for source, target in self.glossary:
            translated = re.sub(rf"\b{re.escape(source)}\b", target, translated, flags=re.IGNORECASE)
        translated = re.sub(r"(?<=[\u4e00-\u9fff])'s\b", "的", translated)
        translated = re.sub(r"[ \t]+", " ", translated).strip()
        translated = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", translated)
        return translated or text

    def _translate_pattern(self, text: str) -> str:
        simple_patterns = [
            (r"^Place and power a (.+) to generate (.+)$", "放置并驱动{0}来产生{1}"),
            (r"^Place and power a (.+)$", "放置并驱动{0}"),
            (r"^Obtain a pair of (.+)$", "获得一副{0}"),
            (r"^Obtain a (.+)$", "获得{0}"),
            (r"^Obtain and place a (.+)$", "获得并放置{0}"),
            (r"^Craft a (.+)$", "合成{0}"),
            (r"^Assemble a (.+) to generate more (.+)$", "组装{0}以产生更多{1}"),
            (r"^Assemble a (.+)$", "组装{0}"),
            (r"^Fill an airtight (.+) structure with hot air$", "用热空气填充气密的{0}结构"),
            (r"^Kill a (.+) using a (.+)$", "使用{1}击杀{0}"),
            (r"^Fire a (.+) from a (.+)$", "从{1}发射{0}"),
            (r"^Crystallize (.+) into (.+)$", "将{0}结晶为{1}"),
            (r"^(.+) Data$", "{0}数据"),
            (r"^Total (.+)$", "总{0}"),
            (r"^(.+) volume: (%s)$", "{0}体积：{1}"),
            (r"^(.+) output: (%s)$", "{0}输出：{1}"),
            (r"^via 1 vent$", "通过 1 个通风口"),
            (r"^via (%1\$s) vents$", "通过 {0} 个通风口"),
        ]
        for pattern, replacement in simple_patterns:
            match = re.match(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue
            translated_groups = [self._translate_text(group) for group in match.groups()]
            return replacement.format(*translated_groups)
        return ""


class RateLimiter:
    """Coordinates backoff across concurrent workers when hitting 429."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._paused = Event()
        self._resume_at: float = 0.0

    def pause(self, seconds: float) -> None:
        with self._lock:
            target = time.monotonic() + seconds
            if target > self._resume_at:
                self._resume_at = target
                self._paused.clear()

    def wait_if_paused(self) -> None:
        while True:
            with self._lock:
                remaining = self._resume_at - time.monotonic()
                if remaining <= 0:
                    self._paused.set()
                    return
            time.sleep(min(remaining, 1.0))


class OpenAICompatibleTranslator(Translator):
    def __init__(
        self,
        api_url: str,
        api_key_env: str,
        model: str,
        api_key: str = "",
        provider_label: str = "OpenAI 兼容",
        debug_log_path: str = "",
        concurrency: int = 1,
        max_retries: int = 3,
        batch_size: int = 40,
        request_timeout: float = 10.0,
        progress_callback: Callable[..., None] | None = None,
        task_id: str = "",
    ) -> None:
        self.api_url = normalize_chat_completions_url(api_url)
        self.api_key_env = api_key_env
        self.model = model
        self.api_key = api_key
        self.provider_label = provider_label
        self.debug_log_path = debug_log_path
        self.concurrency = max(1, concurrency)
        self.max_retries = max(1, max_retries)
        self.batch_size = max(1, batch_size)
        self.request_timeout = max(1.0, request_timeout)
        self.progress_callback = progress_callback
        self.task_id = task_id
        self._debug_log_lock = Lock()
        self._rate_limiter = RateLimiter()
        self.failed_items: dict[str, str] = {}

    def translate_batch(self, items: list[TranslationItem]) -> dict[str, str]:
        api_key = self.api_key or os.environ.get(self.api_key_env, "")
        if not api_key:
            raise RuntimeError(f"{self.provider_label} API Key 未填写，且环境变量 {self.api_key_env} 未设置")
        if not items:
            return {}

        result: dict[str, str] = {}
        failed_items: dict[str, str] = {}
        chunks = chunked(items, self.batch_size)
        total = len(chunks)
        self._report_progress(0, total)
        workers = max(1, min(self.concurrency, total))

        chunk_queue: Queue[list[TranslationItem]] = Queue()
        for chunk in chunks:
            chunk_queue.put(chunk)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(self._translate_worker, chunk_queue, failed_items, api_key) for _ in range(workers)]
            for future in as_completed(futures):
                worker_result, worker_completed = future.result()
                result.update(worker_result)
                self._report_progress(worker_completed, 0)
        self.failed_items = failed_items
        return result

    def _report_progress(self, completed: int, total: int) -> None:
        if self.progress_callback:
            self.progress_callback(completed, total)

    def _report_event(self, event: dict[str, Any]) -> None:
        if self.progress_callback:
            self.progress_callback(event)

    def _translate_worker(
        self,
        chunk_queue: Queue[list[TranslationItem]],
        failed_items: dict[str, str],
        api_key: str,
    ) -> tuple[dict[str, str], int]:
        translated: dict[str, str] = {}
        completed = 0
        while True:
            self._rate_limiter.wait_if_paused()
            try:
                chunk = chunk_queue.get_nowait()
            except Empty:
                break
            translated.update(self._translate_chunk_safely(chunk, failed_items, api_key))
            completed += 1
        return translated, completed

    def _translate_chunk_safely(self, items: list[TranslationItem], failed_items: dict[str, str], api_key: str) -> dict[str, str]:
        try:
            return self._translate_chunk(items, api_key)
        except Exception as exc:
            self._record_failed_items(items, reason=str(exc), failed_items=failed_items)
            return {}

    def _record_failed_items(self, items: list[TranslationItem], reason: str, failed_items: dict[str, str]) -> None:
        for item in items:
            failed_items[item.id] = reason
        self._write_debug_log(
            {
                "type": "batch_failed",
                "provider": self.provider_label,
                "batch_size": len(items),
                "error": reason,
                "item_ids": [item.id for item in items],
            }
        )

    def _translate_chunk(self, items: list[TranslationItem], api_key: str) -> dict[str, str]:
        start_time = time.monotonic()
        payload = {
            "model": self.model,
            "temperature": 0.2,
            "stream": False,
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

        response_status, response_headers, response_text = self._open_with_retries(request, items, start_time)
        elapsed_ms = round((time.monotonic() - start_time) * 1000)

        self._write_debug_log(
            {
                "type": "api_call",
                "provider": self.provider_label,
                "elapsed_ms": elapsed_ms,
                "api_url": self.api_url,
                "model": self.model,
                "api_key_env": self.api_key_env,
                "has_inline_api_key": bool(self.api_key),
                "request_headers": {
                    "Authorization": "Bearer ***",
                    "Content-Type": "application/json",
                },
                "request_body": payload,
                "status": response_status,
                "response_headers": response_headers,
                "body_preview": response_text[:2000],
            }
        )

        content = _extract_chat_content(response_text, self.provider_label)
        try:
            parsed = json.loads(_strip_json_fence(content))
        except json.JSONDecodeError as exc:
            preview = content[:180].replace("\n", "\\n")
            raise RuntimeError(f"{self.provider_label} API 返回的译文不是 JSON 数组：{preview}") from exc
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

    def _open_with_retries(
        self,
        request: urllib.request.Request,
        items: list[TranslationItem],
        start_time: float = 0.0,
    ) -> tuple[int, dict[str, str], str]:
        retryable_http = {408, 409, 425, 429, 500, 502, 503, 504}
        last_error = ""
        for attempt in range(1, self.max_retries + 1):
            self._rate_limiter.wait_if_paused()
            self._report_event(
                {
                    "type": "request_attempt",
                    "attempt": attempt,
                    "max_retries": self.max_retries,
                    "timeout_seconds": self.request_timeout,
                    "batch_size": len(items),
                }
            )
            try:
                with urllib.request.urlopen(request, timeout=self.request_timeout) as response:
                    return response.status, dict(response.headers.items()), response.read().decode("utf-8")
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                headers = dict(exc.headers.items())
                self._write_debug_log(
                    {
                        "type": "retry_error",
                        "provider": self.provider_label,
                        "elapsed_ms": round((time.monotonic() - start_time) * 1000) if start_time else 0,
                        "status": exc.code,
                        "error": "http_error",
                        "attempt": attempt,
                        "retryable": exc.code in retryable_http,
                        "body_preview": body[:500],
                    }
                )
                if exc.code not in retryable_http or attempt >= self.max_retries:
                    raise RuntimeError(f"{self.provider_label} API 请求失败：HTTP {exc.code}: {body}") from exc
                if exc.code == 429:
                    retry_after = _parse_retry_after(headers)
                    pause_seconds = retry_after if retry_after > 0 else min(30.0, 2.0 * (2 ** (attempt - 1)))
                    self._rate_limiter.pause(pause_seconds)
                last_error = f"HTTP {exc.code}"
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
                reason = getattr(exc, "reason", exc)
                last_error = str(reason)
                self._write_debug_log(
                    {
                        "type": "retry_error",
                        "provider": self.provider_label,
                        "elapsed_ms": round((time.monotonic() - start_time) * 1000) if start_time else 0,
                        "status": 0,
                        "error": last_error,
                        "attempt": attempt,
                        "retryable": True,
                    }
                )
                if attempt >= self.max_retries:
                    raise RuntimeError(f"{self.provider_label} API 连接失败，已重试 {attempt} 次：{last_error}") from exc

            base_delay = min(20.0, 0.8 * (2 ** (attempt - 1)))
            delay = base_delay * (0.5 + random.random())
            self._report_event(
                {
                    "type": "retry_wait",
                    "attempt": attempt,
                    "next_attempt": attempt + 1,
                    "max_retries": self.max_retries,
                    "delay_seconds": delay,
                    "timeout_seconds": self.request_timeout,
                    "batch_size": len(items),
                    "reason": last_error,
                }
            )
            self._write_debug_log(
                {
                    "type": "retry",
                    "provider": self.provider_label,
                    "attempt": attempt + 1,
                    "delay_seconds": delay,
                    "batch_size": len(items),
                    "reason": last_error,
                }
            )
            time.sleep(delay)

        raise RuntimeError(f"{self.provider_label} API 连接失败：{last_error}")

    def _write_debug_log(self, record: dict[str, object]) -> None:
        if not self.debug_log_path:
            return
        path = Path(self.debug_log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "time": datetime.now(timezone.utc).astimezone(_BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "task_id": self.task_id,
            **record,
        }
        with self._debug_log_lock:
            with path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(record, ensure_ascii=False) + "\n")


def split_evenly(items: list[TranslationItem], parts: int) -> list[list[TranslationItem]]:
    if not items:
        return []
    parts = max(1, min(parts, len(items)))
    base, remainder = divmod(len(items), parts)
    groups: list[list[TranslationItem]] = []
    start = 0
    for index in range(parts):
        size = base + (1 if index < remainder else 0)
        if size <= 0:
            continue
        groups.append(items[start : start + size])
        start += size
    return groups


def chunked(items: list[TranslationItem], size: int) -> list[list[TranslationItem]]:
    size = max(1, size)
    return [items[start : start + size] for start in range(0, len(items), size)]


def _extract_chat_content(response_text: str, provider_label: str) -> str:
    stripped = response_text.lstrip()
    if stripped.startswith("data:"):
        return _extract_stream_content(response_text, provider_label)

    try:
        data = json.loads(response_text)
    except json.JSONDecodeError as exc:
        preview = response_text[:180].replace("\n", "\\n")
        raise RuntimeError(f"{provider_label} API 返回格式无法识别：{preview}") from exc

    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        if isinstance(data, dict) and isinstance(data.get("content"), str):
            return data["content"]
        raise RuntimeError(f"{provider_label} API 返回格式无法识别") from exc


def _extract_stream_content(response_text: str, provider_label: str) -> str:
    chunks: list[str] = []
    for raw_line in response_text.splitlines():
        line = raw_line.strip()
        if not line.startswith("data:"):
            continue
        event_data = line.removeprefix("data:").strip()
        if not event_data or event_data == "[DONE]":
            continue
        try:
            data = json.loads(event_data)
        except json.JSONDecodeError:
            continue
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            continue
        choice = choices[0]
        if not isinstance(choice, dict):
            continue
        delta = choice.get("delta")
        if isinstance(delta, dict) and isinstance(delta.get("content"), str):
            chunks.append(delta["content"])
            continue
        message = choice.get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            chunks.append(message["content"])

    content = "".join(chunks).strip()
    if not content:
        raise RuntimeError(f"{provider_label} API 流式响应中没有可用文本")
    return content


def _strip_json_fence(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def _parse_retry_after(headers: dict[str, str]) -> float:
    value = headers.get("Retry-After") or headers.get("retry-after") or ""
    if not value:
        return 0.0
    try:
        return max(0.0, float(value))
    except ValueError:
        return 0.0


def load_glossary(path: str | None) -> dict[str, str]:
    if not path:
        return {}
    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError("glossary file must contain a JSON object")
    return {str(key): str(value) for key, value in data.items()}
