"""Start the local Ollama service and load an installed model with bounded waits."""
from pathlib import Path
import os
import shutil
import subprocess
import threading
import time
from urllib.parse import urlsplit

import requests


class ModelStartError(Exception):
    pass


class OllamaModels:
    def __init__(self):
        self._lock = threading.Lock()
        self._server = None

    @staticmethod
    def supports(url):
        try:
            parsed = urlsplit(url)
            return parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1", "::1") and parsed.port == 11434
        except ValueError:
            return False

    def _launch_service(self):
        candidates = [Path("/Applications/Ollama.app/Contents/Resources/ollama"),
                      Path("/opt/homebrew/bin/ollama"), Path("/usr/local/bin/ollama")]
        discovered = shutil.which("ollama")
        if discovered:
            candidates.append(Path(discovered))
        binary = next((p for p in candidates if p.is_file() and os.access(p, os.X_OK)), None)
        if binary is None:
            raise ModelStartError("尚未安装 Ollama，请先安装 Ollama 并下载所选模型。")
        environment = dict(os.environ, OLLAMA_HOST="127.0.0.1:11434")
        self._server = subprocess.Popen([str(binary), "serve"], env=environment,
                                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL, start_new_session=True)

    def start(self, url, model):
        if not self.supports(url):
            raise ModelStartError("此服务请在服务端启动，Prism 仅自动启动本机 Ollama。")
        parsed = urlsplit(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        model = model.strip()
        if not model:
            raise ModelStartError("请先填写模型名称。")
        with self._lock:
            try:
                with requests.Session() as session:
                    try:
                        tags = session.get(base + "/api/tags", timeout=(1, 3))
                    except requests.ConnectionError:
                        self._launch_service()
                        deadline = time.monotonic() + 15
                        while True:
                            try:
                                tags = session.get(base + "/api/tags", timeout=(1, 2))
                                break
                            except requests.ConnectionError:
                                if time.monotonic() >= deadline:
                                    raise ModelStartError("Ollama 启动失败，请打开 Ollama 后重试。")
                                time.sleep(.25)
                    tags.raise_for_status()
                    names = {item.get("name", item.get("model")) for item in tags.json().get("models", [])}
                    aliases = {model, model + ":latest"}
                    if not names & aliases:
                        raise ModelStartError(f"未找到模型 {model}，请先在 Ollama 下载该模型，或填写已安装的模型名。")
                    running = session.get(base + "/api/ps", timeout=(2, 4))
                    if running.status_code == 200:
                        loaded = {item.get("name", item.get("model")) for item in running.json().get("models", [])}
                        if loaded & aliases:
                            return {"ok": True, "state": "ready", "message": "模型已就绪"}
                    # An empty prompt asks Ollama to load, not generate a translation.
                    warmed = session.post(base + "/api/generate", json={
                        "model": model, "prompt": "", "stream": False, "keep_alive": "15m",
                    }, timeout=(3, 120))
                    warmed.raise_for_status()
                    if warmed.json().get("error"):
                        raise ModelStartError("模型加载失败，请检查可用内存或换用较小模型。")
                    return {"ok": True, "state": "ready", "message": "模型已就绪"}
            except requests.Timeout as exc:
                raise ModelStartError("模型启动超时，请检查 Ollama 或换用较小模型后重试。") from exc
            except requests.RequestException as exc:
                raise ModelStartError("无法连接 Ollama 或加载模型，请检查本机服务后重试。") from exc
            except OSError as exc:
                raise ModelStartError("无法启动 Ollama，请检查安装后重试。") from exc
            except (ValueError, TypeError, AttributeError) as exc:
                raise ModelStartError("Ollama 返回的状态无法识别，请检查服务后重试。") from exc
