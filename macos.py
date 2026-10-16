"""Cocoa integration. All AppKit/Accessibility access is marshalled to the main thread."""
from __future__ import annotations

from concurrent.futures import Future
import os
import threading
import time

import AppKit
import ApplicationServices as AX
import Foundation
import Quartz
from PyObjCTools import AppHelper


def on_main(function, *args):
    if Foundation.NSThread.isMainThread():
        return function(*args)
    future = Future()

    def invoke():
        if not future.set_running_or_notify_cancel():
            return
        try:
            future.set_result(function(*args))
        except BaseException as exc:
            future.set_exception(exc)

    AppHelper.callAfter(invoke)
    try:
        return future.result(timeout=8)
    except TimeoutError:
        future.cancel()
        raise


def frontmost_pid():
    application = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
    return application.processIdentifier() if application else None


def accessibility_allowed(prompt=False):
    return bool(AX.AXIsProcessTrustedWithOptions({AX.kAXTrustedCheckOptionPrompt: bool(prompt)}))


def ax_selected_text(pid):
    if not pid:
        return ""
    application = AX.AXUIElementCreateApplication(pid)
    AX.AXUIElementSetMessagingTimeout(application, 0.4)
    status, element = AX.AXUIElementCopyAttributeValue(application, AX.kAXFocusedUIElementAttribute, None)
    if status != AX.kAXErrorSuccess or element is None:
        return ""
    status, text = AX.AXUIElementCopyAttributeValue(element, AX.kAXSelectedTextAttribute, None)
    return str(text).strip() if status == AX.kAXErrorSuccess and text else ""


def clipboard_snapshot():
    pasteboard = AppKit.NSPasteboard.generalPasteboard()
    items = []
    for item in pasteboard.pasteboardItems() or []:
        types = {}
        for content_type in item.types():
            data = item.dataForType_(content_type)
            if data is not None:
                types[str(content_type)] = bytes(data)
        items.append(types)
    return pasteboard.changeCount(), items


def clipboard_read():
    pasteboard = AppKit.NSPasteboard.generalPasteboard()
    return pasteboard.changeCount(), str(pasteboard.stringForType_(AppKit.NSPasteboardTypeString) or "")


def clipboard_restore(expected_count, snapshot):
    pasteboard = AppKit.NSPasteboard.generalPasteboard()
    # A user's subsequent copy always wins over our restoration.
    if pasteboard.changeCount() != expected_count:
        return False
    items = []
    for content in snapshot:
        item = AppKit.NSPasteboardItem.alloc().init()
        for content_type, value in content.items():
            data = Foundation.NSData.dataWithBytes_length_(value, len(value))
            item.setData_forType_(data, content_type)
        items.append(item)
    pasteboard.clearContents()
    if items:
        pasteboard.writeObjects_(items)
    return True


def copy_text(text):
    pasteboard = AppKit.NSPasteboard.generalPasteboard()
    pasteboard.clearContents()
    return bool(pasteboard.setString_forType_(text, AppKit.NSPasteboardTypeString))


class SelectionReader:
    def __init__(self):
        self._lock = threading.Lock()

    def read(self, pid, cancelled=lambda: False):
        with self._lock:
            if cancelled():
                return ""
            if not on_main(accessibility_allowed):
                raise PermissionError("请先授权辅助功能。")
            selected = on_main(ax_selected_text, pid)
            if selected:
                return selected
            # Wait for physical modifiers to be released; generated events also set exact flags.
            deadline = time.monotonic() + 0.7
            time.sleep(0.15)
            modifier_mask = (Quartz.kCGEventFlagMaskAlternate | Quartz.kCGEventFlagMaskCommand
                             | Quartz.kCGEventFlagMaskControl | Quartz.kCGEventFlagMaskShift)
            while Quartz.CGEventSourceFlagsState(Quartz.kCGEventSourceStateCombinedSessionState) & modifier_mask:
                if time.monotonic() >= deadline or cancelled():
                    break
                time.sleep(0.02)
            if cancelled() or on_main(frontmost_pid) != pid or pid == os.getpid():
                return ""
            original_count, snapshot = on_main(clipboard_snapshot)
            source = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStatePrivate)
            for pressed in (True, False):
                event = Quartz.CGEventCreateKeyboardEvent(source, 8, pressed)  # ANSI C
                Quartz.CGEventSetFlags(event, Quartz.kCGEventFlagMaskCommand)
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
            copied_count = original_count
            result = ""
            try:
                deadline = time.monotonic() + 0.8
                while time.monotonic() < deadline:
                    time.sleep(0.02)
                    copied_count, result = on_main(clipboard_read)
                    if copied_count != original_count:
                        break
                if copied_count == original_count:
                    return ""  # Never translate an unrelated, stale clipboard value.
                return result.strip()
            finally:
                if copied_count != original_count:
                    on_main(clipboard_restore, copied_count, snapshot)


def request_accessibility():
    accessibility_allowed(prompt=True)
    url = Foundation.NSURL.URLWithString_(
        "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility")
    AppKit.NSWorkspace.sharedWorkspace().openURL_(url)


REOPEN_NOTIFICATION = "app.prism.translator.reopen"


def notify_running_app():
    Foundation.NSDistributedNotificationCenter.defaultCenter().postNotificationName_object_userInfo_deliverImmediately_(
        REOPEN_NOTIFICATION, None, None, True)


def install_reopen_delegate(application, controller):
    import objc

    class PrismApplicationDelegate(type(application.delegate())):
        @objc.signature(b"Z@:@Z")
        def applicationShouldHandleReopen_hasVisibleWindows_(self, sender, visible):
            self.controller.reopen()
            return False

        def showRequested_(self, notification):
            self.controller.reopen()

    delegate = PrismApplicationDelegate.alloc().init()
    delegate.controller = controller
    application.setDelegate_(delegate)
    Foundation.NSDistributedNotificationCenter.defaultCenter().addObserver_selector_name_object_(
        delegate, "showRequested:", REOPEN_NOTIFICATION, None)
    return delegate
