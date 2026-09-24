def _capsule(draw, box, size, color):
    """Draw an upright capsule (rounded vertical bar) inside a normalised box —
    reads as a single standing body."""
    x0, y0, x1, y1 = box
    px0, py0, px1, py1 = int(x0 * size), int(y0 * size), int(x1 * size), int(y1 * size)
    if px1 - px0 < 4 or py1 - py0 < 4:
        return
    r = max(4, (px1 - px0) // 2)
    draw.rounded_rectangle((px0, py0, px1, py1), radius=r, fill=color)
