"""Signed GINI must not treat an inverted score as equivalent."""
import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from credit_metrics import signed_gini  # noqa: E402


def test_signed_gini_inverted_score_is_negative():
    rng = np.random.default_rng(0)
    y = np.array([0] * 40 + [1] * 40)
    good_score = y.astype(float) + rng.normal(0, 0.1, size=len(y))
    assert signed_gini(good_score, y) > 0.8
    assert signed_gini(-good_score, y) < -0.8
    assert signed_gini(-good_score, y) == pytest.approx(-signed_gini(good_score, y), abs=1e-9)


def test_signed_gini_never_takes_abs():
    src = (ROOT / "src" / "credit_metrics.py").read_text()
    assert "abs(" not in src
    exp = (ROOT / "src" / "experiment3_taxonomy_iv.py").read_text()
    assert "from credit_metrics import signed_gini" in exp
    assert "max(auc" not in exp
