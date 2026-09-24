def _faint(i: int):
    v = max(200, FAINT_BASE - (i % 6) * FAINT_STEP)
    return (v, v, v)
