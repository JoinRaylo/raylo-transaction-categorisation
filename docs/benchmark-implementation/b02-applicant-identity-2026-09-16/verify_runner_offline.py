#!/usr/bin/env python3
"""Offline guards for the bounded applicant identity runner.

This test deliberately stubs BigQuery.  It creates only synthetic identifiers and
never contacts a warehouse or prints cohort values.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

RUNNER_PATH = Path(
    os.environ.get(
        "IDENTITY_RUNNER_PATH",
        Path(__file__).with_name("run_applicant_identity_coverage.py"),
    )
)


class FakeQueryJobConfig:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class FakeArrayQueryParameter:
    def __init__(self, *args):
        self.args = args


class FakeTable:
    etag = "synthetic"
    created = None
    modified = None
    num_rows = 0
    num_bytes = 0
    schema = []


class FakeJob:
    def __init__(
        self,
        bytes_processed,
        result_rows=(),
        statement_type="SELECT",
        total_bytes_billed=0,
    ):
        self.total_bytes_processed = bytes_processed
        self.job_id = "synthetic-job"
        self.statement_type = statement_type
        self.total_bytes_billed = total_bytes_billed
        self._result_rows = result_rows

    def result(self):
        return iter(self._result_rows)


class FakeClient:
    jobs = []

    def __init__(self, project):
        self.project = project

    def get_table(self, name):
        return FakeTable()

    def query(self, sql, location, job_config):
        return self.jobs.pop(0)


def load_runner():
    # The production runner imports google-cloud-bigquery, which is intentionally
    # unavailable in this offline test environment.
    bigquery = types.ModuleType("google.cloud.bigquery")
    bigquery.QueryJobConfig = FakeQueryJobConfig
    bigquery.ArrayQueryParameter = FakeArrayQueryParameter
    bigquery.Client = FakeClient
    cloud = types.ModuleType("google.cloud")
    cloud.bigquery = bigquery
    google = types.ModuleType("google")
    google.cloud = cloud
    sys.modules.update({"google": google, "google.cloud": cloud, "google.cloud.bigquery": bigquery})

    spec = importlib.util.spec_from_file_location("identity_runner", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def synthetic_rows():
    rows = []
    for index in range(99):
        missing = index < 49
        rows.append(
            {
                "assessment_id": f"assessment-{index:03d}",
                "checkout_id": f"checkout-{index:03d}",
                "user_count": 0 if missing else 1,
                "user_customer_count": None if missing else 1,
            }
        )
    return rows


class RunnerOfflineTests(unittest.TestCase):
    def setUp(self):
        self.runner = load_runner()
        self.temp = tempfile.TemporaryDirectory(prefix="identity-runner-", dir="/private/tmp")
        self.base = Path(self.temp.name)
        (self.base / "links").mkdir()
        self.rows = synthetic_rows()
        self.write_links(self.rows)

    def tearDown(self):
        self.temp.cleanup()

    def write_links(self, rows, statement_type="SELECT"):
        rows_bytes = ("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n").encode()
        digest = hashlib.sha256(rows_bytes).hexdigest()
        (self.base / "links" / "rows.jsonl").write_bytes(rows_bytes)
        (self.base / "links" / "receipt.json").write_text(
            json.dumps(
                {
                    "project": self.runner.PROJECT,
                    "location": self.runner.LOCATION,
                    "statement_type": statement_type,
                    "result_rows": 99,
                    "result_sha256": digest,
                }
            )
        )
        self.runner.EXPECTED_LINKS_ROWS_SHA256 = digest

    def test_valid_cohort_preserves_49(self):
        checkout_ids, _, _ = self.runner.read_and_validate_cohort(self.base)
        self.assertEqual(len(checkout_ids), 49)

    def test_modified_cohort_file_is_rejected(self):
        changed = list(self.rows)
        changed[0] = dict(changed[0], user_count=1, user_customer_count=1)
        rows_path = self.base / "links" / "rows.jsonl"
        rows_path.write_bytes(
            ("\n".join(json.dumps(row, sort_keys=True) for row in changed) + "\n").encode()
        )
        with self.assertRaises(RuntimeError):
            self.runner.read_and_validate_cohort(self.base)

    def test_missing_duplicate_and_blank_ids_are_rejected(self):
        cases = []
        missing = list(self.rows)
        missing[0] = dict(missing[0])
        del missing[0]["checkout_id"]
        cases.append(missing)
        duplicate = list(self.rows)
        duplicate[50] = dict(duplicate[50], checkout_id=duplicate[0]["checkout_id"])
        cases.append(duplicate)
        blank = list(self.rows)
        blank[0] = dict(blank[0], assessment_id="   ")
        cases.append(blank)
        for malformed in cases:
            with self.subTest():
                self.write_links(malformed)
                with self.assertRaises(RuntimeError):
                    self.runner.read_and_validate_cohort(self.base)

    def test_non_select_receipt_is_rejected(self):
        self.write_links(self.rows, statement_type="UPDATE")
        with self.assertRaises(RuntimeError):
            self.runner.read_and_validate_cohort(self.base)

    def test_dry_run_budget_guard_is_enforced(self):
        sql_path = self.base / "probe.sql"
        sql_path.write_text("SELECT 1\n")
        self.runner.SQL_PATH = sql_path
        FakeClient.jobs = [FakeJob(self.runner.MAXIMUM_BYTES_BILLED + 1)]
        with self.assertRaises(RuntimeError):
            self.runner.run(False, self.base, self.base / "out")

    def test_non_select_dry_run_stops_before_execute(self):
        sql_path = self.base / "probe.sql"
        sql_path.write_text("SELECT 1\n")
        self.runner.SQL_PATH = sql_path
        FakeClient.jobs = [
            FakeJob(1, statement_type="UPDATE"),
            FakeJob(1, [{"cohort_rows": 49, "cohort_unique_checkouts": 49}]),
        ]
        with self.assertRaises(RuntimeError):
            self.runner.run(True, self.base, self.base / "out")
        self.assertEqual(len(FakeClient.jobs), 1)

    def test_wrong_result_denominator_stops_receipt_publication(self):
        sql_path = self.base / "probe.sql"
        sql_path.write_text("SELECT 1\n")
        self.runner.SQL_PATH = sql_path
        FakeClient.jobs = [
            FakeJob(1),
            FakeJob(
                1,
                [{"cohort_rows": 48, "cohort_unique_checkouts": 49}],
                total_bytes_billed=1,
            ),
        ]
        output_dir = self.base / "out"
        with self.assertRaises(RuntimeError):
            self.runner.run(True, self.base, output_dir)
        self.assertFalse((output_dir / "executed_receipt.json").exists())


if __name__ == "__main__":
    unittest.main()
