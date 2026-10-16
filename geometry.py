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


def language_picker_origin(anchor, visible, size, gap=5):
    """Place a small list below the badge, or above when the lower edge is near."""
    x, y, width, height = anchor
    left, bottom, screen_width, screen_height = visible
    menu_width, menu_height = size
    top = bottom + screen_height
    below = y - bottom - 8
    above = top - y - height - 8
    if below >= menu_height + gap or below >= above:
        menu_y = y - gap - menu_height
    else:
        menu_y = y + height + gap
    return (max(left + 8, min(x, left + screen_width - menu_width - 8)),
            max(bottom + 8, min(menu_y, top - menu_height - 8)))
