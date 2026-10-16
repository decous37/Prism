"""Popup placement in Cocoa's global bottom-left coordinate space."""


def popup_origin(mouse, visible, size, gap=12):
    mx, my = mouse
    left, bottom, width, height = visible
    win_w, win_h = size
    right, top = left + width, bottom + height
    x, y = mx + gap, my - gap - win_h
    if x + win_w > right - 8:
        x = mx - gap - win_w
    if y < bottom + 8:
        y = my + gap
    return (max(left + 8, min(x, right - win_w - 8)),
            max(bottom + 8, min(y, top - win_h - 8)))
