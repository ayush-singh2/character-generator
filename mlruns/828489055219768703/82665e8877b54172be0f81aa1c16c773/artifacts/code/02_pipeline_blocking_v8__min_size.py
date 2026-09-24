def _min_size(box):
    """Grow a too-small box around its centre to a minimum footprint, clamped
    to frame — so a small character (e.g. Twiggy) isn't dropped by the model."""
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    w, h = max(x1 - x0, MIN_W), max(y1 - y0, MIN_H)
    nx0, nx1 = max(0.0, cx - w / 2), min(1.0, cx + w / 2)
    ny0, ny1 = max(0.0, cy - h / 2), min(1.0, cy + h / 2)
    return [nx0, ny0, nx1, ny1]
