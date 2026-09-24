def _setting_ref(data_dir: str, setting_key: str):
    """(path, description) of the establishing setting plate for a scene's
    setting_key, or (None, '') — this is the piece the first blocking probe
    dropped, which is why the studio background vanished."""
    if not setting_key:
        return None, ""
    try:
        refs = toon_io.load(os.path.join(data_dir, "refs.toon"))
    except Exception:                                        # noqa: BLE001
        return None, ""
    for s in refs.get("settings", []) or []:
        if s.get("key") == setting_key:
            p = s.get("path", "")
            # paths in refs.toon are book-relative (v3_kimi/refs/...); resolve
            book_root = os.path.dirname(data_dir.rstrip("/"))
            full = p if os.path.isabs(p) else os.path.join(book_root, os.path.basename(os.path.dirname(p)), os.path.basename(p))
            if not os.path.exists(full):
                full = os.path.join(book_root, p.split("/", 1)[-1]) if "/" in p else p
            return (full if os.path.exists(full) else None), s.get("description", "")
    return None, ""
