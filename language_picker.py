"""A five-row native language list, independent of the WebKit card's bounds."""
import AppKit

from geometry import language_picker_origin
from languages import LANGUAGES

ROW_HEIGHT = 28
VISIBLE_ROWS = 5
PICKER_SIZE = (172, ROW_HEIGHT * VISIBLE_ROWS + 8)


class FlippedList(AppKit.NSView):
    def isFlipped(self):
        return True


class PickerActions(AppKit.NSObject):
    def choose_(self, sender):
        self.callback(int(sender.tag()))


class PickerPanel(AppKit.NSPanel):
    def canBecomeKeyWindow(self):
        return True


class LanguagePicker:
    def __init__(self):
        self.panel = PickerPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            AppKit.NSMakeRect(0, 0, *PICKER_SIZE),
            AppKit.NSWindowStyleMaskBorderless | AppKit.NSWindowStyleMaskNonactivatingPanel,
            AppKit.NSBackingStoreBuffered, False)
        self.panel.setReleasedWhenClosed_(False)
        self.panel.setTitle_("Prism")
        self.panel.setOpaque_(False)
        self.panel.setBackgroundColor_(AppKit.NSColor.clearColor())
        self.panel.setHasShadow_(True)
        self.panel.setLevel_(AppKit.NSPopUpMenuWindowLevel)
        self.panel.setCollectionBehavior_(AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
                                          | AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary)
        background = AppKit.NSVisualEffectView.alloc().initWithFrame_(AppKit.NSMakeRect(0, 0, *PICKER_SIZE))
        background.setMaterial_(AppKit.NSVisualEffectMaterialPopover)
        background.setState_(AppKit.NSVisualEffectStateActive)
        background.setWantsLayer_(True)
        background.layer().setCornerRadius_(9)
        background.layer().setMasksToBounds_(True)
        self.panel.setContentView_(background)
        self.scroll = AppKit.NSScrollView.alloc().initWithFrame_(AppKit.NSMakeRect(4, 4, 164, ROW_HEIGHT * VISIBLE_ROWS))
        self.scroll.setHasVerticalScroller_(True)
        self.scroll.setAutohidesScrollers_(True)
        self.scroll.setScrollerStyle_(AppKit.NSScrollerStyleOverlay)
        self.scroll.setDrawsBackground_(False)
        self.document = FlippedList.alloc().initWithFrame_(AppKit.NSMakeRect(0, 0, 164, ROW_HEIGHT * len(LANGUAGES)))
        self.scroll.setDocumentView_(self.document)
        background.addSubview_(self.scroll)
        self.actions = PickerActions.alloc().init()
        self.actions.callback = self._choose
        self.buttons = []
        self.callback = None
        self.index = 0
        for index, (_, title, _, _) in enumerate(LANGUAGES):
            button = AppKit.NSButton.alloc().initWithFrame_(AppKit.NSMakeRect(0, index * ROW_HEIGHT, 164, ROW_HEIGHT))
            button.setTitle_(title)
            button.setFont_(AppKit.NSFont.systemFontOfSize_(12))
            button.setAlignment_(AppKit.NSTextAlignmentLeft)
            button.setBordered_(False)
            button.setButtonType_(AppKit.NSButtonTypeMomentaryChange)
            button.setTag_(index)
            button.setTarget_(self.actions)
            button.setAction_("choose:")
            button.setWantsLayer_(True)
            button.layer().setCornerRadius_(5)
            self.document.addSubview_(button)
            self.buttons.append(button)

    def _choose(self, index):
        callback = self.callback
        self.hide()
        if callback:
            callback(LANGUAGES[index][0])

    def _highlight(self):
        for index, button in enumerate(self.buttons):
            color = (AppKit.NSColor.controlAccentColor().colorWithAlphaComponent_(.15)
                     if index == self.index else AppKit.NSColor.clearColor())
            button.layer().setBackgroundColor_(color.CGColor())

    def show(self, selected, anchor, visible, callback):
        self.callback = callback
        self.index = next((i for i, row in enumerate(LANGUAGES) if row[0] == selected), 0)
        self._highlight()
        offset = max(0, min(self.index - 2, len(LANGUAGES) - VISIBLE_ROWS)) * ROW_HEIGHT
        self.document.scrollPoint_(AppKit.NSMakePoint(0, offset))
        x, y = language_picker_origin(anchor, visible, PICKER_SIZE)
        self.panel.setFrame_display_(AppKit.NSMakeRect(x, y, *PICKER_SIZE), True)
        self.panel.makeKeyAndOrderFront_(None)

    def is_visible(self):
        return bool(self.panel.isVisible())

    def hide(self):
        self.panel.orderOut_(None)
        self.callback = None

    def key(self, code):
        if code == 53:
            self.hide()
        elif code in (36, 76):
            self._choose(self.index)
        elif code in (125, 126):
            self.index = max(0, min(len(LANGUAGES) - 1, self.index + (1 if code == 125 else -1)))
            self._highlight()
            self.document.scrollRectToVisible_(self.buttons[self.index].frame())
        else:
            return False
        return True
