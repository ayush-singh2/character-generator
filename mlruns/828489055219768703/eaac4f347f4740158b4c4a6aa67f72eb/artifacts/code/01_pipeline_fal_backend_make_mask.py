def make_mask(size, box, *, feather: int = 8) -> bytes:
    """White-in-box, black-out mask PNG bytes for a normalised box on a WxH
    image. Feathered so the inpaint seam blends."""
    W, H = size
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).rectangle(
        (int(box[0] * W), int(box[1] * H), int(box[2] * W), int(box[3] * H)),
        fill=255)
    if feather:
        m = m.filter(ImageFilter.GaussianBlur(feather))
    buf = io.BytesIO(); m.convert("RGB").save(buf, "PNG")
    return buf.getvalue()
