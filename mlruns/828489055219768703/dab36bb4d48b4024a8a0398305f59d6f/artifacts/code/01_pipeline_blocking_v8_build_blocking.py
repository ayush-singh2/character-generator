def build_blocking(layout_entry: dict, size: int = 1024, label: bool = False,
                   faint: bool = False) -> Image.Image:
    """Blocking canvas for one page's layout entry. `faint` uses near-paper
    greys instead of colours (avoids the img2img colour-halo artifact)."""
    img = Image.new("RGB", (size, size), PAPER)
    d = ImageDraw.Draw(img)

    tz = layout_entry.get("text_zone")
    if tz and len(tz) == 4:
        d.rectangle((int(tz[0] * size), int(tz[1] * size),
                     int(tz[2] * size), int(tz[3] * size)), fill=TEXT_BAND)

    for i, ch in enumerate(layout_entry.get("chars") or []):
        box = ch.get("box")
        if not (isinstance(box, list) and len(box) == 4):
            continue
        box = _min_size(box)          # tiny capsules get dropped by the model
        color = _faint(i) if faint else PALETTE[i % len(PALETTE)]
        _capsule(d, box, size, color)
        if label:
            d.text((int(box[0] * size) + 4, int(box[1] * size) + 4),
                   str(ch.get("name", "")), fill=(40, 40, 40))
    return img
