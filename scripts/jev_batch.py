"""Batch-call Jev (System One) over encoded windows with cache + resume.

Reads data/jev_windows.jsonl + scripts/jev_questions.json, POSTs each state
once to POST /v1/systemone, appends answers to data/jev_features.jsonl keyed
by state hash so re-runs are free.

Security: API key comes ONLY from env TYPESAFE_API_KEY, never committed.
Offline HTML must not call Jev directly; this script is the bridge.

Usage:
    set TYPESAFE_API_KEY=...   (PowerShell: $env:TYPESAFE_API_KEY="...")
    python jev_batch.py --limit 5              # smoke test (real API)
    python jev_batch.py --dry-run --limit 20   # offline mock, no network
    python jev_batch.py                        # full run (~1710 windows)
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

API_URL = "https://api.typesafe.ai/v1/systemone"


def load_dotenv():
    """Load TYPESAFE_API_KEY from .env (stdlib, no dependency).

    Env vars already set always win. Looks in CWD then in the project root
    next to scripts/ (simulator-clob-mm/.env).
    """
    candidates = [
        os.path.join(os.getcwd(), ".env"),
        os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), ".env"),
    ]
    for path in dict.fromkeys(candidates):
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip().strip("'\"")
                    if k and v and k not in os.environ:
                        os.environ[k] = v
        except OSError:
            continue


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Batch Jev calls with cache.")
    ap.add_argument("--windows", default=os.path.join("data", "jev_windows.jsonl"))
    ap.add_argument("--questions", default=os.path.join("scripts", "jev_questions.json"))
    ap.add_argument("--out", default=os.path.join("data", "jev_features.jsonl"))
    ap.add_argument("--model", default="jev-latest")
    ap.add_argument("--limit", type=int, default=0, help="0 = all")
    ap.add_argument("--dry-run", action="store_true", help="mock answers, no network")
    ap.add_argument("--sleep", type=float, default=0.2, help="pause between calls")
    ap.add_argument("--max-retries", type=int, default=5)
    return ap.parse_args(argv)


def load_jsonl(path):
    recs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def load_cache(path):
    done = {}
    if not os.path.exists(path):
        return done
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            done[r.get("hash")] = r
    return done


def mock_answers():
    # Uniform / neutral mock so the pipeline is testable without a key.
    return {
        "regime": {
            "type": "choice", "choice": "no_clear",
            "probabilities": {"stable": 0.2, "steam_sharp": 0.15,
                              "drift_public": 0.15, "reversal": 0.15,
                              "choppy": 0.15, "no_clear": 0.2},
            "confidence": 0.0,
        },
        "momentum": {
            "type": "score", "score": 1.0,
            "legend": {"0": "calm", "1": "moderate", "2": "strong"},
            "probabilities": {"0": 0.33, "1": 0.34, "2": 0.33},
            "confidence": 0.0,
        },
        "toxicity": {
            "type": "score", "score": 1.0,
            "legend": {"0": "benign", "1": "mixed", "2": "toxic"},
            "probabilities": {"0": 0.33, "1": 0.34, "2": 0.33},
            "confidence": 0.0,
        },
        "is_steam": {"type": "noul", "noul": 0.5},
        "is_public_fade": {"type": "noul", "noul": 0.5},
        "line_unstable": {"type": "noul", "noul": 0.5},
    }


def call_jev(state, questions, model, api_key, max_retries):
    body = json.dumps(
        {"state": state, "model": model, "questions": questions}
    ).encode("utf-8")
    last_err = None
    for attempt in range(max_retries + 1):
        req = urllib.request.Request(
            API_URL,
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}"
            if e.code in (429, 529) and attempt < max_retries:
                time.sleep((2 ** attempt) + 0.5)
                continue
            raise RuntimeError(last_err)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_err = f"network: {e}"
            if attempt < max_retries:
                time.sleep((2 ** attempt) + 0.5)
                continue
            raise RuntimeError(last_err)
    raise RuntimeError(last_err or "unknown Jev error")


def main(argv=None):
    args = parse_args(argv)
    load_dotenv()
    with open(args.questions, encoding="utf-8") as f:
        questions = json.load(f)
    windows = load_jsonl(args.windows)
    if args.limit > 0:
        windows = windows[:args.limit]
    cache = load_cache(args.out)

    api_key = os.environ.get("TYPESAFE_API_KEY", "")
    if not args.dry_run and not api_key:
        print("ERROR: TYPESAFE_API_KEY not set. Re-run with --dry-run for a "
              "mock test, or set the key first.", file=sys.stderr)
        return 2

    n_skip, n_new, n_fail = 0, 0, 0
    new_recs = []
    for i, w in enumerate(windows):
        h = w["hash"]
        cached = cache.get(h)
        if cached is not None:
            # Mock entries must never satisfy a real run and vice versa,
            # otherwise a --dry-run would pollute the real cache.
            cached_is_mock = cached.get("model") == "mock"
            if cached_is_mock == bool(args.dry_run):
                n_skip += 1
                continue
        if args.dry_run:
            resp = {"model": "mock", "answers": mock_answers(),
                    "usage": {"input_tokens": 0, "output_tokens": 0}}
        else:
            try:
                resp = call_jev(w["state"], questions, args.model,
                                api_key, args.max_retries)
            except Exception as e:
                n_fail += 1
                print(f"[{i}] {w['match_id']}@{w['idx_start']} FAIL {e}",
                      file=sys.stderr)
                continue
            if args.sleep > 0:
                time.sleep(args.sleep)
        rec = {
            "match_id": w["match_id"],
            "idx_start": w["idx_start"],
            "hash": h,
            "y": w["y"],
            "is_push": w.get("is_push", False),
            "p_close_match": w.get("p_close_match"),
            "p_last_window": w["state"]["window"]["p_last"],
            "model": resp.get("model", args.model),
            "answers": resp.get("answers", {}),
            "usage": resp.get("usage", {}),
        }
        new_recs.append(rec)
        cache[h] = rec
        n_new += 1
        if n_new % 25 == 0:
            print(f"... {n_new} new ({n_skip} cached, {n_fail} failed)")

    # Rewrite whole cache so a mock->real (or real->mock) switch overwrites
    # stale entries instead of duplicating hashes.
    if new_recs:
        with open(args.out, "w", encoding="utf-8") as out:
            for rec in cache.values():
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"done: windows={len(windows)} new={n_new} cached={n_skip} "
          f"failed={n_fail} -> {args.out}")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
