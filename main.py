"""Prism: a quiet translation utility for macOS 15+ (Apple Silicon)."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import fcntl
import json
import logging
import math
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

import AppKit
import Foundation
import webview
from PyObjCTools import AppHelper, MachSignals

from geometry import popup_origin
from ai_models import ModelStartError, OllamaModels
from hotkey import GlobalHotkey
from keyboard import KeyInterceptor
from language_picker import LanguagePicker
from languages import CHOICES, badge_label
from macos import (SelectionReader, accessibility_allowed, copy_text, frontmost_pid, on_main,
                   request_accessibility, install_reopen_delegate, notify_running_app)
from settings import ConfigStore, parse_hotkey, validate_config
from translator import PrismTranslator, TranslationError

LOG = logging.getLogger("prism")
ROOT = Path(__file__).resolve().parent


class PrismBridge:
    def __init__(self, app, view="popup"):
        self._app = app
        self._view = view

    def hide_window(self):
        if self._view == "main":
            on_main(self._app.hide_main)
        else:
            self._app.hide_card()
        return {"ok": True}

    def request_accessibility(self):
        if self._view != "main":
            return {"ok": False, "error": "请在主页面设置辅助功能。"}
        if not on_main(accessibility_allowed):
            # Ad-hoc builds are identified by their code hash. An old enabled
            # TCC entry can refer to the replaced build and cannot authorize us.
            try:
                subprocess.run(["/usr/bin/tccutil", "reset", "Accessibility", "app.prism.translator"],
                               check=True, timeout=5, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except (OSError, subprocess.SubprocessError):
                LOG.warning("Old Accessibility entry could not be reset")
                return {"ok": False, "error": "请在系统辅助功能中移除旧 Prism，再添加应用程序中的 Prism。"}
            try:
                self._app.restart_for_accessibility()
            except OSError:
                LOG.exception("Prism could not restart for Accessibility")
                return {"ok": False, "error": "请退出并重新打开 Prism 后授权。"}
            return {"ok": True}
        on_main(request_accessibility)
        return {"ok": True}

    def quit_app(self):
        AppHelper.callAfter(self._app.quit)
        return {"ok": True}

    def speak(self, text):
        if not isinstance(text, str) or not text.strip() or len(text) > 20000:
            return {"ok": False, "error": "暂无可朗读的译文"}
        self._app.speak(text)
        return {"ok": True}

    def copy_text(self, text):
        if not isinstance(text, str) or not text:
            return {"ok": False, "error": "暂无可复制的译文"}
        return {"ok": on_main(copy_text, text)}

    def save_config(self, updates):
        previous = self._app.store.snapshot()
        try:
            candidate = validate_config(updates, previous)
            if candidate["hotkey"] != previous["hotkey"]:
                on_main(self._app.hotkey.register, candidate["hotkey"])
            try:
                config = self._app.store.update(updates)
            except OSError:
                on_main(self._app.hotkey.register, previous["hotkey"])
                raise
            if any(key in updates for key in ("engine", "ai_url", "ai_model")):
                on_main(self._app.retranslate)
            self._app.ui_workers.submit(self._app.sync_config)
            return {"ok": True, "config": config}
        except (ValueError, OSError) as exc:
            LOG.warning("Configuration could not be saved: %s", type(exc).__name__)
            return {"ok": False, "error": str(exc), "config": self._app.store.snapshot()}

    def get_config(self):
        return self._app.store.snapshot()

    def open_language_menu(self, side, rect):
        if self._view != "popup" or side not in ("source", "target") or not isinstance(rect, dict):
            return {"ok": False}
        values = [rect.get(key) for key in ("left", "top", "width", "height")]
        if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in values):
            return {"ok": False}
        on_main(self._app.open_language_menu, side, values)
        return {"ok": True}

    def start_ai_model(self):
        config = self._app.store.snapshot()
        try:
            return self._app.ai_models.start(config["ai_url"], config["ai_model"])
        except ModelStartError as exc:
            return {"ok": False, "state": "error", "message": str(exc)}

    def resize_card(self, height):
        if isinstance(height, (float, int)):
            on_main(self._app.resize_card, max(100, min(480, int(height))))

    def set_recording(self, active):
        on_main(self._app.set_recording, bool(active))


class PrismApp:
    def __init__(self, config_path=None, request_accessibility=False):
        self.store = ConfigStore(config_path)
        self.translator = PrismTranslator(ROOT / "native" / "prism-translation")
        self.selection = SelectionReader()
        self.bridge = PrismBridge(self)
        self.window = None
        self.main_window = None
        self.native = None
        self.app_delegate = None
        self.monitors = []
        self.workers = ThreadPoolExecutor(max_workers=2, thread_name_prefix="prism-translate")
        self.ui_workers = ThreadPoolExecutor(max_workers=1, thread_name_prefix="prism-ui")
        self.capture = ThreadPoolExecutor(max_workers=1, thread_name_prefix="prism-selection")
        self._generation = 0
        self._state_lock = threading.RLock()
        self._ui_lock = threading.Lock()
        self._last_trigger = 0.0
        self._closed = False
        self._ready = threading.Event()
        self._main_ready = threading.Event()
        self._speech = None
        self._speech_lock = threading.Lock()
        self._authorized = False
        self._return_app = None
        self._activated = False
        self.recording = False
        self._height = 125
        self._mouse = (0, 0)
        self._visible = None
        self._last_selected = ""
        self._route = None
        self.language_picker = None
        self._request_accessibility = request_accessibility
        self.keyboard = KeyInterceptor(self)
        self.hotkey = GlobalHotkey(self.on_hotkey)
        self._startup_warning = ""
        self._loading = False
        self.ai_models = OllamaModels()

    def invalidate(self):
        with self._state_lock:
            self._generation += 1
            return self._generation

    def current(self, generation):
        with self._state_lock:
            return generation == self._generation and not self._closed

    def js(self, function, data=None, generation=None):
        # evaluate_js waits for WebKit; never run this method on the Cocoa thread.
        if Foundation.NSThread.isMainThread():
            raise RuntimeError("JavaScript must run off the Cocoa main thread")
        with self._ui_lock:
            if self._closed or (generation is not None and not self.current(generation)):
                return
            if isinstance(data, dict) and data.get("source") and data.get("target"):
                data = {**data, "source_label": badge_label(data["source"]),
                        "target_label": badge_label(data["target"])}
            argument = "" if data is None else json.dumps(data, ensure_ascii=False)
            if function == "showLoadingState":
                self._loading = True
            elif function in ("renderTranslation", "renderMessage"):
                self._loading = False
            self.window.evaluate_js(f"window.{function}({argument})")

    def main_js(self, function, data=None):
        if Foundation.NSThread.isMainThread():
            raise RuntimeError("JavaScript must run off the Cocoa main thread")
        if self._closed or not self._main_ready.is_set():
            return
        with self._ui_lock:
            argument = "" if data is None else json.dumps(data, ensure_ascii=False)
            self.main_window.evaluate_js(f"window.{function}({argument})")

    def sync_config(self):
        config = self.store.snapshot()
        if self._ready.is_set():
            self.js("initConfig", config)
        self.main_js("initConfig", config)

    def _match_hotkey(self, event):
        characters = event.charactersIgnoringModifiers()
        if not characters:
            return False
        modifiers, key = parse_hotkey(self.store.snapshot()["hotkey"])
        flags = event.modifierFlags()
        masks = {
            "<cmd>": AppKit.NSEventModifierFlagCommand, "<alt>": AppKit.NSEventModifierFlagOption,
            "<ctrl>": AppKit.NSEventModifierFlagControl, "<shift>": AppKit.NSEventModifierFlagShift,
        }
        return str(characters).lower() == key and all(bool(flags & mask) == (name in modifiers)
                                                       for name, mask in masks.items())

    def _event(self, event, local=False):
        try:
            if self.recording:
                return event
            if self.language_picker and self.language_picker.is_visible():
                if local and self.language_picker.key(event.keyCode()):
                    if not self.language_picker.is_visible():
                        self.native.makeKeyAndOrderFront_(None)
                    return None
                return event
            if local and event.modifierFlags() & AppKit.NSEventModifierFlagCommand:
                key = str(event.charactersIgnoringModifiers() or "").lower()
                if key == "q":
                    self.quit()
                    return None
                if key == "w" and self.main_window and event.window() == self.main_window.native:
                    self.hide_main()
                    return None
            if not event.isARepeat() and self._match_hotkey(event):
                self.on_hotkey()
                return None if local else event
            # Passive cards do not take keyboard focus. These keys still work before clicking.
            if not local and self.native and self.native.isVisible():
                if event.keyCode() == 53:
                    self.hide_card()
                elif event.keyCode() in (36, 76) and not event.modifierFlags() & (
                        AppKit.NSEventModifierFlagCommand | AppKit.NSEventModifierFlagOption
                        | AppKit.NSEventModifierFlagControl | AppKit.NSEventModifierFlagShift):
                    self.ui_workers.submit(self._copy_and_hide)
        except Exception:
            LOG.exception("Keyboard event handling failed")
        return event

    def _copy_and_hide(self):
        self.js("copyAndHide")

    def on_hotkey(self):
        if getattr(self, "language_picker", None) and self.language_picker.is_visible():
            return
        if not self.recording and time.monotonic() - self._last_trigger > 0.35:
            self._last_trigger = time.monotonic()
            self.trigger()

    def set_recording(self, active):
        self.recording = active
        if active:
            self.hotkey.pause()
        elif not self.hotkey.reference:
            try:
                self.hotkey.register(self.store.snapshot()["hotkey"])
            except ValueError as exc:
                LOG.warning("Hotkey could not be resumed: %s", exc)

    def setup_native(self):
        if self.app_delegate is not None:
            return
        self.native = self.window.native
        application = AppKit.NSApplication.sharedApplication()
        application.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
        self.native.setStyleMask_(AppKit.NSWindowStyleMaskBorderless)
        self.native.setOpaque_(False)
        self.native.setBackgroundColor_(AppKit.NSColor.clearColor())
        self.native.setHasShadow_(False)
        self.native.setLevel_(AppKit.NSFloatingWindowLevel)
        self.native.setCollectionBehavior_(AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
                                          | AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary)
        self.native.setMovableByWindowBackground_(False)
        self.monitors = [
            AppKit.NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
                AppKit.NSEventMaskKeyDown, lambda event: self._event(event)),
            AppKit.NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
                AppKit.NSEventMaskKeyDown, lambda event: self._event(event, local=True)),
            AppKit.NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
                AppKit.NSEventMaskLeftMouseDown | AppKit.NSEventMaskRightMouseDown | AppKit.NSEventMaskOtherMouseDown,
                self.outside_click),
            AppKit.NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
                AppKit.NSEventMaskLeftMouseDown | AppKit.NSEventMaskRightMouseDown | AppKit.NSEventMaskOtherMouseDown,
                self.outside_click),
        ]
        application.setMainMenu_(None)
        self.app_delegate = install_reopen_delegate(application, self)
        try:
            self.hotkey.register(self.store.snapshot()["hotkey"])
        except ValueError as exc:
            self._startup_warning = str(exc)
        self._ready.set()
        self.check_permissions()

    def check_permissions(self):
        if self._closed:
            return
        allowed = accessibility_allowed()
        changed = allowed != self._authorized
        if allowed and not self._authorized:
            # Re-register after permission is granted without requiring an app restart.
            if self.monitors[0]:
                AppKit.NSEvent.removeMonitor_(self.monitors[0])
            self.monitors[0] = AppKit.NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
                AppKit.NSEventMaskKeyDown, lambda event: self._event(event))
        self._authorized = allowed
        if allowed:
            self.keyboard.start()
        elif self.keyboard.tap:
            self.keyboard.close()
        if changed:
            LOG.info("Accessibility granted=%s, keyboard interceptor=%s", allowed, bool(self.keyboard.tap))
            self.ui_workers.submit(self.main_js, "updateAppStatus", {"authorized": allowed})
        AppHelper.callLater(2, self.check_permissions)

    def _placement(self):
        mouse = AppKit.NSEvent.mouseLocation()
        screen = next((s for s in AppKit.NSScreen.screens()
                       if AppKit.NSPointInRect(mouse, s.frame())), AppKit.NSScreen.mainScreen())
        frame = screen.visibleFrame()
        return (mouse.x, mouse.y), (frame.origin.x, frame.origin.y, frame.size.width, frame.size.height)

    def show_card(self, placement, activate=False):
        self._mouse, self._visible = placement
        self._return_app = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
        self._activated = activate
        self.resize_card(self._height, reposition=True)
        if activate:
            AppKit.NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
            self.native.makeKeyAndOrderFront_(None)
        else:
            self.native.orderFrontRegardless()

    def resize_card(self, height, reposition=False):
        self._height = height
        if not self.native:
            return
        if self._visible is None:
            self._mouse, self._visible = self._placement()
        if self.native.isVisible() and not reposition:
            # Keep the user's dragged position, including the top edge, when content grows.
            frame = self.native.frame()
            screen = self.native.screen() or AppKit.NSScreen.mainScreen()
            visible = screen.visibleFrame()
            x = max(visible.origin.x + 8, min(frame.origin.x,
                    visible.origin.x + visible.size.width - 360 - 8))
            y = max(visible.origin.y + 8, min(frame.origin.y + frame.size.height - height,
                    visible.origin.y + visible.size.height - height - 8))
        else:
            x, y = popup_origin(self._mouse, self._visible, (360, height))
        self.native.setFrame_display_(AppKit.NSMakeRect(x, y, 360, height), True)

    def trigger(self):
        if not self._ready.is_set() or self._closed:
            return
        generation = self.invalidate()
        self._route = None
        self._last_selected = ""
        pid = frontmost_pid()
        placement = self._placement()
        self.capture.submit(self._capture_then_translate, pid, placement, generation)

    def retranslate(self):
        if self._last_selected and self.native and self.native.isVisible():
            generation = self.invalidate()
            self.workers.submit(self._translate, self._last_selected,
                                (self._mouse, self._visible), generation, False, self._route)

    def open_language_menu(self, side, rect):
        if not self._route or not self._last_selected or not self.native.isVisible():
            return
        left, top, width, height = rect
        content = self.native.contentView().bounds().size
        if not (0 <= left <= content.width and 0 <= top <= content.height and 0 < width <= 336 and 0 < height <= 60):
            return
        point = self.native.convertPointToScreen_(AppKit.NSMakePoint(left, content.height - top - height))
        screen = self.native.screen() or AppKit.NSScreen.mainScreen()
        frame = screen.visibleFrame()
        visible = (frame.origin.x, frame.origin.y, frame.size.width, frame.size.height)
        if self.language_picker is None:
            self.language_picker = LanguagePicker()
        generation = self._generation
        self._activated = True
        AppKit.NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        self.native.makeKeyAndOrderFront_(None)
        self.language_picker.show(self._route[side], (point.x, point.y, width, height), visible,
                                  lambda language: self.set_language(side, language, generation))

    def set_language(self, side, language, generation):
        if (not self.current(generation) or not self._route or not self.native.isVisible()
                or side not in ("source", "target") or language not in CHOICES):
            return
        self.native.makeKeyAndOrderFront_(None)
        if self._route[side] == language:
            return
        self._route = {**self._route, side: language}
        self.retranslate()

    def _capture_then_translate(self, pid, placement, generation):
        try:
            selected = self.selection.read(pid, lambda: not self.current(generation))
        except PermissionError:
            self._show_message("无法读取选中文字，请在 Prism 主页面授权辅助功能。", placement, generation)
            return
        except Exception:
            LOG.exception("Selection could not be read")
            self._show_message("未能读取选区，请重新选中文字后再试。", placement, generation)
            return
        if not self.current(generation):
            return
        if not selected:
            self._last_selected = ""
            self._show_message("请先选中文字。", placement, generation)
            return
        self._last_selected = selected
        self.workers.submit(self._translate, selected, placement, generation)

    def _show_if_current(self, placement, generation, reposition=True):
        if self.current(generation):
            if reposition or not self.native.isVisible():
                self.show_card(placement)

    def _show_message(self, text, placement, generation):
        self.js("renderMessage", {"badge": "提示", "result": text}, generation)
        on_main(self._show_if_current, placement, generation)

    def _translate(self, selected, placement, generation, reposition=True, route=None):
        display_route = {"badge": "暂未完成"}
        try:
            if not self.current(generation):
                return
            display_route = self.translator.resolve_route(selected, **(route or {}))
            with self._state_lock:
                if not self.current(generation):
                    return
                self._route = {key: display_route[key] for key in ("source", "target")}
            self.js("showLoadingState", display_route, generation=generation)
            on_main(self._show_if_current, placement, generation, reposition)
            config = self.store.snapshot()
            if config["engine"] == "ai" and self.ai_models.supports(config["ai_url"]):
                self.js("showLoadingState", {"message": "正在准备 AI…"}, generation)
                self.js("renderAIStatus", {"state": "starting", "message": "正在启动模型…"}, generation)
                try:
                    status = self.ai_models.start(config["ai_url"], config["ai_model"])
                except ModelStartError as exc:
                    self.js("renderAIStatus", {"state": "error", "message": str(exc)}, generation)
                    raise TranslationError(str(exc)) from exc
                self.js("renderAIStatus", status, generation)
                if not self.current(generation):
                    return
                self.js("showLoadingState", {"message": "正在翻译…"}, generation)
            result = self.translator.translate(selected, config["engine"], config["ai_url"], config["ai_model"],
                                               cancel=lambda: not self.current(generation),
                                               source=display_route["source"], target=display_route["target"])
            self.js("renderTranslation", result, generation)
        except TranslationError as exc:
            self.js("renderMessage", {**display_route, "result": str(exc)}, generation)
        except Exception:
            LOG.exception("Translation failed")
            self.js("renderMessage", {**display_route, "result": "翻译暂时不可用，请重试或切换翻译源。"}, generation)

    def reopen(self):
        generation = self.invalidate()
        self.ui_workers.submit(self._present_main, generation)

    def _present_main(self, generation):
        if not self.current(generation):
            return
        if not self._main_ready.wait(timeout=10):
            return
        self.main_js("initConfig", self.store.snapshot())
        self.main_js("updateAppStatus", {"authorized": on_main(accessibility_allowed),
                     "notice": self._startup_warning or ("设置已恢复默认" if self.store.warning else "")})
        on_main(self._show_main_if_current, generation)

    def _show_main_if_current(self, generation):
        if self.current(generation):
            self._hide(restore_focus=False)
            application = AppKit.NSApplication.sharedApplication()
            application.setActivationPolicy_(AppKit.NSApplicationActivationPolicyRegular)
            self.main_window.native.makeKeyAndOrderFront_(None)
            application.activateIgnoringOtherApps_(True)

    def hide_main(self):
        self.set_recording(False)
        self.main_window.native.orderOut_(None)
        AppKit.NSApplication.sharedApplication().setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)

    def on_main_closing(self):
        if self._closed:
            return True
        on_main(self.hide_main)
        return False

    def restart_for_accessibility(self):
        bundle = Foundation.NSBundle.mainBundle()
        if bundle.bundleIdentifier() != "app.prism.translator":
            on_main(request_accessibility)
            return
        # TCC's prompt state is cached for the life of a process. Request from a
        # fresh process after resetting the old code signature's permission.
        subprocess.Popen([
            "/bin/sh", "-c",
            'while /bin/kill -0 "$1" 2>/dev/null; do /bin/sleep 0.1; done; '
            '/usr/bin/open "$2" --args --request-accessibility',
            "prism-restart", str(os.getpid()), str(bundle.bundlePath()),
        ], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True)
        AppHelper.callAfter(self.quit)

    def on_main_loaded(self):
        if not self._ready.wait(timeout=10):
            LOG.error("Popup initialization timed out")
            return
        self._main_ready.set()
        self._present_main(self.invalidate())
        if self._request_accessibility and not on_main(accessibility_allowed):
            on_main(request_accessibility)

    def outside_click(self, event):
        if getattr(self, "language_picker", None) and self.language_picker.is_visible():
            window = event.window() if hasattr(event, "window") else None
            point = window.convertPointToScreen_(event.locationInWindow()) if window else AppKit.NSEvent.mouseLocation()
            if AppKit.NSPointInRect(point, self.language_picker.panel.frame()):
                return event
            self.language_picker.hide()
        if self.native and self.native.isVisible():
            card = AppKit.NSInsetRect(self.native.frame(), 12, 12)
            if hasattr(event, "window") and event.window() == self.native:
                point = self.native.convertPointToScreen_(event.locationInWindow())
            else:
                point = AppKit.NSEvent.mouseLocation()
            if not AppKit.NSPointInRect(point, card):
                self.hide_card(restore_focus=False)
        return event

    def hide_card(self, restore_focus=True):
        self.invalidate()
        on_main(self.set_recording, False)
        on_main(self._hide, restore_focus)

    def _hide(self, restore_focus=True):
        if self.language_picker:
            self.language_picker.hide()
        if self.native:
            self.native.orderOut_(None)
        if restore_focus and self._activated and self._return_app and self._return_app.processIdentifier() != os.getpid():
            self._return_app.activateWithOptions_(AppKit.NSApplicationActivateIgnoringOtherApps)
        self._activated = False

    def speak(self, text):
        with self._speech_lock:
            if self._speech and self._speech.poll() is None:
                self._speech.terminate()
            # Text goes through stdin so leading '-' can never become a say option.
            self._speech = subprocess.Popen(["/usr/bin/say"], stdin=subprocess.PIPE,
                                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            process = self._speech
        process.communicate(text.encode("utf-8"))

    def quit(self):
        if self._closed:
            return
        self._closed = True
        self.invalidate()
        self.translator.close()
        self.keyboard.close()
        self.hotkey.close()
        if self._speech and self._speech.poll() is None:
            self._speech.terminate()
        for monitor in self.monitors:
            if monitor:
                AppKit.NSEvent.removeMonitor_(monitor)
        if self.app_delegate:
            Foundation.NSDistributedNotificationCenter.defaultCenter().removeObserver_(self.app_delegate)
        self.capture.shutdown(wait=False, cancel_futures=True)
        self.ui_workers.shutdown(wait=False, cancel_futures=True)
        self.workers.shutdown(wait=False, cancel_futures=True)
        # Cocoa terminates the process, including any bounded in-flight network worker.
        AppKit.NSApplication.sharedApplication().terminate_(None)

    def on_loaded(self):
        try:
            on_main(self.setup_native)
            self.js("initConfig", self.store.snapshot())
            LOG.info("Prism ready")
            LOG.info("Runtime bundle=%s executable=%s accessibility=%s hotkey=%s",
                     Foundation.NSBundle.mainBundle().bundlePath(), sys.executable,
                     on_main(accessibility_allowed), self.store.snapshot()["hotkey"])
        except Exception:
            LOG.exception("Startup failed")

    def run(self):
        from webview.platforms.cocoa import BrowserView
        BrowserView.app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
        # WebKit ignores Electron's -webkit-app-region CSS. Use pywebview's actual
        # drag bridge and restrict it to blank surfaces, never text or controls.
        webview.settings["DRAG_REGION_SELECTOR"] = ".card, .footer"
        webview.settings["DRAG_REGION_DIRECT_TARGET_ONLY"] = True
        self.window = webview.create_window(
            "Prism 翻译", url=(ROOT / "ui.html").as_uri(), width=360, height=125,
            min_size=(360, 80), frameless=True, easy_drag=False, on_top=True,
            transparent=True, hidden=True, focus=True, resizable=False, js_api=self.bridge,
            background_color="#FFFFFF", text_select=True,
        )
        self.window.events.loaded += self.on_loaded
        self.main_window = webview.create_window(
            "Prism", url=(ROOT / "main.html").as_uri(), width=460, height=480,
            min_size=(460, 480), hidden=True, resizable=False, on_top=False,
            js_api=PrismBridge(self, view="main"), background_color="#FAFAFC", text_select=True,
        )
        self.main_window.events.loaded += self.on_main_loaded
        self.main_window.events.closing += self.on_main_closing
        MachSignals.signal(signal.SIGTERM, lambda *_: self.quit())
        MachSignals.signal(signal.SIGINT, lambda *_: self.quit())
        webview.start(gui="cocoa", debug=False, private_mode=True)


def configure_logging():
    directory = Path.home() / "Library" / "Logs" / "Prism"
    directory.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(directory / "prism.log", maxBytes=512000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    LOG.addHandler(handler)
    LOG.setLevel(logging.INFO)


def main():
    parser = argparse.ArgumentParser(description="Prism macOS translation utility")
    parser.add_argument("--config", type=Path, help="Use a separate configuration file")
    parser.add_argument("--request-accessibility", action="store_true", help="Request Accessibility and open System Settings")
    options = parser.parse_args()
    configure_logging()
    lock_path = Path.home() / "Library" / "Caches" / "Prism" / "instance.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("w") as instance_lock:
        try:
            fcntl.flock(instance_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            notify_running_app()
            LOG.info("Reopened the running Prism window")
            return
        PrismApp(options.config, options.request_accessibility).run()


if __name__ == "__main__":
    main()
