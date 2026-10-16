"""Selection and pasteboard tests never type into the user's foreground app."""
import unittest
from unittest.mock import Mock, patch
import uuid
import macos


class SelectionTests(unittest.TestCase):
    def test_ax_selection_never_touches_clipboard(self):
        with patch("macos.on_main", side_effect=lambda fn, *a: fn(*a)), \
                patch("macos.accessibility_allowed", return_value=True), \
                patch("macos.ax_selected_text", return_value="selected text"), \
                patch("macos.clipboard_snapshot") as snapshot:
            self.assertEqual(macos.SelectionReader().read(1234), "selected text")
            snapshot.assert_not_called()

    def test_permission_failure_never_copies(self):
        with patch("macos.on_main", side_effect=lambda fn, *a: fn(*a)), \
                patch("macos.accessibility_allowed", return_value=False), \
                patch("macos.Quartz.CGEventPost") as post:
            with self.assertRaises(PermissionError):
                macos.SelectionReader().read(1234)
            post.assert_not_called()

    def test_restore_does_not_overwrite_a_new_user_copy(self):
        pasteboard = Mock()
        pasteboard.changeCount.return_value = 99
        with patch("macos.AppKit.NSPasteboard") as pasteboard_class:
            pasteboard_class.generalPasteboard.return_value = pasteboard
            self.assertFalse(macos.clipboard_restore(98, [{"public.utf8-plain-text": b"old"}]))
            pasteboard.clearContents.assert_not_called()

    def test_cancelled_capture_does_nothing(self):
        with patch("macos.on_main") as dispatch:
            self.assertEqual(macos.SelectionReader().read(1234, lambda: True), "")
            dispatch.assert_not_called()

    def test_rich_clipboard_roundtrip_in_private_pasteboard(self):
        # Exercise real Cocoa serialization without touching the user's pasteboard.
        pasteboard_class = macos.AppKit.NSPasteboard
        pasteboard = pasteboard_class.pasteboardWithName_("prism-test-" + uuid.uuid4().hex)
        contents = [
            {"public.utf8-plain-text": "旧剪贴板".encode("utf-8"), "public.html": b"<b>original</b>"},
            {"public.png": b"\x89PNG\r\n\x1a\n\x00test"},
        ]
        try:
            with patch("macos.AppKit.NSPasteboard") as facade:
                facade.generalPasteboard.return_value = pasteboard
                self.assertTrue(macos.clipboard_restore(pasteboard.changeCount(), contents))
                original_count, snapshot = macos.clipboard_snapshot()
                self.assertEqual(snapshot, contents)
                self.assertTrue(macos.copy_text("temporary selection"))
                copied_count, value = macos.clipboard_read()
                self.assertNotEqual(original_count, copied_count)
                self.assertEqual(value, "temporary selection")
                self.assertTrue(macos.clipboard_restore(copied_count, snapshot))
                self.assertEqual(macos.clipboard_snapshot()[1], contents)
        finally:
            pasteboard.releaseGlobally()


if __name__ == "__main__":
    unittest.main()
