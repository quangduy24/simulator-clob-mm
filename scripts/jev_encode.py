"""Encode odds-tick windows into Jev-ready states (offline, stdlib only).

Input:  data/timelines_all.json — 90 matches x 120 ticks, each tick
        {t, H, hh, ha, p, s}  (p = de-vigged HOME-cover prob, s = sharp flag)
Output: data/jev_windows.jsonl — one JSON per sliding window with:
        {match_id, league, ft, ht, settle, y, idx_start, idx_end,
         hash, state, meta}

State follows TypeSafe guidance: named JSON fields, code pre-computes all
numbers (gap/slope/vol/events), Jev only judges. Instructions live in
jev_questions.json and reference these fields with backticked paths.

Usage:
    python jev_encode.py --input ..\\data\\timelines_all.json \
        --output ..\\data\\jev_windows.jsonl --window 12 --step 6
"""

import argparse
import hashlib
import json
import math
import os
import sys


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Encode Jev windows from timelines.")
    ap.add_argument("--input", default=os.path.join("data", "timelines_all.json"))
    ap.add_argument("--output", default=os.path.join("data", "jev_windows.jsonl"))
    ap.add_argument("--window", type=int, default=12)
    ap.add_argument("--step", type=int, default=6)
    return ap.parse_args(argv)


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def std(xs):
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / len(xs))


def slope(xs):
    # Simple OLS slope over evenly spaced ticks.
    n = len(xs)
    if n < 2:
        return 0.0
    xbar = (n - 1) / 2.0
    ybar = mean(xs)
    den = sum((i - xbar) ** 2 for i in range(n))
    if den == 0:
        return 0.0
    return sum((i - xbar) * (y - ybar) for i, y in enumerate(xs)) / den


def median(xs):
    if not xs:
        return 0.0
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2.0


def settle_to_label(settle):
    # settle m in {+1,+0.5,0,-0.5,-1}; y=1 means HOME-cover wins (m>0).
    # Push (m==0) is rare; map to 0 and flag it so eval can exclude if wanted.
    try:
        m = float(settle)
    except (TypeError, ValueError):
        return 0, True
    if m == 0:
        return 0, True
    return (1 if m > 0 else 0), False


def sha1_state(state):
    blob = json.dumps(state, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha1(blob).hexdigest()[:16]


def encode_window(match, ticks, start, window):
    seg = ticks[start:start + window]
    ps = [t["p"] for t in seg]
    hs = [t["H"] for t in seg]
    sharp_ps = [t["p"] for t in seg if t.get("s") == 1]
    public_ps = [t["p"] for t in seg if t.get("s") != 1]

    p_first, p_last = ps[0], ps[-1]
    dp = p_last - p_first
    sharp_med = median(sharp_ps) if sharp_ps else median(ps)
    public_last = public_ps[-1] if public_ps else ps[-1]
    gap = sharp_med - public_last

    distinct_h = sorted(set(hs))
    n_line_changes = sum(1 for i in range(1, len(hs)) if hs[i] != hs[i - 1])

    events = []
    if n_line_changes:
        events.append(f"H changed {n_line_changes}x within window ({hs[0]}->{hs[-1]})")
    # Steam heuristic for the event log only (Jev makes the real judgment).
    max_jump = max((ps[i + 1] - ps[i] for i in range(len(ps) - 1)), default=0.0, key=abs)
    if abs(max_jump) >= 0.02:
        events.append(f"fast jump {max_jump:+.3f} in one tick (possible steam)")
    if abs(dp) >= 0.03:
        events.append(f"net drift {dp:+.3f} over window (possible steam/drift)")
    if abs(gap) >= 0.02:
        events.append(f"sharp-public gap {gap:+.3f} (fade candidate)")
    if not events:
        events.append("no notable events")

    state = {
        "match_id": match.get("id"),
        "window": {
            "n": len(seg),
            "idx_start": start,
            "idx_end": start + len(seg) - 1,
            "H_first": hs[0],
            "H_last": hs[-1],
            "p_first": round(p_first, 4),
            "p_last": round(p_last, 4),
            "dp": round(dp, 4),
            "slope": round(slope(ps), 5),
            "vol": round(std(ps), 4),
        },
        "ticks": [
            {
                "t": t.get("t"),
                "H": t.get("H"),
                "p": t.get("p"),
                "s": t.get("s"),
                "hh": t.get("hh"),
                "ha": t.get("ha"),
            }
            for t in seg
        ],
        "divergence": {
            "sharp_med": round(sharp_med, 4),
            "public_last": round(public_last, 4),
            "gap": round(gap, 4),
            "n_sharp": len(sharp_ps),
            "n_public": len(public_ps),
        },
        "line": {
            "distinct_H": distinct_h,
            "n_line_changes": n_line_changes,
        },
        "events": events,
    }
    return state


def main(argv=None):
    args = parse_args(argv)
    with open(args.input, encoding="utf-8") as f:
        matches = json.load(f)

    n_out = 0
    with open(args.output, "w", encoding="utf-8") as out:
        for m in matches:
            tl = m.get("tl") or []
            if len(tl) < args.window:
                continue
            y, is_push = settle_to_label(m.get("settle"))
            for start in range(0, len(tl) - args.window + 1, args.step):
                state = encode_window(m, tl, start, args.window)
                rec = {
                    "match_id": m.get("id"),
                    "league": m.get("league"),
                    "ft": m.get("ft"),
                    "ht": m.get("ht"),
                    "settle": m.get("settle"),
                    "y": y,
                    "is_push": is_push,
                    "H_close": m.get("H_close"),
                    "p_close_match": m.get("p_close"),
                    "idx_start": start,
                    "idx_end": start + args.window - 1,
                    "hash": sha1_state(state),
                    "state": state,
                }
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n_out += 1

    print(f"matches={len(matches)} windows={n_out} "
          f"(window={args.window} step={args.step}) -> {args.output}")


if __name__ == "__main__":
    sys.exit(main())
