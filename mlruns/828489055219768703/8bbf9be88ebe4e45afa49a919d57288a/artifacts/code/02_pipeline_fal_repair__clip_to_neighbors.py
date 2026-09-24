def _clip_to_neighbors(box, others, *, pad: float = 0.01):
    """Shrink `box` so it does not overlap any box in `others`. For each
    neighbour that overlaps, push whichever of box's edges is nearest the
    neighbour inward past the neighbour's edge (+pad). Neighbour-safety first:
    better to mask slightly less than to eat an adjacent character."""
    x0, y0, x1, y1 = box
    for o in others:
        ox0, oy0, ox1, oy1 = o
        # skip if no overlap
        if x1 <= ox0 or x0 >= ox1 or y1 <= oy0 or y0 >= oy1:
            continue
        # horizontal push: if neighbour is to our left, raise x0; to our right, lower x1
        ncx = (ox0 + ox1) / 2
        bcx = (x0 + x1) / 2
        if ncx < bcx:                 # neighbour on the left → cut left edge
            x0 = max(x0, ox1 + pad)
        else:                         # neighbour on the right → cut right edge
            x1 = min(x1, ox0 - pad)
    if x1 - x0 < 0.03 or y1 - y0 < 0.03:
        return None                   # nothing safe left to mask
    return [x0, y0, x1, y1]
