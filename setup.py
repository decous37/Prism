"""Build a standalone .app with Command Line Tools; no Xcode project required."""
from pathlib import Path
from setuptools import setup

ROOT = Path(__file__).resolve().parent
HELPER = ROOT / "native" / "prism-translation"
if not HELPER.exists():
    raise SystemExit("Run ./scripts/build_native.sh first")

setup(
    name="Prism", version="1.5.0", app=["main.py"],
    data_files=["ui.html", "main.html", ("native", ["native/prism-translation"])],
    options={"py2app": {
        "arch": "arm64", "argv_emulation": False, "strip": True,
        "iconfile": "resources/Prism.icns",
        "packages": ["webview", "requests", "certifi"],
        "includes": ["AppKit", "Foundation", "Quartz", "ApplicationServices", "NaturalLanguage",
                     "WebKit", "Security", "UniformTypeIdentifiers", "objc", "PyObjCTools.AppHelper"],
        "excludes": ["tkinter", "PyQt5", "PyQt6", "PySide2", "PySide6", "pynput", "pytest"],
        "plist": {
            "CFBundleName": "Prism", "CFBundleDisplayName": "Prism",
            "CFBundleIdentifier": "app.prism.translator",
            "CFBundleShortVersionString": "1.5.0", "CFBundleVersion": "11",
            "LSMinimumSystemVersion": "15.0", "LSUIElement": True,
            "NSHighResolutionCapable": True,
            "NSHumanReadableCopyright": "Prism",
            "NSAccessibilityUsageDescription": "Prism 读取当前选中文字，并使用快捷键呼出翻译。",
            "NSInputMonitoringUsageDescription": "Prism 使用全局快捷键翻译当前选中文字。",
        },
    }},
)
