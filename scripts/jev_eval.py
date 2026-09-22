"""Evaluate baseline vs +Jev features (stdlib only, no sklearn/numpy).

Joins data/jev_windows.jsonl with data/jev_features.jsonl on hash, fits two
tiny logistic regressions (baseline numeric vs numeric+Jev) with a
match-grouped train/test split, and reports Brier / log-loss / AUC /
accuracy. Proves whether Jev judgments add signal over p_last alone.

Usage:
    python jev_eval.py                                   # needs jev_features
    python jev_batch.py --dry-run --limit 200 && python jev_eval.py --min-test 20
"""

import argparse
import json
import math
import os
import sys
from collections import defaultdict


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Eval baseline vs +Jev.")
    ap.add_argument("--windows", default=os.path.join("data", "jev_windows.jsonl"))
    ap.add_argument("--features", default=os.path.join("data", "jev_features.jsonl"))
    ap.add_argument("--out", default=os.path.join("data", "jev_eval.json"))
    ap.add_argument("--train-matches", type=int, default=60)
    ap.add_argument("--exclude-push", action="store_true", default=True)
    ap.add_argument("--lr", type=float, default=0.1)
    ap.add_argument("--epochs", type=int, default=500)
    ap.add_argument("--l2", type=float, default=1.0)
    ap.add_argument("--min-test", type=int, default=1)
    return ap.parse_args(argv)


def load_jsonl(path):
    recs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def clamp(p, lo=1e-6, hi=1 - 1e-6):
    return min(hi, max(lo, p))


def sigmoid(z):
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


def auc_score(y, p):
    # Mann-Whitney rank AUC, ties averaged.
    order = sorted(range(len(y)), key=lambda i: p[i])
    n_pos = sum(y)
    n_neg = len(y) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    rank_sum = 0.0
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and p[order[j + 1]] == p[order[i]]:
            j += 1
        avg_rank = (i + 1 + j + 1) / 2.0  # 1-based
        for k in range(i, j + 1):
            if y[order[k]] == 1:
                rank_sum += avg_rank
        i = j + 1
    return (rank_sum - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def metrics(y, p):
    n = len(y)
    brier = sum((pi - yi) ** 2 for yi, pi in zip(y, p)) / n
    ll = -sum(yi * math.log(clamp(pi)) + (1 - yi) * math.log(clamp(1 - pi))
               for yi, pi in zip(y, p)) / n
    acc = sum((pi >= 0.5) == bool(yi) for yi, pi in zip(y, p)) / n
    return {"n": n, "brier": brier, "logloss": ll,
            "auc": auc_score(y, p), "acc": acc}


def numeric_feats(w):
    s = w["state"]["window"]
    d = w["state"]["divergence"]
    ln = w["state"]["line"]
    return {
        "p_last": s["p_last"],
        "dp": s["dp"],
        "slope": s["slope"] * 10.0,  # scale to ~dp magnitude
        "vol": s["vol"],
        "gap": d["gap"],
        "sharp_frac": d["n_sharp"] / max(1, s["n"]),
        "n_line_changes": float(ln["n_line_changes"]),
    }


BASE_NUM_KEYS = ["p_last", "dp", "slope", "vol", "gap",
                 "sharp_frac", "n_line_changes"]


def jev_feats(ans):
    out = {}
    reg = (ans.get("regime") or {})
    probs = reg.get("probabilities") or {}
    for k in ("stable", "steam_sharp", "drift_public", "reversal",
              "choppy", "no_clear"):
        try:
            out[f"reg_{k}"] = float(probs.get(k, 0.0))
        except (TypeError, ValueError):
            out[f"reg_{k}"] = 0.0
    out["reg_conf"] = float(reg.get("confidence", 0.0) or 0.0)
    mom = ans.get("momentum") or {}
    tox = ans.get("toxicity") or {}
    try:
        out["momentum"] = float(mom.get("score", 1.0)) / 2.0
    except (TypeError, ValueError):
        out["momentum"] = 0.5
    try:
        out["toxicity"] = float(tox.get("score", 1.0)) / 2.0
    except (TypeError, ValueError):
        out["toxicity"] = 0.5
    out["momentum_conf"] = float(mom.get("confidence", 0.0) or 0.0)
    out["toxicity_conf"] = float(tox.get("confidence", 0.0) or 0.0)
    for k in ("is_steam", "is_public_fade", "line_unstable"):
        try:
            out[k] = float((ans.get(k) or {}).get("noul", 0.5))
        except (TypeError, ValueError):
            out[k] = 0.5
    return out


def design_matrix(rows, keys):
    return [[r["feat"][k] for k in keys] for r in rows]


def fit_logreg(X, y, lr=0.1, epochs=500, l2=1.0):
    # Standardize with train stats, GD on [bias + weights], L2 (no penalty on bias).
    n = len(X)
    d = len(X[0]) if n else 0
    mu = [sum(col) / n for col in zip(*X)] if n else [0.0] * d
    sd = []
    for j in range(d):
        v = sum((row[j] - mu[j]) ** 2 for row in X) / n if n else 0.0
        sd.append(math.sqrt(v) or 1.0)
    Xs = [[(row[j] - mu[j]) / sd[j] for j in range(d)] for row in X]
    w = [0.0] * (d + 1)
    for _ in range(epochs):
        grad = [0.0] * (d + 1)
        for xi, yi in zip(Xs, y):
            z = w[0] + sum(w[j + 1] * xi[j] for j in range(d))
            err = sigmoid(z) - yi
            grad[0] += err
            for j in range(d):
                grad[j + 1] += err * xi[j]
        w[0] -= lr * grad[0] / n
        for j in range(d):
            w[j + 1] -= lr * (grad[j + 1] / n + l2 * w[j + 1] / n)
    return {"mu": mu, "sd": sd, "w": w}


def predict_logreg(model, X):
    mu, sd, w = model["mu"], model["sd"], model["w"]
    d = len(mu)
    out = []
    for row in X:
        xs = [(row[j] - mu[j]) / sd[j] for j in range(d)]
        out.append(sigmoid(w[0] + sum(w[j + 1] * xs[j] for j in range(d))))
    return out


def main(argv=None):
    args = parse_args(argv)
    windows = load_jsonl(args.windows)
    feats = load_jsonl(args.features)
    if not windows:
        print(f"ERROR: no windows in {args.windows}. Run jev_encode.py first.",
              file=sys.stderr)
        return 2
    if not feats:
        print(f"ERROR: no features in {args.features}. Run jev_batch.py first.",
              file=sys.stderr)
        return 2

    by_hash = {w["hash"]: w for w in windows}
    rows = []
    n_push = 0
    for f in feats:
        w = by_hash.get(f.get("hash"))
        if w is None:
            continue
        if args.exclude_push and (w.get("is_push") or f.get("is_push")):
            n_push += 1
            continue
        num = numeric_feats(w)
        jf = jev_feats(f.get("answers") or {})
        feat = dict(num)
        feat.update(jf)
        rows.append({"match_id": w["match_id"], "y": int(w["y"]),
                     "p_last": num["p_last"], "feat": feat})
    if not rows:
        print("ERROR: nothing joined (all pushes or hash mismatch).",
              file=sys.stderr)
        return 2

    match_ids = sorted({r["match_id"] for r in rows})
    train_ids = set(match_ids[:args.train_matches])
    tr = [r for r in rows if r["match_id"] in train_ids]
    te = [r for r in rows if r["match_id"] not in train_ids]
    if len(te) < args.min_test:
        print(f"ERROR: test rows {len(te)} < min {args.min_test}; "
              f"lower --train-matches or add features.", file=sys.stderr)
        return 2

    jev_keys = sorted(k for k in rows[0]["feat"] if k not in BASE_NUM_KEYS)
    full_keys = BASE_NUM_KEYS + jev_keys

    y_tr = [r["y"] for r in tr]
    y_te = [r["y"] for r in te]
    naive_te = [clamp(r["p_last"]) for r in te]

    m_base = fit_logreg(design_matrix(tr, BASE_NUM_KEYS), y_tr,
                        args.lr, args.epochs, args.l2)
    m_full = fit_logreg(design_matrix(tr, full_keys), y_tr,
                        args.lr, args.epochs, args.l2)
    p_base = predict_logreg(m_base, design_matrix(te, BASE_NUM_KEYS))
    p_full = predict_logreg(m_full, design_matrix(te, full_keys))

    report = {
        "matches": len(match_ids),
        "train_matches": len(train_ids),
        "test_matches": len(match_ids) - len(train_ids),
        "rows": len(rows),
        "train_rows": len(tr),
        "test_rows": len(te),
        "excluded_pushes": n_push,
        "keys": {"baseline": BASE_NUM_KEYS, "jev_added": jev_keys},
        "naive_p_last": metrics(y_te, naive_te),
        "baseline_logreg": metrics(y_te, p_base),
        "full_jev_logreg": metrics(y_te, p_full),
        "delta_brier_full_minus_base":
            metrics(y_te, p_full)["brier"] - metrics(y_te, p_base)["brier"],
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    def fmt(m):
        auc = "n/a" if m["auc"] != m["auc"] else f"{m['auc']:.3f}"
        return (f"n={m['n']} brier={m['brier']:.4f} "
                f"logloss={m['logloss']:.4f} auc={auc} acc={m['acc']:.3f}")

    print(f"matches={report['matches']} "
          f"train={report['train_matches']} test={report['test_matches']} "
          f"rows={report['rows']} (train={report['train_rows']} "
          f"test={report['test_rows']}, pushes excluded={n_push})")
    print(f"naive p_last : {fmt(report['naive_p_last'])}")
    print(f"baseline     : {fmt(report['baseline_logreg'])}")
    print(f"full +Jev    : {fmt(report['full_jev_logreg'])}")
    print(f"delta brier (full-base): "
          f"{report['delta_brier_full_minus_base']:+.4f}  (negative = Jev helps)")
    print(f"report -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
