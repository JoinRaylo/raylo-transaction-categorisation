"""Corroborate source identity without promoting indirect account links to customers.

Produces a private HMAC sidecar and public aggregate evidence. It does not mutate
the snapshot, resolve natural persons or certify historical split separation.
"""

import argparse
import os
from collections import Counter, defaultdict
from pathlib import Path

from benchmark_build_index import private_key
from raylo_txncat.benchmark import observation_key
from raylo_txncat.benchmark_exposure import file_sha256
from raylo_txncat.hashing import canonical_json, strict_json_loads


def indexed(rows, fields):
    result = {}
    for row in rows:
        key = tuple(row[f] for f in fields)
        if key in result and result[key] != row:
            raise ValueError("conflicting identity evidence")
        result[key] = row
    return result


def reconcile(source, links, reports, accounts, key):
    direct = indexed(links, ("assessment_id",))
    report_index = indexed(reports, ("external_request_id", "report_id", "item_id", "account_id"))
    account_index = indexed(accounts, ("account_id",))
    counts, event_statuses = Counter(), defaultdict(set)
    sidecar = []
    for position, row in enumerate(source, 1):
        link = direct[(row["assessment_id"],)]
        report = report_index[
            tuple(row[k] for k in ("external_request_id", "report_id", "item_id", "account_id"))
        ]
        account = account_index[(row["account_id"],)]
        if (
            link["checkout_count"] != 1
            or link["user_count"] > 1
            or (link["user_customer_count"] or 0) > 1
            or account["ambiguous_link_rows"]
            or report["assessment_id"] != row["assessment_id"]
            or report["client_report_id"] != link["checkout_id"]
        ):
            raise ValueError("ambiguous or inconsistent checkout evidence")
        if any(
            row[k] and row[k] != link[v]
            for k, v in (("user_id", "user_id"), ("customer_id", "user_customer_id"))
        ):
            raise ValueError("source identity changed")
        customer, user = link["user_customer_id"], link["user_id"]
        if report["client_user_id"] and report["client_user_id"] != user:
            raise ValueError("provider customer evidence conflicts")
        customers, users = set(account["customer_ids"]), set(account["user_ids"])
        if len(customers) != account["customers"] or len(users) != account["users"]:
            raise ValueError("incomplete account group evidence")
        if len(customers) > 1 or len(users) > 1:
            raise ValueError("ambiguous cross-assessment account")
        if customer and (customer not in customers or user not in users):
            raise ValueError("direct and account group evidence conflict")
        if link["order_customer_id"] and link["order_customer_id"] != customer:
            raise ValueError("order customer evidence conflicts")
        status = (
            "direct_customer_link"
            if row["customer_id"] and row["user_id"]
            else "recovered_current_checkout_link"
            if customer and user
            else "indirect_account_blocking_group"
            if customers and users
            else "unresolved_customer_identity"
        )
        counts[status] += 1
        event = observation_key(
            key,
            namespace="plaid",
            account_id=row["account_id"],
            transaction_id=row["transaction_id"],
        )
        event_statuses[event].add(status)
        sidecar.append(
            {
                "source_position": position,
                "key_id": key.key_id,
                "event": event,
                "account": key.token(
                    "account", {"namespace": "plaid", "account": row["account_id"]}
                ),
                "status": status,
                "direct_customer": key.token(
                    "customer", {"namespace": "raylo", "customer": customer}
                )
                if customer
                else None,
                "blocking_customers": sorted(
                    key.token("customer", {"namespace": "raylo", "customer": c}) for c in customers
                ),
                "provider_checkout_corroborated": True,
                "provider_user_corroborated": bool(report["client_user_id"]),
                "persistent_account_id_present": bool(report["persistent_account_id"]),
                "event_aliases_verified": False,
                "historical_identity_separation_verified": False,
                "authorizes_consumption": False,
            }
        )
    missing_states = Counter()
    for link in direct.values():
        if not link["user_id"]:
            missing_states.update(link["checkout_states"])
    return sidecar, {
        "schema_version": "benchmark-identity-reconciliation-v1",
        "source_observations": len(source),
        "distinct_account_transaction_events": len(event_statuses),
        "observation_status": dict(sorted(counts.items())),
        "event_status_combinations": dict(
            sorted(Counter("+".join(sorted(s)) for s in event_statuses.values()).items())
        ),
        "assessments_without_user": sum(not r["user_id"] for r in direct.values()),
        "assessments_without_user_by_checkout_state": dict(sorted(missing_states.items())),
        "provider_user_corroborated_observations": sum(
            r["provider_user_corroborated"] for r in sidecar
        ),
        "persistent_account_id_present_observations": sum(
            r["persistent_account_id_present"] for r in sidecar
        ),
        "indirect_account_links_are_verified_customers": False,
        "historical_identity_separation_verified": False,
        "source_snapshot_changed": False,
        "rows_reserved_or_labelled": 0,
        "authorizes_consumption": False,
    }


def load_verified(directory, source_sha=None):
    receipt = strict_json_loads((directory / "receipt.json").read_bytes())
    path = directory / ("observations.jsonl" if source_sha is None else "rows.jsonl")
    if file_sha256(path) != receipt["result_sha256"]:
        raise ValueError("private evidence changed")
    if source_sha is not None and (
        receipt["source_sha256"] != source_sha or receipt["statement_type"] != "SELECT"
    ):
        raise ValueError("investigation refers to another snapshot")
    with path.open("rb") as stream:
        rows = [strict_json_loads(line) for line in stream]
    if len(rows) != receipt["result_rows"]:
        raise ValueError("incomplete private evidence")
    return rows, receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "links", "reports", "accounts", "key-file", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    args.output.mkdir(mode=0o700, exist_ok=False)
    source, source_receipt = load_verified(args.source)
    evidence = [
        load_verified(p, source_receipt["result_sha256"])
        for p in (args.links, args.reports, args.accounts)
    ]
    sidecar, summary = reconcile(
        source,
        *(e[0] for e in evidence),
        private_key(args.key_file, "benchmark-private-20260916-v1"),
    )
    path = args.output / "identity-sidecar.jsonl"
    with path.open("xb") as stream:
        for row in sidecar:
            stream.write(canonical_json(row) + b"\n")
    summary.update(
        source_sha256=source_receipt["result_sha256"],
        evidence_receipts=[e[1] for e in evidence],
        private_sidecar_sha256=file_sha256(path),
        adapter_sha256=file_sha256(Path(__file__)),
    )
    (args.output / "summary.json").write_bytes(canonical_json(summary) + b"\n")
    print(f"Reconciled {len(sidecar):,} observations; no admission authorized.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Identity reconciliation failed; no identity may be certified.") from None
