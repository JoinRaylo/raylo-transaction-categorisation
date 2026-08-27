"""Retrain TF-IDF heads on the current (label-corrected) tuning_train.jsonl.

1. SGD logreg — overwrites outputs/distill_models/tfidf_logreg_v2.joblib
2. SGD hinge — outputs/distill_models/tfidf_linearsvm_sgd.joblib
3. liblinear LinearSVC via src/fit_linearsvc_liblinear.py, killed after --svc-timeout

Usage:
    python src/retrain_corrected_heads.py
    python src/retrain_corrected_heads.py --svc-timeout 1800
    python src/retrain_corrected_heads.py --hinge-only --skip-svc \\
        --hinge-out outputs/distill_models/tfidf_linearsvm_sgd_v5d.joblib
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys
import time

import joblib
import numpy as np
from scipy.sparse import csr_matrix, hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from distillation_bakeoff import (  # noqa: E402
    MODELS_DIR,
    OUT_DIR,
    SEED,
    _parse_tuning_jsonl,
    build_text,
)

LOGREG_PATH = MODELS_DIR / "tfidf_logreg_v2.joblib"
HINGE_PATH = MODELS_DIR / "tfidf_linearsvm_sgd.joblib"
FIT_SVC = ROOT / "src" / "fit_linearsvc_liblinear.py"


def _features(df, vectorizer=None):
    text = build_text(df)
    num = np.column_stack([
        np.log1p(np.abs(df["amount"].to_numpy(dtype=np.float32))),
        df["is_credit"].to_numpy(dtype=np.float32),
    ])
    if vectorizer is None:
        vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5),
                                     max_features=30_000, min_df=2)
        X_text = vectorizer.fit_transform(text)
    else:
        X_text = vectorizer.transform(text)
    X = hstack([X_text, csr_matrix(num)], format="csr")
    return vectorizer, X


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--svc-timeout", type=int, default=1800)
    parser.add_argument("--skip-logreg", action="store_true")
    parser.add_argument("--skip-hinge", action="store_true")
    parser.add_argument("--skip-svc", action="store_true")
    parser.add_argument(
        "--hinge-only", action="store_true",
        help="Fit a fresh TF-IDF and hinge only (no logreg). Use with --hinge-out.")
    parser.add_argument(
        "--hinge-out", type=pathlib.Path, default=None,
        help="Hinge dump path (default: tfidf_linearsvm_sgd.joblib serving name)")
    parser.add_argument(
        "--reuse-vectorizer", action="store_true",
        help="With --skip-logreg, reuse TF-IDF from the serving logreg dump")
    args = parser.parse_args()

    if args.hinge_only:
        args.skip_logreg = True
        args.skip_hinge = False

    train_path = OUT_DIR / "tuning_train.jsonl"
    print(f"Loading {train_path}...", file=sys.stderr)
    df = _parse_tuning_jsonl(train_path)
    rng = np.random.default_rng(SEED)
    df = df.iloc[rng.permutation(len(df))].reset_index(drop=True)
    y = df["leaf"].to_numpy()
    print(f"{len(df)} rows, {df['leaf'].nunique()} classes", file=sys.stderr)
    MODELS_DIR.mkdir(exist_ok=True)

    hinge_path = args.hinge_out or HINGE_PATH

    if args.hinge_only or (args.skip_logreg and not args.reuse_vectorizer):
        t0 = time.time()
        print("Fitting TF-IDF (no logreg)...", file=sys.stderr)
        vectorizer, X = _features(df)
        print(f"TF-IDF ready in {time.time() - t0:.0f}s", file=sys.stderr)
    elif args.skip_logreg and LOGREG_PATH.exists():
        bundle = joblib.load(LOGREG_PATH)
        vectorizer = bundle["vectorizer"]
        _, X = _features(df, vectorizer)
        print(f"Reusing vectorizer from {LOGREG_PATH.name}", file=sys.stderr)
    else:
        t0 = time.time()
        print("Training SGD logreg...", file=sys.stderr)
        vectorizer, X = _features(df)
        clf = SGDClassifier(loss="log_loss", alpha=1e-6, random_state=SEED,
                            tol=None, max_iter=50)
        clf.fit(X, y)
        joblib.dump({"vectorizer": vectorizer, "clf": clf, "kind": "tfidf"}, LOGREG_PATH)
        print(f"Wrote {LOGREG_PATH} in {time.time() - t0:.0f}s", file=sys.stderr)

    if not args.skip_hinge:
        t0 = time.time()
        print("Training SGD hinge SVM...", file=sys.stderr)
        hinge = SGDClassifier(loss="hinge", alpha=1e-6, random_state=SEED,
                              tol=None, max_iter=50)
        hinge.fit(X, y)
        joblib.dump({"vectorizer": vectorizer, "clf": hinge, "kind": "linearsvc"}, hinge_path)
        print(f"Wrote {hinge_path} in {time.time() - t0:.0f}s", file=sys.stderr)

    if args.skip_svc:
        return
    print(f"Launching liblinear LinearSVC (timeout {args.svc_timeout}s)...", file=sys.stderr)
    py = sys.executable
    try:
        subprocess.run([py, str(FIT_SVC)], timeout=args.svc_timeout, check=True)
    except subprocess.TimeoutExpired:
        print(f"LinearSVC still running after {args.svc_timeout}s — bouncing.", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
