"""Locked character spec → identical, exact prompt text on every page.

Characters drift between pages (Ella's t-shirt logo, shoe colour, hair shade
change) because the description is vague ("favourite colour", "mid-size") and
the image model re-invents the blanks each time. The cure is a CANONICAL SPEC:
a nested JSON with exact, enumerated values (hex codes, coordinates, garment
names) and a DETERMINISTIC serialiser that renders it to the same text every
time. That exact block is pasted verbatim into the reference sheet AND every
page prompt, so Flux is never left to guess.

Schema (per character, stored on the bible entry as `locked_spec`):

  {
    "identity": {
      "species": "human",
      "age_years": 9,
      "gender_presentation": "girl",
      "skin":  {"hex": "#E8B48C", "undertone": "warm",
                 "notes": "smooth, no wrinkles, freckles across nose bridge"},
      "build": {"height_cm": 135, "body_type": "slender"}
    },
    "hair": {"color_hex": "#3B2A1A", "length": "shoulder-length",
              "style": "two low pigtails", "texture": "wavy",
              "accessory": {"item": "hair ties", "color_hex": "#FF4D4D"}},
    "face": {"eye_color_hex": "#5B3A1E", "eye_shape": "round",
              "eyebrows": "thin arched", "nose": "small button",
              "wrinkles": "none",
              "distinguishing": ["dimple on left cheek"]},
    "outfit": {
      "top":    {"garment": "short-sleeve t-shirt", "color_hex": "#FFD23F",
                  "fit": "relaxed",
                  "logo": {"present": true, "motif": "white five-point star",
                            "position": "centre chest", "coords_pct": [50, 40],
                            "size_pct": 18, "color_hex": "#FFFFFF"}},
      "bottom": {"garment": "denim jogger pants", "color_hex": "#3E5C76",
                  "fit": "elastic waist"},
      "footwear": {"garment": "slip-on sneakers", "color_hex": "#FFFFFF",
                    "sole_hex": "#D9D9D9", "fastening": "velcro strap",
                    "logo": "none"},
      "outerwear": "none"
    },
    "accessories": [{"item": "bicycle helmet", "color_hex": "#4A90E2",
                      "when": "only when riding"}]
  }

For animals the same shape is reused: `hair` = coat colour/markings, `outfit`
= collar/bandana (or "none"), `face` = muzzle/ears; skip human-only garments.

Rule the bible must follow: NEVER an approximate value ("blue-ish", "mid-size",
"a hat"). Always commit to one exact value; if the text is silent, invent one
and LOCK it. Consistency beats accuracy here — the same wrong-but-fixed shade
every page reads as one character; a different right-ish shade each page does not.
"""


def _hexc(v) -> str:
    """Normalise a colour value to '#RRGGBB' text if it looks like hex."""
    if not v:
        return ""
    s = str(v).strip()
    return s if s.startswith("#") else s


def _seg(label: str, value) -> str | None:
    return f"{label} {value}" if value not in (None, "", [], {}) else None


def _skin(idn: dict) -> str | None:
    sk = idn.get("skin") or {}
    if not sk:
        return None
    bits = []
    if sk.get("hex"):
        bits.append(f"skin exactly {_hexc(sk['hex'])}")
    if sk.get("undertone"):
        bits.append(f"{sk['undertone']} undertone")
    if sk.get("notes"):
        bits.append(sk["notes"])
    return ", ".join(bits) if bits else None


def _hair(spec: dict) -> str | None:
    h = spec.get("hair") or {}
    if not h:
        return None
    bits = ["hair"]
    if h.get("color_hex"):
        bits.append(f"exactly {_hexc(h['color_hex'])}")
    for k in ("length", "texture", "style"):
        if h.get(k):
            bits.append(h[k])
    acc = h.get("accessory") or {}
    if acc.get("item"):
        c = f" ({_hexc(acc['color_hex'])})" if acc.get("color_hex") else ""
        bits.append(f"held with {acc['item']}{c}")
    return " ".join([bits[0]] + [", ".join(bits[1:])]) if len(bits) > 1 else None


def _face(spec: dict) -> str | None:
    f = spec.get("face") or {}
    if not f:
        return None
    bits = []
    if f.get("eye_color_hex") or f.get("eye_shape"):
        bits.append("eyes " + " ".join(
            x for x in (_hexc(f.get("eye_color_hex", "")), f.get("eye_shape", "")) if x))
    for k in ("eyebrows", "nose"):
        if f.get(k):
            bits.append(f"{k.replace('_', ' ')} {f[k]}")
    if f.get("wrinkles") is not None:
        bits.append(f"wrinkles: {f['wrinkles']}")
    for d in (f.get("distinguishing") or []):
        bits.append(d)
    return "; ".join(bits) if bits else None


def _logo(logo: dict) -> str:
    if not logo or logo in ("none", "None") or logo.get("present") is False:
        return ("a completely PLAIN blank chest — absolutely NO logo, NO print, "
                "NO graphic, NO text, NO emblem of any kind on it")
    motif = logo.get("motif", "logo")
    pos = logo.get("position", "")
    coords = logo.get("coords_pct")
    size = logo.get("size_pct")
    col = _hexc(logo.get("color_hex", ""))
    out = f"with a {motif}"
    if col:
        out += f" in {col}"
    if pos:
        out += f" at the {pos}"
    if coords and len(coords) == 2:
        out += f" (positioned at {coords[0]}%,{coords[1]}% of the garment)"
    if size:
        out += f", sized ~{size}% of the garment"
    return out


def _garment(g: dict, kind: str) -> str | None:
    if not g or g in ("none", "None"):
        return None
    bits = []
    name = g.get("garment", kind)
    col = _hexc(g.get("color_hex", ""))
    bits.append(f"{name}" + (f" in exactly {col}" if col else ""))
    if g.get("fit"):
        bits.append(g["fit"] + " fit")
    if g.get("fastening"):
        bits.append(g["fastening"])
    if g.get("sole_hex"):
        bits.append(f"soles {_hexc(g['sole_hex'])}")
    if "logo" in g:
        bits.append(_logo(g.get("logo")))
    return ", ".join(bits)


def _outfit(spec: dict) -> list[str]:
    o = spec.get("outfit") or {}
    out = []
    for kind in ("top", "bottom", "footwear", "outerwear"):
        seg = _garment(o.get(kind), kind) if isinstance(o.get(kind), dict) else None
        if seg:
            out.append(seg)
    return out


def _accessories(spec: dict) -> str | None:
    accs = spec.get("accessories") or []
    parts = []
    for a in accs:
        if not isinstance(a, dict):
            continue
        c = f" ({_hexc(a['color_hex'])})" if a.get("color_hex") else ""
        when = f" [{a['when']}]" if a.get("when") else ""
        parts.append(f"{a.get('item', 'accessory')}{c}{when}")
    return "; ".join(parts) if parts else None


def serialize(spec: dict, name: str = "") -> str:
    """Render a locked_spec to a dense, EXACT, deterministic prompt block.

    Same spec in → same text out, so every page pins the identical appearance.
    """
    if not spec:
        return ""
    idn = spec.get("identity") or {}
    head = []
    if idn.get("age_years") is not None:
        head.append(f"{idn['age_years']}-year-old")
    if idn.get("gender_presentation"):
        head.append(idn["gender_presentation"])
    if idn.get("species") and idn["species"] != "human":
        head.append(idn["species"])
    build = idn.get("build") or {}
    if build.get("body_type"):
        head.append(build["body_type"] + " build")
    if build.get("height_cm"):
        head.append(f"{build['height_cm']}cm tall")

    lines = []
    if head:
        lines.append(", ".join(head))
    for seg in (_skin(idn), _hair(spec), _face(spec)):
        if seg:
            lines.append(seg)
    outfit = _outfit(spec)
    if outfit:
        lines.append("wearing " + "; ".join(outfit))
    acc = _accessories(spec)
    if acc:
        lines.append("accessories: " + acc)

    body = ". ".join(lines)
    who = f" for {name}" if name else ""
    return (f"CHARACTER DESIGN{who} (keep these exact details consistent — same "
            f"colours, logo and features on every page): {body}.")


def has_spec(char: dict) -> bool:
    return bool(char.get("locked_spec"))
