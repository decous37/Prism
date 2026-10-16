"""Validated, atomic configuration storage, independent of the GUI."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import tempfile
import threading
from urllib.parse import urlsplit

DEFAULTS = {
    "hotkey": "<cmd>+<alt>+x", "hotkey_display": "⌘ ⌥ X", "engine": "apple",
    "ai_url": "http://localhost:11434/v1/chat/completions", "ai_model": "qwen2.5:7b",
}
MODIFIERS = {"<cmd>": "⌘", "<alt>": "⌥", "<ctrl>": "⌃", "<shift>": "⇧"}


def parse_hotkey(value: str) -> tuple[tuple[str, ...], str]:
    if not isinstance(value, str):
        raise ValueError("快捷键格式无效")
    parts = value.lower().split("+")
    modifiers, key = parts[:-1], parts[-1]
    if (not modifiers or len(set(modifiers)) != len(modifiers)
            or any(m not in MODIFIERS for m in modifiers)
            or not re.fullmatch(r"[a-z0-9]", key)
            or not any(m in modifiers for m in ("<cmd>", "<alt>", "<ctrl>"))):
        raise ValueError("请使用 ⌘、⌥ 或 ⌃ 加一个字母或数字，可同时使用 ⇧")
    return tuple(m for m in MODIFIERS if m in modifiers), key


def validate_config(updates: dict, base: dict | None = None) -> dict:
    if not isinstance(updates, dict) or set(updates) - DEFAULTS.keys():
        raise ValueError("包含无法识别的设置")
    result = dict(base or DEFAULTS)
    result.update(updates)
    modifiers, key = parse_hotkey(result["hotkey"])
    result["hotkey"] = "+".join((*modifiers, key))
    result["hotkey_display"] = " ".join([*(MODIFIERS[m] for m in modifiers), key.upper()])
    if result["engine"] not in ("apple", "light", "ai"):
        raise ValueError("请选择有效的翻译源")
    model = result["ai_model"]
    if not isinstance(model, str) or not model.strip() or len(model) > 200:
        raise ValueError("请输入 AI 模型名称")
    result["ai_model"] = model.strip()
    url = result["ai_url"]
    if not isinstance(url, str):
        raise ValueError("AI 服务地址无效")
    parsed = urlsplit(url)
    if (parsed.scheme not in ("http", "https") or not parsed.hostname
            or parsed.username or parsed.password or parsed.fragment):
        raise ValueError("AI 服务地址应为完整的 HTTP(S) 地址，且不能包含密码")
    result["ai_url"] = url.strip()
    return result


class ConfigStore:
    def __init__(self, path: Path | None = None):
        self.path = path or Path.home() / ".prism_config.json"
        self._lock = threading.RLock()
        self.warning = ""
        self._config = dict(DEFAULTS)
        if self.path.exists():
            try:
                self._config = validate_config(json.loads(self.path.read_text("utf-8")))
            except (ValueError, OSError, TypeError):
                self.warning = f"设置文件无法读取，已使用默认设置。原文件保留在 {self.path}。"

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self._config)

    def update(self, updates: dict) -> dict:
        with self._lock:
            config = validate_config(updates, self._config)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.warning and self.path.exists():
                backup = self.path.with_suffix(".json.invalid")
                if not backup.exists():
                    backup.write_bytes(self.path.read_bytes())
                    backup.chmod(0o600)
            descriptor, temporary = tempfile.mkstemp(prefix=".prism-", dir=self.path.parent)
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                    json.dump(config, stream, ensure_ascii=False, indent=2)
                    stream.write("\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, self.path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            self._config = config
            self.warning = ""
            return dict(config)
