import unittest
from unittest.mock import Mock, patch

import requests

from ai_models import ModelStartError, OllamaModels

URL = "http://localhost:11434/v1/chat/completions"


def response(payload, status=200):
    value = Mock(status_code=status)
    value.json.return_value = payload
    return value


class ModelTests(unittest.TestCase):
    def test_stopped_service_is_started_and_installed_model_loaded(self):
        manager = OllamaModels()
        with patch("ai_models.requests.Session") as session_class, patch.object(manager, "_launch_service") as launch:
            session = session_class.return_value.__enter__.return_value
            session.get.side_effect = [requests.ConnectionError(), response({"models": [{"name": "qwen2.5:7b"}]}), response({"models": []})]
            session.post.return_value = response({"done": True})
            self.assertTrue(manager.start(URL, "qwen2.5:7b")["ok"])
            launch.assert_called_once()
            self.assertEqual(session.post.call_args.kwargs["json"], {
                "model": "qwen2.5:7b", "prompt": "", "stream": False, "keep_alive": "15m"})

    def test_loaded_model_is_not_loaded_again(self):
        manager = OllamaModels()
        with patch("ai_models.requests.Session") as session_class:
            session = session_class.return_value.__enter__.return_value
            session.get.return_value = response({"models": [{"name": "qwen2.5:7b"}]})
            self.assertEqual(manager.start(URL, "qwen2.5:7b")["message"], "模型已就绪")
            session.post.assert_not_called()

    def test_missing_model_has_actionable_error_and_is_not_downloaded(self):
        with patch("ai_models.requests.Session") as session_class:
            session = session_class.return_value.__enter__.return_value
            session.get.return_value = response({"models": []})
            with self.assertRaisesRegex(ModelStartError, "未找到模型"):
                OllamaModels().start(URL, "missing:7b")
            session.post.assert_not_called()

    def test_remote_provider_never_starts_a_local_service(self):
        with patch("ai_models.requests.Session") as session_class:
            with self.assertRaisesRegex(ModelStartError, "本机 Ollama"):
                OllamaModels().start("https://example.com/v1/chat/completions", "model")
            session_class.assert_not_called()

    def test_loading_timeout_is_reported(self):
        with patch("ai_models.requests.Session") as session_class:
            session = session_class.return_value.__enter__.return_value
            session.get.side_effect = [response({"models": [{"name": "qwen2.5:7b"}]}), response({"models": []})]
            session.post.side_effect = requests.Timeout()
            with self.assertRaisesRegex(ModelStartError, "超时"):
                OllamaModels().start(URL, "qwen2.5:7b")
