"""Window roles and capture failures must stay separate from the main page."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import AppKit
from webview.event import Event
from main import PrismApp, PrismBridge


class WindowTests(unittest.TestCase):
    def capture_controller(self):
        return SimpleNamespace(selection=Mock(), current=Mock(return_value=True),
                               _show_message=Mock(), _present_main=Mock(),
                               workers=Mock(), _translate=Mock(), _last_selected="old")

    def test_no_selection_shows_popup_message_without_opening_main(self):
        controller = self.capture_controller()
        controller.selection.read.return_value = ""
        PrismApp._capture_then_translate(controller, 123, "position", 1)
        controller._show_message.assert_called_once_with("请先选中文字。", "position", 1)
        controller._present_main.assert_not_called()
        controller.workers.submit.assert_not_called()

    def test_permission_failure_stays_in_popup(self):
        controller = self.capture_controller()
        controller.selection.read.side_effect = PermissionError()
        PrismApp._capture_then_translate(controller, 123, "position", 1)
        controller._show_message.assert_called_once()
        controller._present_main.assert_not_called()
        controller.workers.submit.assert_not_called()

    def test_valid_selection_uses_translation_worker_without_opening_main(self):
        controller = self.capture_controller()
        controller.selection.read.return_value = "Hello"
        PrismApp._capture_then_translate(controller, 123, "position", 1)
        controller.workers.submit.assert_called_once_with(controller._translate, "Hello", "position", 1)
        controller._present_main.assert_not_called()

    def test_main_close_cancels_destruction_and_keeps_process_in_background(self):
        controller = SimpleNamespace(_closed=False, hide_main=Mock())
        closing = Event(None, should_lock=True)
        closing += lambda: PrismApp.on_main_closing(controller)
        self.assertTrue(closing.set())  # pywebview's True means cancel destruction.
        controller.hide_main.assert_called_once()
        controller._closed = True
        self.assertFalse(closing.set())  # Full quit must be allowed to finish.

    def test_hiding_main_orders_out_only_main_and_leaves_popup_independent(self):
        controller = SimpleNamespace(set_recording=Mock(), main_window=Mock(), native=Mock())
        with patch("main.AppKit.NSApplication") as application:
            PrismApp.hide_main(controller)
            application.sharedApplication().setActivationPolicy_.assert_called_once_with(
                AppKit.NSApplicationActivationPolicyAccessory)
        controller.main_window.native.orderOut_.assert_called_once_with(None)
        controller.native.orderOut_.assert_not_called()

    def test_popup_has_no_permission_action(self):
        with patch("main.request_accessibility") as request, patch("main.subprocess.run") as reset:
            self.assertFalse(PrismBridge(Mock()).request_accessibility()["ok"])
            request.assert_not_called()
            reset.assert_not_called()

    def test_invalid_permission_resets_only_prism_before_request(self):
        controller = Mock()
        with patch("main.accessibility_allowed", return_value=False), \
                patch("main.request_accessibility") as request, patch("main.subprocess.run") as reset:
            self.assertTrue(PrismBridge(controller, "main").request_accessibility()["ok"])
            self.assertEqual(reset.call_args.args[0],
                             ["/usr/bin/tccutil", "reset", "Accessibility", "app.prism.translator"])
            controller.restart_for_accessibility.assert_called_once()
            request.assert_not_called()

    def test_valid_permission_is_not_reset_when_opening_settings(self):
        with patch("main.accessibility_allowed", return_value=True), \
                patch("main.request_accessibility") as request, patch("main.subprocess.run") as reset:
            self.assertTrue(PrismBridge(Mock(), "main").request_accessibility()["ok"])
            reset.assert_not_called()
            request.assert_called_once()
