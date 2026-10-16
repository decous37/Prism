import unittest
from unittest.mock import Mock, patch

import Quartz

from keyboard import KeyInterceptor


class KeyInterceptorTests(unittest.TestCase):
    def test_enter_is_consumed_until_release_and_runs_copy_hide_once(self):
        controller = Mock(recording=False)
        controller._match_hotkey.return_value = False
        controller.native.isVisible.return_value = True
        interceptor = KeyInterceptor(controller)
        event = object()
        with patch("keyboard.frontmost_pid", return_value=-1), \
                patch("keyboard.AppKit.NSEvent") as ns_event, \
                patch("keyboard.Quartz.CGEventGetIntegerValueField", return_value=36), \
                patch("keyboard.Quartz.CGEventGetFlags", return_value=0):
            ns_event.eventWithCGEvent_.return_value = Mock()
            self.assertIsNone(interceptor._handle(None, Quartz.kCGEventKeyDown, event, None))
            self.assertIsNone(interceptor._handle(None, Quartz.kCGEventKeyDown, event, None))
            self.assertIsNone(interceptor._handle(None, Quartz.kCGEventKeyUp, event, None))
            controller.ui_workers.submit.assert_called_once_with(controller._copy_and_hide)
            self.assertFalse(interceptor.swallowed)

    def test_recording_passes_keys_to_webkit(self):
        controller = Mock(recording=True)
        interceptor = KeyInterceptor(controller)
        event = object()
        with patch("keyboard.Quartz.CGEventGetIntegerValueField", return_value=36):
            self.assertIs(interceptor._handle(None, Quartz.kCGEventKeyDown, event, None), event)
            controller.ui_workers.submit.assert_not_called()

    def test_hidden_popup_does_not_intercept_enter(self):
        controller = Mock(recording=False)
        controller._match_hotkey.return_value = False
        controller.native.isVisible.return_value = False
        interceptor = KeyInterceptor(controller)
        event = object()
        with patch("keyboard.frontmost_pid", return_value=-1), \
                patch("keyboard.AppKit.NSEvent") as ns_event, \
                patch("keyboard.Quartz.CGEventGetIntegerValueField", return_value=36):
            ns_event.eventWithCGEvent_.return_value = Mock()
            self.assertIs(interceptor._handle(None, Quartz.kCGEventKeyDown, event, None), event)
            controller.ui_workers.submit.assert_not_called()
