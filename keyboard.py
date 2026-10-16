"""Consume Prism's keys so a passive popup never types into the source app."""
import logging
import os

import AppKit
import Quartz

from macos import frontmost_pid

LOG = logging.getLogger("prism")


class KeyInterceptor:
    def __init__(self, controller):
        self.controller = controller
        self.tap = None
        self.source = None
        self.swallowed = set()
        self.callback = self._handle

    def start(self):
        if self.tap:
            return True
        mask = (1 << Quartz.kCGEventKeyDown) | (1 << Quartz.kCGEventKeyUp)
        self.tap = Quartz.CGEventTapCreate(Quartz.kCGSessionEventTap, Quartz.kCGHeadInsertEventTap,
                                         Quartz.kCGEventTapOptionDefault, mask, self.callback, None)
        if not self.tap:
            return False
        self.source = Quartz.CFMachPortCreateRunLoopSource(None, self.tap, 0)
        Quartz.CFRunLoopAddSource(Quartz.CFRunLoopGetMain(), self.source, Quartz.kCFRunLoopCommonModes)
        Quartz.CGEventTapEnable(self.tap, True)
        return True

    def _handle(self, proxy, event_type, event, context):
        try:
            if event_type in (Quartz.kCGEventTapDisabledByTimeout, Quartz.kCGEventTapDisabledByUserInput):
                if self.tap:
                    Quartz.CGEventTapEnable(self.tap, True)
                return event
            code = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
            if code in self.swallowed:
                if event_type == Quartz.kCGEventKeyUp:
                    self.swallowed.discard(code)
                return None
            if event_type != Quartz.kCGEventKeyDown or self.controller.recording:
                return event
            # Focused Prism input is handled by WebKit and the local NSEvent monitor.
            if frontmost_pid() == os.getpid():
                return event
            native_event = AppKit.NSEvent.eventWithCGEvent_(event)
            if native_event and self.controller._match_hotkey(native_event):
                self.swallowed.add(code)
                self.controller._event(native_event)
                return None
            if self.controller.native and self.controller.native.isVisible():
                flags = Quartz.CGEventGetFlags(event)
                modifiers = (Quartz.kCGEventFlagMaskCommand | Quartz.kCGEventFlagMaskAlternate
                             | Quartz.kCGEventFlagMaskControl | Quartz.kCGEventFlagMaskShift)
                if code == 53:
                    self.swallowed.add(code)
                    self.controller.hide_card()
                    return None
                if code in (36, 76) and not flags & modifiers:
                    self.swallowed.add(code)
                    self.controller.ui_workers.submit(self.controller._copy_and_hide)
                    return None
        except Exception:
            LOG.exception("Keyboard interception failed")
        return event

    def close(self):
        if self.source:
            Quartz.CFRunLoopRemoveSource(Quartz.CFRunLoopGetMain(), self.source, Quartz.kCFRunLoopCommonModes)
        if self.tap:
            Quartz.CFMachPortInvalidate(self.tap)
        self.source = self.tap = None
        self.swallowed.clear()
