"""Fit liblinear LinearSVC on the frozen TF-IDF from tfidf_logreg_v2.joblib."""
from __future__ import annotations

import pathlib
import sys
import time

import joblib
import numpy as np
from scipy.sparse import csr_matrix, hstack
from sklearn.multiclass import OneVsRestClassifier
from sklearn.svm import LinearSVC

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
SVC_PATH = MODELS_DIR / "tfidf_linearsvc_liblinear.joblib"


def main():
    t0 = time.time()
    bundle = joblib.load(LOGREG_PATH)
    df = _parse_tuning_jsonl(OUT_DIR / "tuning_train.jsonl")
    rng = np.random.default_rng(SEED)
    df = df.iloc[rng.permutation(len(df))].reset_index(drop=True)
    text = build_text(df)
    num = np.column_stack([
        np.log1p(np.abs(df["amount"].to_numpy(dtype=np.float32))),
        df["is_credit"].to_numpy(dtype=np.float32),
    ])
    X = hstack([bundle["vectorizer"].transform(text), csr_matrix(num)], format="csr")
    y = df["leaf"].to_numpy()
    print(f"Fitting LinearSVC OvR on {X.shape}...", file=sys.stderr)
    clf = OneVsRestClassifier(
        LinearSVC(C=1.0, dual=False, max_iter=1000, tol=1e-3, random_state=SEED),
        n_jobs=-1,
    )
    clf.fit(X, y)
    joblib.dump({"vectorizer": bundle["vectorizer"], "clf": clf, "kind": "linearsvc"}, SVC_PATH)
    print(f"Wrote {SVC_PATH} in {time.time() - t0:.0f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
