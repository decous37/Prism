"""Carbon global hotkeys work even while Accessibility authorization is pending."""
import ctypes as C

from settings import parse_hotkey

KEY_CODES = dict(zip(
    "asdfhgzxcv" + "bqwerty123465=97-80]ou[iplj'k;\\,/nm.",
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17,
     18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33,
     34, 35, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47], strict=True))


class EventType(C.Structure):
    _fields_ = [("event_class", C.c_uint32), ("kind", C.c_uint32)]


class HotkeyID(C.Structure):
    _fields_ = [("signature", C.c_uint32), ("identifier", C.c_uint32)]


CALLBACK = C.CFUNCTYPE(C.c_int32, C.c_void_p, C.c_void_p, C.c_void_p)


class GlobalHotkey:
    def __init__(self, callback):
        self.callback = callback
        self.library = C.CDLL("/System/Library/Frameworks/Carbon.framework/Carbon")
        self.library.GetApplicationEventTarget.restype = C.c_void_p
        self.library.InstallEventHandler.argtypes = [C.c_void_p, CALLBACK, C.c_uint32,
                                                     C.POINTER(EventType), C.c_void_p, C.POINTER(C.c_void_p)]
        self.library.InstallEventHandler.restype = C.c_int32
        self.library.RegisterEventHotKey.argtypes = [C.c_uint32, C.c_uint32, HotkeyID,
                                                     C.c_void_p, C.c_uint32, C.POINTER(C.c_void_p)]
        self.library.RegisterEventHotKey.restype = C.c_int32
        self.library.UnregisterEventHotKey.argtypes = [C.c_void_p]
        self.library.RemoveEventHandler.argtypes = [C.c_void_p]
        self.handler = C.c_void_p()
        self.reference = C.c_void_p()
        self.definition = None
        self.native_callback = CALLBACK(self._invoke)

    def _invoke(self, next_handler, event, context):
        self.callback()
        return 0

    def register(self, definition):
        modifiers, key = parse_hotkey(definition)
        if self.reference and self.definition == definition:
            return
        target = self.library.GetApplicationEventTarget()
        if not self.handler:
            spec = EventType(0x6B657962, 6)  # kEventClassKeyboard, kEventHotKeyPressed
            status = self.library.InstallEventHandler(target, self.native_callback, 1,
                                                     C.byref(spec), None, C.byref(self.handler))
            if status:
                raise ValueError(f"无法注册全局快捷键（{status}）")
        masks = {"<cmd>": 1 << 8, "<shift>": 1 << 9, "<alt>": 1 << 11, "<ctrl>": 1 << 12}
        reference = C.c_void_p()
        status = self.library.RegisterEventHotKey(KEY_CODES[key], sum(masks[m] for m in modifiers),
                                                 HotkeyID(0x5072736D, 1), target, 0, C.byref(reference))
        if status:
            raise ValueError("此快捷键已被其他应用占用，请换一个组合。" if status == -9878
                             else f"快捷键注册失败（{status}），请换一个组合。")
        self.pause()
        self.reference = reference
        self.definition = definition

    def pause(self):
        if self.reference:
            self.library.UnregisterEventHotKey(self.reference)
            self.reference = C.c_void_p()

    def close(self):
        self.pause()
        if self.handler:
            self.library.RemoveEventHandler(self.handler)
            self.handler = C.c_void_p()
