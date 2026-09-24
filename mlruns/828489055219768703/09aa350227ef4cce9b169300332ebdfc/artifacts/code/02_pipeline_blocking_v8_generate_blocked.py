def generate_blocked(pid: str, book_dir: str, *, faint: bool = True):
    """Full setting-aware blocking generation for one page. Feeds, IN ORDER:
    [blocking guide, setting plate, character sheets] into the image editor with
    an instruction that (a) keeps the real setting background, (b) follows the
    blocking for position/scale/negative-space, (c) forces ONE upright body per
    character. Returns the rendered PNG bytes. This is the fix for the
    background-regression: the first probe omitted the setting plate.
    """
    from . import editor  # local import: editor pulls network deps
    data_dir = os.path.join(book_dir, "data")
    layouts = _load_layout(data_dir)
    scenes = {str(s.get("page")): s for s in
              toon_io.load(os.path.join(data_dir, "scenes.toon"))["scenes"]}
    entry = layouts.get(str(pid))
    sc = scenes.get(str(pid))
    if not entry or not sc:
        raise SystemExit(f"no layout/scene for page {pid}")

    present = [c.get("name") for c in (entry.get("chars") or []) if c.get("name")]
    # character reference sheets (skip the auto placeholder duplicates)
    refs = []
    for nm in dict.fromkeys(present):                       # de-dup, keep order
        p = os.path.join(book_dir, "refs", f"{nm.lower()}.png")
        if os.path.exists(p):
            refs.append(open(p, "rb").read())

    set_path, set_desc = _setting_ref(data_dir, sc.get("setting_key"))
    setting_bytes = [open(set_path, "rb").read()] if set_path else []

    import io as _io
    blk = build_blocking(entry, faint=faint)
    buf = _io.BytesIO(); blk.save(buf, "PNG")

    desc = (sc.get("illustration") or sc.get("action") or "")[:600]
    if present:
        roster = ", ".join(dict.fromkeys(present))
        instr = (
            f"Illustrate this children's yoga-book page in the SAME soft "
            f"watercolour style as the reference images. SCENE: {desc}. "
            f"ALL {len(dict.fromkeys(present))} of these characters MUST appear, "
            f"each drawn once as a distinct figure: {roster}. Do not omit or "
            f"merge any of them. "
            f"BACKGROUND: render the full setting from the setting reference "
            f"image — {set_desc[:280]}. Keep that room/scene fully painted "
            f"behind the characters (do NOT leave a blank or plain background). "
            f"COMPOSITION: the grey-capsule image is a LAYOUT GUIDE — each grey "
            f"capsule marks WHERE one character stands and how tall; paint "
            f"characters at those positions and do NOT keep any grey shapes. "
            f"Each character is a SINGLE upright bipedal body — two legs, two "
            f"arms, human-like torso with an animal head — NEVER a four-legged "
            f"body, NEVER an extra second body or extra legs. Keep the bottom "
            f"band clear of characters for the caption. Match each character to "
            f"its reference sheet.")
    else:
        instr = (
            f"Illustrate this children's book page in soft watercolour style. "
            f"SCENE: {desc}. This page has NO animal or human characters — only "
            f"the setting/decoration. Do NOT draw any animals or people. Keep "
            f"open space for text.")

    imgs = [buf.getvalue()] + setting_bytes + refs
    print(f"  page {pid}: blocking + {len(setting_bytes)} setting + {len(refs)} "
          f"char refs ({'set='+os.path.basename(set_path) if set_path else 'NO SETTING'})")
    return editor.to_square(editor.edit(instr, imgs))
