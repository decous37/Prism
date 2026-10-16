import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import requests

from geometry import popup_origin
from settings import ConfigStore, DEFAULTS, parse_hotkey, validate_config
from translator import PrismTranslator, TranslationError, sanitize_text, split_text, route_language


class ConfigTests(unittest.TestCase):
    def test_config_roundtrip_and_private_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            store = ConfigStore(path)
            config = store.update({"hotkey": "<shift>+<alt>+k", "engine": "ai"})
            self.assertEqual(config["hotkey_display"], "⌥ ⇧ K")
            self.assertEqual(ConfigStore(path).snapshot(), config)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_rejected_updates_do_not_change_disk_or_memory(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            store = ConfigStore(path)
            store.update({})
            original = path.read_bytes()
            for invalid in ({"engine": "unknown"}, {"hotkey": "x"}, {"ai_model": ""},
                            {"ai_url": "file:///etc/passwd"}, {"ai_url": "https://user:pass@example.com"}):
                with self.assertRaises(ValueError):
                    store.update(invalid)
                self.assertEqual(store.snapshot(), DEFAULTS)
                self.assertEqual(path.read_bytes(), original)

    def test_corrupt_file_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text("broken", encoding="utf-8")
            store = ConfigStore(path)
            self.assertTrue(store.warning)
            self.assertEqual(path.read_text(), "broken")
            store.update({"engine": "light"})
            self.assertEqual(path.with_suffix(".json.invalid").read_text(), "broken")

    def test_unrecordable_hotkeys_rejected(self):
        for key in ("<alt>+escape", "<shift>+x", "<alt>+<alt>+x", "<alt>+≈", "<alt>+", "<foo>+x"):
            with self.assertRaises(ValueError):
                parse_hotkey(key)


class TranslationTests(unittest.TestCase):
    def setUp(self):
        self.translator = PrismTranslator(detector=lambda _: "en")

    def test_pdf_lines_and_paragraphs(self):
        self.assertEqual(sanitize_text("  A long\r\nline\r\n\r\nNext sentence.\r\nNew. "),
                         "A long line\n\nNext sentence.\nNew.")

    def test_chunking_is_lossless_and_bounded(self):
        text = "A sentence. Another sentence.\n\n" * 500
        chunks = split_text(text)
        self.assertEqual("".join(chunks), text)
        self.assertTrue(all(0 < len(chunk) <= 1400 for chunk in chunks))

    def test_routing(self):
        self.assertEqual(route_language("zh-Hant"), ("中文 → EN", "zh-TW", "en"))
        for language in ("en", "ja", "ko", "fr", "de", "ru", "ar"):
            self.assertEqual(route_language(language)[2], "zh-CN")

    def test_empty_and_oversized_text_do_not_send_requests(self):
        with patch.object(self.translator, "_light") as request:
            for text in (" ", "a" * 12001):
                with self.assertRaises(TranslationError):
                    self.translator.translate(text, "light")
            request.assert_not_called()

    def test_cache_separates_backends_and_models(self):
        with patch.object(self.translator, "_light", return_value="你好") as light, \
                patch.object(self.translator, "_ai", return_value="您好") as ai:
            self.translator.translate("hello", "light")
            self.translator.translate("hello", "light")
            self.translator.translate("hello", "ai", ai_model="one")
            self.translator.translate("hello", "ai", ai_model="two")
            self.assertEqual(light.call_count, 1)
            self.assertEqual(ai.call_count, 2)

    def test_cancelled_translation_is_not_sent(self):
        with patch.object(self.translator, "_light") as request:
            with self.assertRaises(TranslationError):
                self.translator.translate("hello", "light", cancel=lambda: True)
            request.assert_not_called()

    def test_engine_apple_never_silently_sends_to_cloud(self):
        self.translator.helper = Path("/missing/prism-helper")
        with patch("requests.Session") as request:
            with self.assertRaises(TranslationError):
                self.translator.translate("hello", "apple")
            request.assert_not_called()

    def test_http_and_timeout_errors_are_actionable(self):
        for error in (requests.Timeout(), requests.ConnectionError()):
            with patch.object(self.translator, "_ai", side_effect=error):
                with self.assertRaises(TranslationError):
                    self.translator.translate("hello", "ai")
        response = Mock(status_code=404)
        with patch.object(self.translator, "_ai", side_effect=requests.HTTPError(response=response)):
            with self.assertRaisesRegex(TranslationError, "模型"):
                self.translator.translate("hello", "ai")

    def test_ai_contract_and_plain_translation(self):
        with patch("requests.post") as request:
            request.return_value.json.return_value = {"choices": [{"message": {"content": "你好"}}]}
            result = self.translator.translate("Hello", "ai")
            payload = request.call_args.kwargs["json"]
            self.assertFalse(payload["stream"])
            self.assertIn("Output only the translation", payload["messages"][0]["content"])
            self.assertEqual(result["result"], "你好")

    def test_malformed_or_empty_response_is_error(self):
        for payload in ({}, {"choices": []}, {"choices": [{"message": {"content": ""}}]}):
            with patch("requests.post") as request:
                request.return_value.json.return_value = payload
                with self.assertRaises(TranslationError):
                    self.translator.translate("Hello", "ai")

    def test_native_protocol_is_utf8_even_with_ascii_desktop_locale(self):
        with tempfile.TemporaryDirectory() as directory:
            helper = Path(directory) / "translate"
            helper.write_text('#!/bin/sh\nprintf \'%s\\n\' \'{"ok":true,"result":"你好，世界。"}\'\n', encoding="utf-8")
            helper.chmod(0o700)
            self.translator.helper = helper
            with patch("locale.getencoding", return_value="US-ASCII"):
                self.assertEqual(self.translator.translate("Hello world", "apple")["result"], "你好，世界。")

    def test_default_hotkey_is_command_option_x(self):
        self.assertEqual(DEFAULTS["hotkey"], "<cmd>+<alt>+x")
        self.assertEqual(DEFAULTS["hotkey_display"], "⌘ ⌥ X")


class GeometryTests(unittest.TestCase):
    def test_edges_and_negative_multimonitor_coordinates(self):
        for visible in ((0, 30, 1440, 850), (-1920, 0, 1920, 1080), (0, 1080, 1920, 1080)):
            left, bottom, width, height = visible
            for mouse in ((left, bottom), (left + width, bottom + height), (left + width, bottom)):
                x, y = popup_origin(mouse, visible, (360, 300))
                self.assertGreaterEqual(x, left)
                self.assertGreaterEqual(y, bottom)
                self.assertLessEqual(x + 360, left + width)
                self.assertLessEqual(y + 300, bottom + height)


if __name__ == "__main__":
    unittest.main()
