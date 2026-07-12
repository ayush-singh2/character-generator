"""TOON (Token-Oriented Object Notation) I/O for the rebuilt pipeline.

Client asked for TOON. TOON encodes uniform arrays as a compact tabular block
(header once, then rows), saving tokens vs JSON's repeated keys/braces. Its real
payoff is fewer INPUT tokens when data is injected into LLM prompts.

Design note: `python-toon` (v0.1.x) encodes reliably but its strict DECODER trips
on deeply-nested rich data (arrays of objects that themselves contain lists — e.g.
scene `chars:[...]`, group `members:[...]`). So we keep the CANONICAL on-disk form
as JSON (100% reliable round-trip) and use TOON purely for prompt injection via
`for_prompt()`, which is exactly where the token savings matter. A companion
`.toon` sidecar is written alongside for human inspection / the client's format.
"""

import json
import os

import toon  # python-toon: toon.encode(obj) / toon.decode(str)

# Tab delimiter for tabular arrays: the default comma delimiter breaks when field
# values contain commas (common in prose). Decode auto-detects the delimiter.
_ENC = toon.EncodeOptions(delimiter="\t")


def dumps(obj) -> str:
    """Encode a dict/list to a TOON string (tab-delimited)."""
    return toon.encode(obj, _ENC)


def loads(s: str):
    """Decode a TOON string to a Python object."""
    return toon.decode(s)


def save(obj, path: str) -> str:
    """Write `obj` as canonical JSON to `path`, plus a `.toon` sidecar.

    `path` keeps its (usually .toon) name for downstream compatibility but holds
    JSON so it always reloads. A parallel `<path>.view.toon` holds the TOON
    rendering for inspection.
    """
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    try:
        with open(path + ".view.toon", "w", encoding="utf-8") as f:
            f.write(dumps(obj))
    except Exception:
        pass  # sidecar is best-effort; canonical JSON is what load() reads
    return path


def load(path: str):
    """Read a data file (JSON canonical, TOON tolerated) into a Python object."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    try:
        return json.loads(text)
    except Exception:
        return loads(text)  # tolerate a hand-written TOON file


def for_prompt(obj) -> str:
    """TOON string for embedding in an LLM prompt (compact, token-lean)."""
    return dumps(obj)
