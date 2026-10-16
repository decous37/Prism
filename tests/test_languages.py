import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import AppKit

from geometry import language_picker_origin
from language_picker import PICKER_SIZE, ROW_HEIGHT, VISIBLE_ROWS
from main import PrismApp
from translator import PrismTranslator, TranslationError


class LanguageTests(unittest.TestCase):
    def test_picker_selection_returns_keyboard_focus_to_card(self):
        picker = Mock()
        picker.is_visible.side_effect = [True, False]
        picker.key.return_value = True
        controller = SimpleNamespace(recording=False, language_picker=picker, native=Mock())
        event = Mock()
        event.keyCode.return_value = 36
        self.assertIsNone(PrismApp._event(controller, event, local=True))
        controller.native.makeKeyAndOrderFront_.assert_called_once_with(None)

    def test_each_engine_receives_both_manual_languages(self):
        translator = PrismTranslator(detector=lambda _: "en")
        for engine in ("apple", "light", "ai"):
            method = "_" + engine
            with patch.object(translator, method, return_value="Bonjour") as request:
                result = translator.translate("Hello", engine, source="ja", target="fr")
                self.assertEqual((result["source"], result["target"]), ("ja", "fr"))
                self.assertTrue(result["badge"].startswith("日语 → 法语"))
                if engine == "ai":
                    self.assertEqual(request.call_args.args[1], "fr")
                    self.assertEqual(request.call_args.kwargs["source"], "ja")
                else:
                    self.assertEqual(request.call_args.args[:3], ("Hello", "ja", "fr"))

    def test_cache_separates_target_and_source_overrides(self):
        translator = PrismTranslator(detector=lambda _: "en")
        with patch.object(translator, "_light", return_value="translated") as request:
            for source, target in [("en", "ja"), ("en", "fr"), ("de", "fr"), ("en", "ja")]:
                translator.translate("Hello", "light", source=source, target=target)
            self.assertEqual(request.call_count, 3)

    def test_same_language_returns_original_without_network(self):
        translator = PrismTranslator(detector=lambda _: "en")
        with patch.object(translator, "_light") as request:
            result = translator.translate("Hello", "light", source="en", target="en")
            self.assertEqual(result["result"], "Hello")
            request.assert_not_called()

    def test_invalid_language_never_sends_request(self):
        translator = PrismTranslator(detector=lambda _: "en")
        with patch.object(translator, "_light") as request:
            for language in ("invalid", [], 3):
                with self.assertRaises(TranslationError):
                    translator.translate("Hello", "light", target=language)
            request.assert_not_called()

    def test_manual_change_reuses_original_and_preserves_other_side(self):
        controller = SimpleNamespace(_route={"source": "en", "target": "zh-CN"},
                                     current=Mock(return_value=True), native=Mock(), retranslate=Mock())
        PrismApp.set_language(controller, "target", "ja", 1)
        self.assertEqual(controller._route, {"source": "en", "target": "ja"})
        PrismApp.set_language(controller, "source", "fr", 1)
        self.assertEqual(controller._route, {"source": "fr", "target": "ja"})
        controller.current.return_value = False
        PrismApp.set_language(controller, "target", "ko", 1)
        self.assertEqual(controller._route["target"], "ja")
        self.assertEqual(controller.retranslate.call_count, 2)

    def test_retranslate_uses_existing_text_route_and_position(self):
        controller = SimpleNamespace(_last_selected="original selection", native=Mock(),
                                     _mouse=(20, 30), _visible=(0, 0, 900, 900),
                                     _route={"source": "ja", "target": "fr"},
                                     invalidate=Mock(return_value=3), workers=Mock(), _translate=Mock())
        PrismApp.retranslate(controller)
        controller.workers.submit.assert_called_once_with(controller._translate, "original selection",
            ((20, 30), (0, 0, 900, 900)), 3, False, {"source": "ja", "target": "fr"})

    def test_loading_and_error_keep_language_choices(self):
        translator = PrismTranslator(detector=lambda _: "en")
        translator.translate = Mock(side_effect=TranslationError("Unavailable"))
        controller = SimpleNamespace(current=Mock(return_value=True), translator=translator,
            _state_lock=threading.RLock(), js=Mock(), _show_if_current=Mock(),
            store=SimpleNamespace(snapshot=lambda: {"engine": "apple", "ai_url": "", "ai_model": ""}))
        PrismApp._translate(controller, "Hello", "placement", 1, False, {"source": "en", "target": "ko"})
        self.assertEqual(controller._route, {"source": "en", "target": "ko"})
        name, data, _ = controller.js.call_args.args
        self.assertEqual(name, "renderMessage")
        self.assertEqual(data["target"], "ko")

    def test_picker_has_five_visible_rows_and_fits_above_or_below(self):
        self.assertEqual(VISIBLE_ROWS, 5)
        self.assertEqual(PICKER_SIZE[1] - 8, 5 * ROW_HEIGHT)
        visible = (-900, 30, 900, 700)
        low = (-100, 50, 40, 20)
        high = (-100, 690, 40, 20)
        for anchor in (low, high):
            x, y = language_picker_origin(anchor, visible, PICKER_SIZE)
            self.assertGreaterEqual(x, -892)
            self.assertLessEqual(x + PICKER_SIZE[0], -8)
            self.assertGreaterEqual(y, 38)
            self.assertLessEqual(y + PICKER_SIZE[1], 722)
        self.assertGreater(language_picker_origin(low, visible, PICKER_SIZE)[1], low[1] + low[3])
        self.assertLess(language_picker_origin(high, visible, PICKER_SIZE)[1] + PICKER_SIZE[1], high[1])

    def test_clicking_language_list_keeps_card_open(self):
        picker = Mock()
        picker.is_visible.return_value = True
        picker.panel.frame.return_value = AppKit.NSMakeRect(100, 100, *PICKER_SIZE)
        native = Mock()
        native.isVisible.return_value = True
        native.frame.return_value = AppKit.NSMakeRect(100, 300, 360, 130)
        controller = SimpleNamespace(language_picker=picker, native=native, hide_card=Mock())
        with patch("main.AppKit.NSEvent") as events:
            events.mouseLocation.return_value = AppKit.NSMakePoint(120, 120)
            PrismApp.outside_click(controller, object())
            picker.hide.assert_not_called()
            controller.hide_card.assert_not_called()
            events.mouseLocation.return_value = AppKit.NSMakePoint(800, 800)
            PrismApp.outside_click(controller, object())
            picker.hide.assert_called_once()
            controller.hide_card.assert_called_once_with(restore_focus=False)
