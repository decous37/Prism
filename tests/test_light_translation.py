import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from email.utils import formatdate
from unittest.mock import Mock, patch

import requests

from translator import PrismTranslator, TranslationError


class Clock:
    def __init__(self):
        self.now = 100.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def response(status=200, text="你好", retry_after=None):
    result = Mock(status_code=status, headers={})
    if retry_after is not None:
        result.headers["Retry-After"] = retry_after
    result.json.return_value = [[[text]]]
    if status >= 400:
        result.raise_for_status.side_effect = requests.HTTPError(response=result)
    return result


class LightTranslationTests(unittest.TestCase):
    def setUp(self):
        self.translator = PrismTranslator(detector=lambda _: "en")
        self.clock = Clock()
        self.session = Mock()
        session_patch = patch("translator.requests.Session")
        session_patch.start().return_value.__enter__.return_value = self.session
        self.addCleanup(session_patch.stop)
        clock_patch = patch("translator.time.monotonic", self.clock.monotonic)
        clock_patch.start()
        self.addCleanup(clock_patch.stop)
        sleep_patch = patch("translator.time.sleep", self.clock.sleep)
        sleep_patch.start()
        self.addCleanup(sleep_patch.stop)
        self.session.get.return_value = response()

    def translate(self, text="Hello", **kwargs):
        return self.translator.translate(text, "light", **kwargs)

    def test_429_sends_once_and_blocks_new_requests_until_retry_after(self):
        self.session.get.return_value = response(429, retry_after="120")
        with self.assertRaisesRegex(TranslationError, "120 秒"):
            self.translate()
        self.clock.now += 30
        with self.assertRaisesRegex(TranslationError, "90 秒"):
            self.translate("Another selection")
        self.assertEqual(self.session.get.call_count, 1)
        self.clock.now += 90
        self.session.get.return_value = response()
        self.assertEqual(self.translate()["result"], "你好")
        self.assertEqual(self.session.get.call_count, 2)

    def test_missing_header_uses_backoff_and_success_resets_it(self):
        self.session.get.return_value = response(429)
        for delay in (60, 120):
            with self.assertRaisesRegex(TranslationError, f"{delay} 秒"):
                self.translate()
            self.clock.now += delay
        self.session.get.return_value = response()
        self.translate()
        self.session.get.return_value = response(429)
        with self.assertRaisesRegex(TranslationError, "60 秒"):
            self.translate("Different selection")

    def test_http_date_retry_after_and_invalid_values(self):
        with patch("translator.time.time", return_value=1_700_000_000):
            self.session.get.return_value = response(429, retry_after=formatdate(1_700_000_300, usegmt=True))
            with self.assertRaisesRegex(TranslationError, "300 秒"):
                self.translate()
        for invalid in (None, "bad date", "NaN", "inf", "-12"):
            self.assertEqual(self.translator._retry_after(invalid), 0)

    def test_chunks_and_selections_are_spaced_and_cached(self):
        starts = []
        def get(*args, **kwargs):
            starts.append(self.clock.now)
            return response(text=kwargs["params"]["q"])
        self.session.get.side_effect = get
        text = "a" * 1400 + "b"
        self.assertEqual(self.translate(text)["result"], "a" * 1400 + "\nb")
        self.translate("Next selection")
        self.assertEqual(starts, [100.0, 101.0, 102.0])
        self.translate(text)
        self.assertEqual(len(starts), 3)

    def test_cache_is_available_during_cooldown_and_separates_languages(self):
        self.translate()
        self.session.get.return_value = response(429)
        with self.assertRaises(TranslationError):
            self.translate("Another selection")
        self.assertEqual(self.translate()["result"], "你好")
        with self.assertRaises(TranslationError):
            self.translate(target="ja")
        self.assertEqual(self.session.get.call_count, 2)

    def test_partial_result_reused_after_cancellation(self):
        cancelled = threading.Event()
        def get(*args, **kwargs):
            cancelled.set()
            return response(text="第一段")
        self.session.get.side_effect = get
        text = "a" * 1400 + "b"
        with self.assertRaisesRegex(TranslationError, "取消"):
            self.translate(text, cancel=cancelled.is_set)
        self.assertEqual(self.session.get.call_count, 1)
        self.session.get.side_effect = None
        self.session.get.return_value = response(text="第二段")
        self.assertEqual(self.translate(text)["result"], "第一段\n第二段")
        self.assertEqual(self.session.get.call_count, 2)

    def test_cancelled_wait_does_not_send_another_request(self):
        self.translate()
        cancelled = threading.Event()
        def sleep(seconds):
            cancelled.set()
            self.clock.sleep(seconds)
        with patch("translator.time.sleep", sleep):
            with self.assertRaisesRegex(TranslationError, "取消"):
                self.translate("Different selection", cancel=cancelled.is_set)
        self.assertEqual(self.session.get.call_count, 1)

    def test_identical_concurrent_requests_share_one_network_result(self):
        entered = threading.Event()
        release = threading.Event()
        second_entered = threading.Event()
        def get(*args, **kwargs):
            entered.set()
            self.assertTrue(release.wait(2))
            return response()
        def second():
            # translate() checks cancellation after its full-result cache miss.
            def cancel():
                second_entered.set()
                return False
            return self.translate(cancel=cancel)
        self.session.get.side_effect = get
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(self.translate)
            try:
                self.assertTrue(entered.wait(2))
                other = pool.submit(second)
                self.assertTrue(second_entered.wait(2))
            finally:
                release.set()
            self.assertEqual(first.result(timeout=2), other.result(timeout=2))
        self.assertEqual(self.session.get.call_count, 1)

    def test_invalid_response_is_not_cached(self):
        for payload in ([], [[[""]]], [[[5]]]):
            self.session.get.return_value.json.return_value = payload
            with self.assertRaises(TranslationError):
                self.translate()
        self.session.get.return_value = response()
        self.assertEqual(self.translate()["result"], "你好")
        self.assertEqual(self.session.get.call_count, 4)

    def test_close_stops_queued_cloud_work(self):
        self.translator.close()
        with self.assertRaisesRegex(TranslationError, "退出"):
            self.translate()
        self.session.get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
