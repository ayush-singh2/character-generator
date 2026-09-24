def _is_erase(issue: str) -> bool:
    s = (issue or "").lower()
    if any(h in s for h in _REDRAW_HINTS) and not any(h in s for h in _ERASE_HINTS):
        return False
    if any(h in s for h in _ERASE_HINTS):
        return True
    # default: prefer ERASE (identity-safe) unless clearly a whole-figure redraw
    return True
