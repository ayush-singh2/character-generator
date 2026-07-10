"""TOON (Token-Oriented Object Notation) I/O for the rebuilt pipeline.

Client asked for TOON instead of JSON. TOON encodes uniform arrays as a compact
tabular block (header once, then rows), saving tokens vs JSON's repeated keys and
braces — useful both for stored data files (.toon) and for serialising data into
LLM prompts.

Uses the `python-toon` package (imports as `toon`). JSON stays available for the
LLM boundary where a model is more reliable at emitting JSON.
"""

import json
import os

import toon  # python-toon: toon.encode(obj) / toon.decode(str)


def dumps(obj) -> str:
    """Encode a dict/list to a TOON string."""
    return toon.encode(obj)


def loads(s: str):
    """Decode a TOON string to a Python object."""
    return toon.decode(s)


def save(obj, path: str) -> str:
    """Write `obj` as TOON to `path` (creates parent dirs)."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(dumps(obj))
    return path


def load(path: str):
    """Read a TOON (or, as a fallback, JSON) file into a Python object."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    try:
        return loads(text)
    except Exception:
        return json.loads(text)  # tolerate legacy .json data


def for_prompt(obj) -> str:
    """TOON string suitable for embedding in an LLM prompt (compact, token-lean)."""
    return dumps(obj)
