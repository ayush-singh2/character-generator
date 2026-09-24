"""Local, zero-cost pre-gate for the v8 coat-colour audit.

WHY THIS EXISTS
---------------
The v8 identity audit is the pipeline's biggest running cost after image
generation: every character on every page triggers several Sonnet vision
calls (zoom-locate, multi-vote identity audit, and — the part this module
targets — a two-call FORCED-CHOICE coat-colour check: name the coat colour
of the page crop, name the coat colour of the reference sheet, compare the
families in code). That coat check is exactly the axis a cheap LOCAL colour
classifier is good at: coat-colour drift (the p17 fawn-brown-vs-cream miss)
is a dominant-colour question, not a semantic one.

This module classifies the dominant coat colour of an image into the SAME
family vocabulary the VLM uses, purely from pixels (PIL + numpy, no model
download, no API call). The audit can then:

  - skip the two VLM coat calls when the local check is a CONFIDENT same-
    family match (pure saving — the common case), and
  - fall back to the authoritative VLM forced-choice whenever the local
    check sees drift or is unsure.

It is deliberately conservative: the local gate can only ever REMOVE VLM
calls on confident matches; any doubt escalates. It never fails a character
on its own (a false local "drift" just means we spend the VLM call we would
have spent anyway). SigLIP/CLIP embeddings would be a stronger drop-in for
`coat_signature` later; this PIL version is the immediately-runnable start.
"""

import io
import os

import numpy as np
from PIL import Image

# Coat families — mirror audit_v8._COATS / its `fam` map so the local verdict
# is directly comparable to the VLM's forced-choice output.
#   0 white/cream   1 tan/golden/light-brown   2 dark-brown
#   3 grey          4 black                     5 pink
FAMILIES = ("white_cream", "tan_golden", "dark_brown", "grey", "black", "pink", "other")

# Tunables (env-overridable) — defaults chosen conservative: only skip the VLM
# when the match is unambiguous.
CONF_FRACTION = float(os.getenv("PREGATE_CONF_FRACTION", "0.45"))   # dominant family must hold ≥ this share
MATCH_INTERSECT = float(os.getenv("PREGATE_MATCH_INTERSECT", "0.55"))  # histogram overlap for a "match"
DRIFT_FRACTION = float(os.getenv("PREGATE_DRIFT_FRACTION", "0.40"))    # both dominants this strong + differ ⇒ drift


def _to_hsv_array(img_bytes: bytes, size: int = 72) -> np.ndarray:
    """Load, centre-crop to the body region, downscale, return H,S,V in 0..1
    as an (N,3) float array. Centre crop drops most background/frame."""
    im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    W, H = im.size
    # central 70% — the character usually dominates the middle of a zoom crop
    dx, dy = int(W * 0.15), int(H * 0.15)
    im = im.crop((dx, dy, W - dx, H - dy)).resize((size, size), Image.BILINEAR)
    hsv = np.asarray(im.convert("HSV"), dtype=np.float32) / 255.0
    return hsv.reshape(-1, 3)


def _classify(hsv: np.ndarray) -> np.ndarray:
    """Map each pixel to a FAMILIES index. Vectorised HSV thresholds.

    The tricky, high-value distinction is white/cream vs tan (the recurring
    drift): low-saturation bright pixels are white/cream (family 0); the same
    hue at higher saturation / lower value is tan→brown (families 1/2)."""
    h, s, v = hsv[:, 0], hsv[:, 1], hsv[:, 2]
    hue = h * 360.0
    out = np.full(h.shape, FAMILIES.index("other"), dtype=np.int8)

    black = v < 0.16
    low_sat = s < 0.22
    warm = (hue >= 25) & (hue <= 55)          # yellow-orange (cream/tan/gold)
    # pink/pig skin is RED-hued (near 0/360), often only lightly saturated —
    # the old band (300..12, s≥0.20) missed pale pigs, which then fell through
    # to white_cream. Widen the red hue window and lower the saturation floor,
    # and (below) let pink reclaim pale-red pixels from white_cream.
    reddish = (hue >= 330) | (hue <= 22)

    white_cream = low_sat & (v >= 0.72) & ~black
    grey = low_sat & (v >= 0.28) & (v < 0.72) & ~black
    pink = reddish & (s >= 0.12) & (v >= 0.5)
    tan_golden = warm & (s >= 0.22) & (v >= 0.42)
    dark_brown = ((warm | reddish)) & (v < 0.42) & (s >= 0.18)

    # order matters: later assignments override earlier ones. pink is placed
    # AFTER white_cream so a pale, red-hued pig is pink, not "cream"; black
    # wins last (lineart/shadow over everything).
    out[grey] = FAMILIES.index("grey")
    out[tan_golden] = FAMILIES.index("tan_golden")
    out[dark_brown] = FAMILIES.index("dark_brown")
    out[white_cream] = FAMILIES.index("white_cream")
    out[pink] = FAMILIES.index("pink")
    out[black] = FAMILIES.index("black")
    return out


def coat_signature(img_bytes: bytes) -> np.ndarray:
    """Return a normalised family histogram (len(FAMILIES),).

    Black and 'other' are excluded from the normalisation base: black is
    usually lineart/shadow and 'other' is unclassifiable clutter, so the
    signature reflects the *coat* families that actually carry meaning."""
    try:
        fam = _classify(_to_hsv_array(img_bytes))
    except Exception:                                    # noqa: BLE001
        return np.zeros(len(FAMILIES), dtype=np.float32)
    hist = np.bincount(fam, minlength=len(FAMILIES)).astype(np.float32)
    coat = hist.copy()
    coat[FAMILIES.index("black")] = 0.0
    coat[FAMILIES.index("other")] = 0.0
    total = coat.sum()
    return coat / total if total > 0 else coat


def _dominant(sig: np.ndarray):
    """(family_name, fraction) of the strongest coat family, or (None, 0)."""
    if sig.sum() <= 0:
        return None, 0.0
    i = int(np.argmax(sig))
    return FAMILIES[i], float(sig[i])


def coat_match(crop_bytes: bytes, sheet_bytes: bytes) -> dict:
    """Compare a page crop of a character to its reference sheet.

    Returns a dict:
      decision: "match" | "drift" | "ambiguous"
        match    — confident same coat family  ⇒ audit may SKIP the VLM calls
        drift    — confident different family   ⇒ escalate (likely real drift)
        ambiguous— not confident either way     ⇒ escalate (let the VLM decide)
      intersect: histogram-overlap score 0..1
      crop_family / sheet_family, crop_frac / sheet_frac: the dominants
    """
    cs, ss = coat_signature(crop_bytes), coat_signature(sheet_bytes)
    intersect = float(np.minimum(cs, ss).sum())
    cf, cfr = _dominant(cs)
    sf, sfr = _dominant(ss)

    decision = "ambiguous"
    if cf is None or sf is None:
        decision = "ambiguous"                            # no coat signal → don't trust
    elif cf == sf and cfr >= CONF_FRACTION and intersect >= MATCH_INTERSECT:
        decision = "match"
    elif cf != sf and cfr >= DRIFT_FRACTION and sfr >= DRIFT_FRACTION:
        decision = "drift"
    return {"decision": decision, "intersect": round(intersect, 3),
            "crop_family": cf, "crop_frac": round(cfr, 3),
            "sheet_family": sf, "sheet_frac": round(sfr, 3)}


def mode() -> str:
    """AUDIT_PREGATE: 'off' | 'shadow' (default) | 'on'.
    off    — module unused, original behaviour.
    shadow — compute + log the local verdict but keep the VLM authoritative
             (zero behaviour change; use this to measure agreement first).
    on     — skip the VLM coat calls on a confident local 'match'.
    """
    return os.getenv("AUDIT_PREGATE", "shadow").strip().lower()
