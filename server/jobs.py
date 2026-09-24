"""Background pipeline-job runner.

Each pipeline stage-group runs as a SUBPROCESS of run_v3 (cwd=book dir),
because the stages chdir + bind cwd-relative paths. We stream its
stdout, watch for `== <stage> ==` banners to compute progress, and persist a
small status doc to books/<slug>/v3/job.json that the frontend polls.

Two groups matter for the author-control flow:
  - "parse"    : parse -> copyedit -> refs   (STOP; author approves characters)
  - "generate" : layout -> generate (v7 gate+repair) -> compose -> book
"""

import glob
import json
import os
import subprocess
import sys
import threading
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Generated books live under STATE_DIR (persistent disk in prod; repo locally).
STATE_DIR = os.environ.get("BB_STATE_DIR", REPO)
BOOKS = os.path.join(STATE_DIR, "books")
PY = sys.executable  # the .venv python running the server

# Full stage order, for progress math.
ORDER = ["parse", "copyedit", "refs", "layout", "generate", "compose", "book"]

# Named groups expand to one or more run_v3 segments (from_stage, to_stage). The
# "parse" group is split so the author's chosen style can be written into
# characters.toon AFTER parse but BEFORE refs (refs consumes the style).
GROUPS = {
    "parse": [("parse", "copyedit"), ("refs", "refs")],   # style override injected between
    "generate": [("layout", "book")],
    # After the author picks a style from the previews: the override is applied
    # in-process by the endpoint, then this re-renders the reference sheets in
    # the new style (refs consume characters.toon's style).
    "restyle": [("refs", "refs")],
}

_locks = {}          # slug -> threading.Lock (guards one job per slug)
_locks_guard = threading.Lock()


def _lock_for(slug):
    with _locks_guard:
        lk = _locks.get(slug)
        if lk is None:
            lk = _locks[slug] = threading.Lock()
        return lk


def _job_path(slug):
    return os.path.join(BOOKS, slug, "v3", "job.json")


def _write(slug, doc):
    p = _job_path(slug)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump(doc, f)
    os.replace(tmp, p)


def read_status(slug):
    p = _job_path(slug)
    if not os.path.exists(p):
        return {"state": "idle", "group": None, "stage": None, "pct": 0, "log": []}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {"state": "unknown", "pct": 0, "log": []}


def is_running(slug):
    return read_status(slug).get("state") == "running"


def recover_stale_jobs():
    """Called once at server startup. A job.json still marked "running" cannot be
    real — its worker thread lived in the previous process and died when the server
    restarted (deploy, crash, instance recycle). Flip those zombies to "error" so
    the UI shows an interrupted state + retry path instead of a frozen "running"
    that never resolves."""
    for jp in glob.glob(os.path.join(BOOKS, "*", "v3", "job.json")):
        try:
            with open(jp) as f:
                doc = json.load(f)
            if doc.get("state") == "running":
                doc["state"] = "error"
                doc["error"] = ("interrupted — the server restarted while this "
                                "was running. Please run it again.")
                doc["updated"] = int(time.time())
                tmp = jp + ".tmp"
                with open(tmp, "w") as f:
                    json.dump(doc, f)
                os.replace(tmp, jp)
        except Exception:
            pass


def _run_segment(slug, frm, to, only, env, doc, span):
    """Run one run_v3 subprocess segment, streaming progress into `doc`.
    Returns the process return code."""
    cmd = [PY, "-m", "pipeline.run_v3",
           "--book", os.path.join(BOOKS, slug),
           "--from", frm, "--to", to]
    if only:
        cmd += ["--only", only]
    proc = subprocess.Popen(cmd, cwd=REPO, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, bufsize=1)
    for line in proc.stdout:
        line = line.rstrip("\n")
        if not line:
            continue
        doc["log"] = (doc["log"] + [line])[-40:]
        # progress on stage banners: "== generate (text-to-image) =="
        if line.lstrip().startswith("== "):
            name = line.strip().strip("= ").split()[0]
            if name in span:
                doc["stage"] = name
                doc["pct"] = int(5 + 90 * (span.index(name) / max(1, len(span))))
        doc["updated"] = int(time.time())
        _write(slug, doc)
    return proc.wait()


def _run(slug, group, only, env, style):
    segments = GROUPS[group]
    first, last = segments[0][0], segments[-1][1]
    span = ORDER[ORDER.index(first):ORDER.index(last) + 1]
    doc = {"state": "running", "group": group, "stage": first, "pct": 1,
           "log": [], "started": int(time.time()), "updated": int(time.time())}
    _write(slug, doc)

    try:
        for i, (frm, to) in enumerate(segments):
            rc = _run_segment(slug, frm, to, only, env, doc, span)
            if rc != 0:
                doc["state"] = "error"
                doc["error"] = f"pipeline stage {frm}..{to} exited {rc}"
                break
            # Style override slots between parse/copyedit and refs.
            if group == "parse" and i == 0 and style:
                try:
                    from server import pipeline_api
                    pipeline_api.apply_style_override(slug, **style)
                    doc["log"] = (doc["log"] + ["== style override applied =="])[-40:]
                    _write(slug, doc)
                except Exception as e:  # noqa: BLE001
                    doc["log"] = (doc["log"] + [f"style override skipped: {e}"])[-40:]
        else:
            doc["state"], doc["pct"], doc["stage"] = "done", 100, last
    except Exception as e:  # noqa: BLE001 — surfaced to the client
        doc["state"] = "error"
        doc["error"] = str(e)[:300]
    doc["updated"] = int(time.time())
    _write(slug, doc)


def start(slug, group, only=None, style=None, env_extra=None):
    """Kick a job group in a background thread. Returns immediately.
    `style` (dict for apply_style_override) is applied between parse and refs.
    `env_extra` merges into the subprocess env (e.g. STORYBOOK_DOCX).
    Rejects if a job is already running for this slug."""
    if group not in GROUPS:
        raise ValueError(f"unknown job group {group}")
    lk = _lock_for(slug)
    if not lk.acquire(blocking=False):
        return {"ok": False, "reason": "a job is already running"}

    env = dict(os.environ)
    env.setdefault("V3_DIR", "v3")
    env["PYTHONPATH"] = REPO + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONUNBUFFERED"] = "1"
    if env_extra:
        env.update({k: str(v) for k, v in env_extra.items()})

    def worker():
        try:
            _run(slug, group, only, env, style)
        finally:
            lk.release()

    threading.Thread(target=worker, daemon=True).start()
    return {"ok": True, "group": group}
