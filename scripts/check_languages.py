"""Real translation checks with public sample sentences; saves an inspectable report."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from ai_models import OllamaModels
from settings import ConfigStore
from translator import PrismTranslator, identify_language

SAMPLES = {"en": "The weather is pleasant today.", "zh-CN": "今天的天气很好。",
           "ja": "今日は天気がいいです。", "fr": "Il fait beau aujourd’hui.", "ko": "오늘은 날씨가 좋아요."}
PAIRS = [("en", "zh-CN"), ("zh-CN", "en")]
for language in ("ja", "fr", "ko"):
    for other in ("zh-CN", "en"):
        PAIRS += [(language, other), (other, language)]
OUTPUT = ROOT / "artifacts" / "language-checks"
OUTPUT.mkdir(parents=True, exist_ok=True)
lock = threading.Lock()
results = []
config = ConfigStore().snapshot()


def save():
    (OUTPUT / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), "utf-8")
    rows = ["# 多语言实测", "", "固定示例句：今天的天气很好。日、法、韩分别与中、英双向测试，并包含中英双向。", "",
            "| 翻译源 | 方向 | 结果 | 译文 / 错误 |", "| --- | --- | --- | --- |"]
    for result in results:
        text = result.get("result", result.get("error", "")).replace("|", "\\|").replace("\n", " ")
        rows.append(f"| {result['engine']} | {result['source']} → {result['target']} | {result['status']} | {text} |")
    (OUTPUT / "report.md").write_text("\n".join(rows) + "\n", "utf-8")


def check_engine(engine):
    translator = PrismTranslator()
    if engine == "ai":
        OllamaModels().start(config["ai_url"], config["ai_model"])
    for source, target in PAIRS:
        record = {"engine": engine, "source": source, "target": target}
        start = time.monotonic()
        try:
            if engine == "apple":
                print(f"apple: {source} → {target} (首次使用可能下载系统语言资源)", flush=True)
                response = subprocess.run([str(translator.helper)], input=json.dumps({
                    "text": SAMPLES[source], "source": source, "target": target}, ensure_ascii=False),
                    capture_output=True, text=True, encoding="utf-8", timeout=600)
                payload = json.loads(response.stdout)
                if not payload.get("ok"):
                    raise RuntimeError(payload.get("error", "Native translation failed"))
                translated = payload["result"]
            elif engine == "light":
                translated = translator._light(SAMPLES[source], source, target, None)
                time.sleep(.3)
            else:
                translated = translator._ai(SAMPLES[source], target, config["ai_url"], config["ai_model"])
            detected = identify_language(translated).split("-")[0]
            expected = target.split("-")[0]
            record.update(result=translated, detected=detected,
                          status="通过" if translated.strip() and detected == expected else "需复核")
        except Exception as exc:
            record.update(status="失败", error=str(exc))
        record["seconds"] = round(time.monotonic() - start, 2)
        with lock:
            results.append(record)
            save()
        print(f"{engine}: {source} → {target}: {record['status']} · {record.get('result', record.get('error'))}", flush=True)


if __name__ == "__main__":
    print("Local routing:", {language: PrismTranslator.detect_route(text) for language, text in SAMPLES.items()}, flush=True)
    with ThreadPoolExecutor(max_workers=3) as executor:
        for result in executor.map(check_engine, ("apple", "light", "ai")):
            pass
    print(f"Saved {len(results)} checks to {OUTPUT / 'report.md'}", flush=True)
