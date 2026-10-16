from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import AppKit
from main import PrismApp


class OutsideClickTests(unittest.TestCase):
    def test_only_clicks_outside_the_card_dismiss_and_preserve_other_app_focus(self):
        native = Mock()
        native.isVisible.return_value = True
        native.frame.return_value = AppKit.NSMakeRect(50, 50, 360, 200)
        controller = SimpleNamespace(native=native, hide_card=Mock())
        event = object()
        with patch("main.AppKit.NSEvent") as events:
            events.mouseLocation.return_value = AppKit.NSMakePoint(150, 150)
            self.assertIs(PrismApp.outside_click(controller, event), event)
            controller.hide_card.assert_not_called()
            events.mouseLocation.return_value = AppKit.NSMakePoint(500, 500)
            self.assertIs(PrismApp.outside_click(controller, event), event)
            controller.hide_card.assert_called_once_with(restore_focus=False)

    def test_hidden_window_does_not_interfere_with_clicks(self):
        native = Mock()
        native.isVisible.return_value = False
        controller = SimpleNamespace(native=native, hide_card=Mock())
        event = object()
        self.assertIs(PrismApp.outside_click(controller, event), event)
        controller.hide_card.assert_not_called()

    def test_local_click_uses_its_own_event_position(self):
        native = Mock()
        native.isVisible.return_value = True
        native.frame.return_value = AppKit.NSMakeRect(50, 50, 360, 200)
        native.convertPointToScreen_.return_value = AppKit.NSMakePoint(150, 150)
        event = Mock()
        event.window.return_value = native
        controller = SimpleNamespace(native=native, hide_card=Mock())
        with patch("main.AppKit.NSEvent") as events:
            events.mouseLocation.return_value = AppKit.NSMakePoint(500, 500)
            self.assertIs(PrismApp.outside_click(controller, event), event)
            controller.hide_card.assert_not_called()
