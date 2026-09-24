"""A/B model harness for the TEXT stages.

Purpose: before swapping the text model (e.g. Sonnet -> Kimi K2.6) to cut
cost, prove the candidate actually returns clean, correctly-structured JSON
for our REAL pipeline prompts — not a toy prompt. For each (stage, model)
it records latency, prompt/completion tokens, OpenRouter's reported cost,
whether the reply parsed as JSON via the pipeline's own `_parse_json`, and
the top-level shape. It then diffs the shapes between models so silent
schema drift is visible.

This deliberately bypasses TEXT_MODEL/VISION_MODEL from .env and calls each
model explicitly, so it is safe to run even while .env points at Kimi.

Usage:
    python -m pipeline.ab_models                 # light stages, default book
    python -m pipeline.ab_models --parse         # also run the heavy
                                                 # manuscript-mining call
    python -m pipeline.ab_models --book books/namaste-ferdinand/v3
    python -m pipeline.ab_models --models anthropic/claude-sonnet-4.5 moonshotai/kimi-k2.6
"""

import argparse
import base64
import glob
import json
import os
import time

import requests

from . import gate_v7, layout_v3, llm, parse_v3, plan_v3, style_guide, copyedit_v3

API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODELS = ["anthropic/claude-sonnet-4.5", "moonshotai/kimi-k2.6"]


def _key() -> str:
    k = os.getenv("OPENROUTER_API_KEY")
    if not k:
        # .env is not auto-loaded here; read it directly so the harness is
        # runnable standalone.
        for line in open(os.path.join(os.getcwd(), ".env")):
            if line.startswith("OPENROUTER_API_KEY="):
                k = line.split("=", 1)[1].strip()
                break
    if not k:
        raise SystemExit("OPENROUTER_API_KEY not set (env or .env)")
    return k


def _call(model: str, system: str, user: str, max_tokens: int, temperature: float,
          *, tame_reasoning: bool = True):
    """One raw OpenRouter call. Returns a dict of measurements + the raw reply.

    Never raises on model/HTTP error — records the failure so the report is
    complete across models.

    `tame_reasoning`: reasoning models (Kimi K2.6) otherwise burn the whole
    completion budget in a `reasoning` field and leave `content` empty, so
    `_parse_json` gets nothing. `reasoning.enabled=false` disables it, and
    `provider.require_parameters=true` forces OpenRouter to route ONLY to
    providers that actually honour that flag (some silently ignore it and
    dump reasoning anyway). This is the config a real swap must use.
    """
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "usage": {"include": True},   # ask OpenRouter to report cost
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if tame_reasoning:
        body["reasoning"] = {"enabled": False}
        body["provider"] = {"require_parameters": True}
    t0 = time.time()
    try:
        r = requests.post(API_URL, headers={"Authorization": f"Bearer {_key()}"},
                          json=body, timeout=300)
    except Exception as e:                                    # noqa: BLE001
        return {"ok": False, "error": f"HTTP: {str(e)[:200]}", "latency": time.time() - t0}
    dt = time.time() - t0
    if r.status_code != 200:
        return {"ok": False, "error": f"{r.status_code}: {r.text[:200]}", "latency": dt}

    j = r.json()
    choice = (j.get("choices") or [{}])[0]
    msg = choice.get("message", {}) or {}
    content = msg.get("content")
    reasoning = msg.get("reasoning")
    usage = j.get("usage", {}) or {}

    out = {
        "ok": True,
        "latency": dt,
        "finish": choice.get("finish_reason"),
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "cost": usage.get("cost"),
        "provider": j.get("provider"),
        "empty_content": not content,
        # If the model dumped everything into a reasoning field and left
        # content empty (Kimi did this), _parse_json downstream would fail.
        "reasoning_only": bool(reasoning) and not content,
    }
    # Now the decisive check: does the pipeline's own parser accept it?
    try:
        parsed = llm._parse_json(content or "")
        out["json_ok"] = True
        out["shape"] = _shape(parsed)
    except Exception as e:                                    # noqa: BLE001
        out["json_ok"] = False
        out["shape"] = None
        out["parse_error"] = str(e)[:160]
        out["preview"] = (content or reasoning or "")[:200]
    return out


def _shape(obj, depth=0):
    """A compact, comparable description of JSON structure (keys + types),
    ignoring scalar values so two runs are comparable."""
    if isinstance(obj, dict):
        return {k: _shape(v, depth + 1) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [f"list[{len(obj)}]"] + ([_shape(obj[0], depth + 1)] if obj else [])
    return type(obj).__name__


# ---- cases: build real (system, user) pairs from an existing book --------

def _cases(book_dir: str, include_parse: bool):
    data_dir = os.path.join(book_dir, "data")
    plan = plan_v3.load(data_dir)
    scenes = plan.get("scenes", [])
    cases = []

    # 1) layout — structured coordinate JSON, the strictest shape test
    sc = next((s for s in scenes if plan_v3.scene_desc(s)), scenes[0] if scenes else None)
    if sc:
        pg = plan_v3.page_id(sc)
        user = (f"SCENE (page {pg}, layout={sc.get('layout','single')}):\n"
                f"{plan_v3.scene_desc(sc)}\n\n"
                f"Characters present: {', '.join(sc.get('chars', [])) or '(none named)'}\n"
                f"Preferred text side: {sc.get('text_area','top')}. "
                f"Reserve a calm area for: {plan_v3.scene_text(sc)[:120]}")
        cases.append(("layout", layout_v3.SYSTEM, user, 1500, 0.4))

    # 2) gate/contract — fact extraction from page text
    sc2 = next((s for s in scenes if plan_v3.scene_text(s)), sc)
    if sc2:
        user = (f"PAGE TEXT:\n{plan_v3.scene_text(sc2)}\n\n"
                f"SCENE:\n{plan_v3.scene_desc(sc2)}")
        cases.append(("gate_contract", gate_v7._CONTRACT_SYSTEM, user, 800, 0.4))

    # 3) copyedit — prose correction (returns JSON diff)
    sc3 = next((s for s in scenes if plan_v3.scene_text(s)), None)
    if sc3:
        cases.append(("copyedit", style_guide.with_guide(copyedit_v3._SYSTEM),
                      plan_v3.scene_text(sc3), 2000, 0.0))

    # 4) parse — the heavy manuscript-mining call (opt-in; big + slow)
    if include_parse:
        docx = _find_manuscript(book_dir)
        if docx:
            text = parse_v3._read_docx(docx)
            cases.append(("parse", parse_v3.SYSTEM, text, 32000, 0.4))
        else:
            print("  (no manuscript .docx found; skipping parse case)")
    return cases


def _find_manuscript(book_dir: str):
    for pat in ("manuscript/*.docx", "*.docx", "../manuscript/*.docx",
                "../*.docx", "../../*.docx"):
        hits = glob.glob(os.path.join(book_dir, pat))
        if hits:
            return hits[0]
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", default="books/namaste-ferdinand/v3")
    ap.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    ap.add_argument("--parse", action="store_true", help="also run the heavy manuscript-mining call")
    ap.add_argument("--raw-reasoning", action="store_true",
                    help="do NOT tame reasoning models (shows the naive-swap failure mode)")
    args = ap.parse_args()
    tame = not args.raw_reasoning

    cases = _cases(args.book, args.parse)
    print(f"book={args.book}  models={args.models}  cases={[c[0] for c in cases]}\n")

    results = {}   # (stage, model) -> measurement
    for stage, system, user, mt, temp in cases:
        print(f"=== stage: {stage}  (user≈{len(user)} chars, max_tokens={mt}) ===")
        for model in args.models:
            m = _call(model, system, user, mt, temp, tame_reasoning=tame)
            results[(stage, model)] = m
            if not m["ok"]:
                print(f"  {model:38s} ERROR {m['error']}")
                continue
            cost = f"${m['cost']:.4f}" if m.get("cost") is not None else "n/a"
            flags = []
            if m.get("reasoning_only"):
                flags.append("REASONING-ONLY(empty content!)")
            if m.get("finish") == "length":
                flags.append("truncated")
            if not m["json_ok"]:
                flags.append(f"JSON-FAIL: {m.get('parse_error')}")
            print(f"  {model:38s} {m['latency']:5.1f}s  "
                  f"tok {str(m.get('prompt_tokens')):>6}/{str(m.get('completion_tokens')):<5} "
                  f"{cost:>8}  json={'OK' if m['json_ok'] else 'NO':<3} "
                  f"[{m.get('provider')}]  {'  '.join(flags)}")
        # shape diff between the first two models for this stage
        if len(args.models) >= 2:
            a, b = args.models[0], args.models[1]
            sa, sb = results.get((stage, a), {}).get("shape"), results.get((stage, b), {}).get("shape")
            if sa is not None and sb is not None:
                same = sa == sb
                print(f"  shape match ({a.split('/')[-1]} vs {b.split('/')[-1]}): "
                      f"{'IDENTICAL' if same else 'DIFFERENT'}")
                if not same:
                    print(f"    A keys: {list(sa) if isinstance(sa, dict) else sa}")
                    print(f"    B keys: {list(sb) if isinstance(sb, dict) else sb}")
        print()

    # summary cost table
    print("=== COST / RELIABILITY SUMMARY ===")
    for model in args.models:
        rows = [results[(s[0], model)] for s in cases if (s[0], model) in results]
        oks = [r for r in rows if r.get("ok")]
        total_cost = sum(r["cost"] for r in oks if r.get("cost")) if oks else 0.0
        json_ok = sum(1 for r in oks if r.get("json_ok"))
        print(f"  {model:38s} json_ok {json_ok}/{len(rows)}  "
              f"total_cost ${total_cost:.4f}  "
              f"avg_latency {sum(r['latency'] for r in rows)/max(len(rows),1):.1f}s")


if __name__ == "__main__":
    main()
