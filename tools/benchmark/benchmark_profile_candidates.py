"""Profile a private customer-linked candidate draw for admission planning.

The candidate draw is source data, not authority state. This adapter joins only
opaque local evidence, computes the pinned effective-input and merchant-name
screens, reports connected block sizes and view decisions, and writes no public
candidate payload. Unknown historical aliases, family lineage and legacy coverage
remain quarantine reasons; this tool cannot authorize reservation or labelling.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from collections import Counter, defaultdict
from pathlib import Path

from benchmark_build_index import private_key
from benchmark_screen_exposure import (
    SOURCE_PATHS,
    historical_batches,
    sparse_keys,
    surface_fold,
    token_keys,
)
from benchmark_screen_merchants import merchant_batches
from raylo_txncat.benchmark import observation_key, project_head
from raylo_txncat.benchmark_exposure import ExposureIndex, file_sha256
from raylo_txncat.classifier_types import ClassifierInput
from raylo_txncat.dictionary import normalise_merchant
from raylo_txncat.hashing import canonical_json, strict_json_loads

MAX_CANDIDATES = 10_000
ARTIFACTS = {
    "tokenizer": "outputs/distill_models/txn_classifier_gold_distilled_s123/tokenizer.json",
    "mlm_tokenizer": "outputs/distill_models/txn_encoder_mlm_distilbert_full/tokenizer.json",
    "mlm_recipe": "outputs/distill_models/txn_encoder_mlm_distilbert_full/pretrain_meta.json",
    "hinge": "outputs/distill_models/tfidf_linearsvm_sgd_v8_risk.joblib",
}
SOURCE_TABLE = "raylo-production.dbt_production.intermediate_credit_plaid_transactions"
SCOPE_CONTRACT = {
    "source_kind": "customer_linked_plaid_materialized",
    "source_table": SOURCE_TABLE,
    "link_rule": "assessment_to_one_checkout_to_one_user_to_one_customer_record",
    "anonymous_id_recovery": False,
}
SCOPE_CONTRACT_SHA256 = hashlib.sha256(canonical_json(SCOPE_CONTRACT)).hexdigest()
POLICY_VERSION = "benchmark-admission-profile-policy-v1"
POLICY_SHA256 = hashlib.sha256(
    canonical_json(
        {
            "policy_version": POLICY_VERSION,
            "views": ("representative", "unseen_input", "unfamiliar_merchant"),
            "unknown_history": "quarantine",
            "strict_input_overlap": "reject",
            "merchant_name_absence": "not_family_absence",
            "authority": "local_profile_never_authorizes_consumption",
        }
    )
).hexdigest()
MERCHANT_SOURCES = (
    *SOURCE_PATHS,
    "taxonomy/merchant_dictionary.csv",
    "taxonomy/rules/t2_entity_collisions.csv",
    "data/production_labels_tranche4.csv",
    "outputs/tuning_gold_v2_split_manifest.csv",
)
LEGACY_FILES = (
    ("members.jsonl", "member_object_sha256"),
    ("label-conflicts.jsonl", "conflict_object_sha256"),
)


def _digest(path: Path) -> str:
    return file_sha256(path)


def _head(row: dict) -> ClassifierInput:
    amount = row.get("amount")
    direction = row.get("direction")
    if not isinstance(amount, str) or not amount or direction not in {"credit", "debit", "zero"}:
        raise ValueError("candidate amount/direction is invalid")
    if direction == "zero":
        direction = "debit"
    return ClassifierInput.from_research(
        {
            "merchant_raw": row.get("merchant_name"),
            "description_raw": row.get("description")
            if row.get("description") is not None
            else row.get("transaction_name"),
            "amount": amount,
            "direction": direction,
        }
    )


def _validate_candidate_receipt(
    receipt: dict, result_path: Path, extractor_sql: Path, extractor: Path
) -> None:
    if (
        receipt.get("schema_version") != "benchmark-candidate-extract-v1"
        or receipt.get("purpose") != "private_customer_linked_plaid_candidate_draw"
        or receipt.get("project") != "raylo-production"
        or receipt.get("location") != "EU"
        or receipt.get("statement_type") != "SELECT"
        or receipt.get("source_table") != SOURCE_TABLE
        or receipt.get("source_kind") != SCOPE_CONTRACT["source_kind"]
        or receipt.get("scope_contract") != SCOPE_CONTRACT
        or receipt.get("scope_contract_sha256") != SCOPE_CONTRACT_SHA256
        or receipt.get("anonymous_id_recovery") is not False
        or receipt.get("authorizes_consumption") is not False
        or receipt.get("executed") is not True
    ):
        raise ValueError("candidate receipt is outside the approved source contract")
    if receipt.get("sql_sha256") != _digest(extractor_sql) or receipt.get(
        "runner_sha256"
    ) != _digest(extractor):
        raise ValueError("candidate receipt is not bound to the current extractor")
    result_sha256 = receipt.get("result_sha256")
    if not isinstance(result_sha256, str) or _digest(result_path) != result_sha256:
        raise ValueError("candidate result is incomplete or changed")
    if (
        type(receipt.get("candidate_limit")) is not int
        or not 0 < receipt["candidate_limit"] <= MAX_CANDIDATES
    ):
        raise ValueError("candidate limit is outside scope")
    if (
        type(receipt.get("result_rows")) is not int
        or not 0 < receipt["result_rows"] <= receipt["candidate_limit"]
    ):
        raise ValueError("candidate result count is outside scope")
    for field in ("dry_run_bytes", "bytes_processed", "bytes_billed"):
        if type(receipt.get(field)) is not int or receipt[field] < 0:
            raise ValueError("candidate byte receipt is invalid")


def _load_candidates(
    directory: Path, extractor_sql: Path, extractor: Path
) -> tuple[dict, list[dict]]:
    receipt = strict_json_loads((directory / "receipt.json").read_bytes())
    path = directory / "candidates.jsonl"
    if not isinstance(receipt, dict):
        raise ValueError("candidate receipt is not an object")
    _validate_candidate_receipt(receipt, path, extractor_sql, extractor)
    rows = []
    events = set()
    with path.open("rb") as stream:
        for line in stream:
            row = strict_json_loads(line)
            if not isinstance(row, dict):
                raise ValueError("candidate row is not an object")
            required = (
                "account_id",
                "transaction_id",
                "customer_id",
                "assessment_id",
                "checkout_id",
                "user_id",
            )
            if any(type(row.get(field)) is not str or not row[field] for field in required):
                raise ValueError("candidate linkage fields are incomplete")
            link_counts = (
                "assessment_checkout_count",
                "checkout_user_count",
                "user_customer_count",
                "customer_record_count",
            )
            if any(type(row.get(field)) is not int or row[field] != 1 for field in link_counts):
                raise ValueError("candidate row is not backed by unique current links")
            event = (row["account_id"], row["transaction_id"])
            if event in events:
                raise ValueError("candidate draw contains duplicate events")
            events.add(event)
            rows.append(row)
    if len(rows) != receipt["result_rows"] or not 0 < len(rows) <= MAX_CANDIDATES:
        raise ValueError("candidate draw count is incomplete or outside scope")
    return receipt, rows


def _load_artifacts(research: Path, inventory: dict):
    import joblib
    from tokenizers import Tokenizer

    for relative in ARTIFACTS.values():
        if (
            relative not in inventory
            or _digest(research / relative) != inventory[relative]["sha256"]
        ):
            raise ValueError("pinned artifact changed or is unavailable")
    tokenizer_path = research / ARTIFACTS["tokenizer"]
    mlm_tokenizer_path = research / ARTIFACTS["mlm_tokenizer"]
    tokenizer_config = strict_json_loads(tokenizer_path.read_bytes())
    mlm_tokenizer_config = strict_json_loads(mlm_tokenizer_path.read_bytes())
    if {k: v for k, v in tokenizer_config.items() if k not in {"truncation", "padding"}} != {
        k: v for k, v in mlm_tokenizer_config.items() if k not in {"truncation", "padding"}
    }:
        raise ValueError("serving and MLM tokenizer semantics differ")
    recipe = strict_json_loads((research / ARTIFACTS["mlm_recipe"]).read_bytes())
    if recipe.get("max_len") != 48:
        raise ValueError("pinned tokenizer context is not 48")
    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    tokenizer.enable_truncation(max_length=48)
    tokenizer.no_padding()
    vectorizer = joblib.load(research / ARTIFACTS["hinge"])["vectorizer"]
    return tokenizer, vectorizer


def _candidate_keys(rows: list[dict], key, tokenizer, vectorizer):
    heads = [_head(row) for row in rows]
    events = [
        observation_key(
            key,
            namespace="plaid",
            account_id=row["account_id"],
            transaction_id=row["transaction_id"],
        )
        for row in rows
    ]
    projections = [project_head(head, key) for head in heads]
    values = {}
    for start in range(0, len(heads), 2048):
        batch = heads[start : start + 2048]
        encoded = list(
            token_keys(
                [head.transformer_text for head in batch],
                [head.is_credit for head in batch],
                tokenizer,
            )
        )
        sparse = list(sparse_keys(batch, vectorizer))
        for offset, (token, sparse_value) in enumerate(zip(encoded, sparse, strict=True), start):
            values[offset] = {
                "token48": token,
                "surface_fold": surface_fold(heads[offset].transformer_text),
                "hinge_sparse": sparse_value,
            }
    return heads, events, projections, values


def _screen_inputs(research: Path, inventory: dict, values: dict[int, dict], tokenizer, vectorizer):
    targets = {name: defaultdict(set) for name in ("token48", "surface_fold", "hinge_sparse")}
    for index, candidate in values.items():
        for name, value in candidate.items():
            targets[name][value].add(index)
    hits = {name: defaultdict(set) for name in targets}
    source_rows = {}
    for relative in SOURCE_PATHS:
        path = research / relative
        if _digest(path) != inventory[relative]["sha256"]:
            raise ValueError("historical source changed")
        count = 0
        for batch in historical_batches(path):
            full = isinstance(batch[0], ClassifierInput)
            texts = [head.transformer_text for head in batch] if full else [row[0] for row in batch]
            credits = [head.is_credit for head in batch] if full else [row[1] for row in batch]
            for name, batch_values in (
                ("token48", token_keys(texts, credits, tokenizer)),
                ("surface_fold", map(surface_fold, texts)),
                ("hinge_sparse", sparse_keys(batch, vectorizer) if full else ()),
            ):
                for value in batch_values:
                    if value in targets[name]:
                        hits[name][relative].update(targets[name][value])
            count += len(batch)
        if count != inventory[relative]["profile"]["rows"]:
            raise ValueError("historical source scan is incomplete")
        source_rows[relative] = count
    return hits, source_rows


def _screen_merchants(research: Path, inventory: dict, legacy: Path, rows: list[dict]):
    targets = defaultdict(set)
    for index, row in enumerate(rows):
        merchant = normalise_merchant(row.get("merchant_name"))
        if merchant:
            targets[merchant].add(index)
    hits = defaultdict(set)
    source_rows = {}
    for relative in MERCHANT_SOURCES:
        path = research / relative
        if _digest(path) != inventory[relative]["sha256"]:
            raise ValueError("merchant source changed")
        count = 0
        for batch in merchant_batches(path):
            count += len(batch)
            for value in batch:
                merchant = normalise_merchant(value)
                if merchant in targets:
                    for index in targets[merchant]:
                        hits[index].add(relative)
        if count != inventory[relative]["profile"]["rows"]:
            raise ValueError("merchant source scan is incomplete")
        source_rows[relative] = count
    legacy_summary = strict_json_loads((legacy / "summary.json").read_bytes())
    for filename, digest_key in LEGACY_FILES:
        path = legacy / filename
        if _digest(path) != legacy_summary[digest_key]:
            raise ValueError("legacy membership changed")
        count = 0
        with path.open("rb") as stream:
            for line in stream:
                record = strict_json_loads(line)
                if not isinstance(record, dict) or not isinstance(record.get("input"), dict):
                    raise ValueError("legacy record is malformed")
                merchant = normalise_merchant(record["input"].get("merchant_raw"))
                if merchant in targets:
                    for index in targets[merchant]:
                        hits[index].add("legacy/" + filename)
                count += 1
        source_rows["legacy/" + filename] = count
    return hits, source_rows


def _view_decisions(
    *,
    current_identity: bool,
    aliases_verified: bool,
    identity_history_complete: bool,
    input_sources: set[str],
    input_history_complete: bool,
    merchant_present: bool,
    merchant_known: bool,
    family_reviewed: bool,
    family_history_complete: bool,
    legacy_index_complete: bool,
):
    decisions = {}
    for view in ("representative", "unseen_input", "unfamiliar_merchant"):
        reject, quarantine = set(), set()
        if not current_identity:
            quarantine.add("unresolved_identity")
        if not aliases_verified:
            quarantine.add("event_alias_history_unknown")
        if not identity_history_complete:
            quarantine.add("unknown_identity_history")
        if not legacy_index_complete:
            quarantine.add("missing_legacy_exclusion_index")
        if view in {"unseen_input", "unfamiliar_merchant"}:
            if input_sources:
                reject.add("effective_input_overlap")
            if not input_history_complete:
                quarantine.add("unknown_input_history")
        if view == "unfamiliar_merchant":
            if not merchant_present:
                quarantine.add("blank_not_unfamiliar")
            if merchant_known:
                reject.add("merchant_family_overlap")
            if not family_reviewed:
                quarantine.add("unresolved_merchant_family")
            if not family_history_complete:
                quarantine.add("unknown_family_history")
        status = "reject" if reject else "quarantine" if quarantine else "eligible_preflight"
        decisions[view] = {
            "status": status,
            "reasons": tuple(sorted(reject | quarantine)),
            "input_exposure": "seen"
            if input_sources
            else "unknown"
            if not input_history_complete
            else "not_found",
        }
    return decisions


def _block_stats(values: dict[str, list[str]]) -> dict[str, dict]:
    result = {}
    for name, groups in values.items():
        counts = Counter(groups)
        sizes = list(counts.values())
        result[name] = {
            "groups": len(sizes),
            "rows": sum(sizes),
            "min_rows_per_group": min(sizes) if sizes else 0,
            "max_rows_per_group": max(sizes) if sizes else 0,
            "size_histogram": {str(size): count for size, count in sorted(Counter(sizes).items())},
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidates", "research", "inventory", "index", "key-file", "legacy", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    args.output.mkdir(mode=0o700, exist_ok=False)
    extractor_sql = Path(__file__).with_name("benchmark_candidate_extract.sql")
    extractor = Path(__file__).with_name("benchmark_candidate_extract.py")
    candidate_receipt, rows = _load_candidates(args.candidates, extractor_sql, extractor)
    inventory = strict_json_loads(args.inventory.read_bytes())["files"]
    index_receipt = strict_json_loads((args.index / "receipt.json").read_bytes())
    key = private_key(args.key_file, index_receipt["key_id"])
    index = ExposureIndex(
        args.index / "inputs.sqlite",
        expected_sha256=index_receipt["database_sha256"],
        key=key,
    )
    try:
        tokenizer, vectorizer = _load_artifacts(args.research, inventory)
        heads, events, projections, values = _candidate_keys(rows, key, tokenizer, vectorizer)
        input_hits, input_source_rows = _screen_inputs(
            args.research, inventory, values, tokenizer, vectorizer
        )
        merchant_hits, merchant_source_rows = _screen_merchants(
            args.research, inventory, args.legacy, rows
        )
        opaque = []
        reason_counts = {
            view: Counter() for view in ("representative", "unseen_input", "unfamiliar_merchant")
        }
        status_counts = {view: Counter() for view in reason_counts}
        combinations = Counter()
        strata = Counter()
        blocks = {name: [] for name in ("customer", "account", "assignment")}
        input_counts = Counter()
        merchant_known_count = 0
        merchant_present_count = 0
        for index_number, row in enumerate(rows):
            event = events[index_number]
            account = key.token("account", {"namespace": "plaid", "account": row["account_id"]})
            customer = key.token("customer", {"namespace": "raylo", "customer": row["customer_id"]})
            assignment = key.token(
                "customer",
                {
                    "namespace": "raylo",
                    "customer": row["customer_id"],
                    "policy": "customer-block-v1",
                },
            )
            input_sources = set()
            for projection in projections[index_number]:
                input_sources.update(index.lookup(projection)["sources"])
            for name in ("token48", "surface_fold", "hinge_sparse"):
                for source, found in input_hits[name].items():
                    if index_number in found:
                        input_sources.add(source)
            for name in ("token48", "surface_fold", "hinge_sparse"):
                if any(index_number in found for found in input_hits[name].values()):
                    input_counts[name] += 1
            merchant = normalise_merchant(row.get("merchant_name"))
            merchant_present = bool(merchant)
            merchant_known = bool(merchant_hits[index_number])
            merchant_present_count += merchant_present
            merchant_known_count += merchant_known
            decisions = _view_decisions(
                current_identity=True,
                aliases_verified=False,
                identity_history_complete=False,
                input_sources=input_sources,
                input_history_complete=False,
                merchant_present=merchant_present,
                merchant_known=merchant_known,
                family_reviewed=False,
                family_history_complete=False,
                legacy_index_complete=False,
            )
            eligible = []
            for view, decision in decisions.items():
                status_counts[view][decision["status"]] += 1
                reason_counts[view].update(decision["reasons"])
                if decision["status"] == "eligible_preflight":
                    eligible.append(view)
            combinations["+".join(eligible) or "none"] += 1
            strata[row.get("source_stratum", "unknown")] += 1
            blocks["customer"].append(customer)
            blocks["account"].append(account)
            blocks["assignment"].append(assignment)
            opaque.append(
                {
                    "candidate_id": hashlib.sha256(
                        canonical_json(
                            {"source": candidate_receipt["result_sha256"], "event": event}
                        )
                    ).hexdigest(),
                    "source_snapshot_sha256": candidate_receipt["result_sha256"],
                    "observation": event,
                    "event_aliases": (),
                    "account": account,
                    "customer": customer,
                    "assignment_block": assignment,
                    "input_sources": tuple(sorted(input_sources)),
                    "merchant_present": merchant_present,
                    "merchant_known_sources": tuple(sorted(merchant_hits[index_number])),
                    "views": decisions,
                    "source_stratum": row.get("source_stratum", "unknown"),
                    "authorizes_consumption": False,
                }
            )
        opaque_path = args.output / "opaque-candidates.jsonl"
        with opaque_path.open("xb") as stream:
            for record in opaque:
                stream.write(canonical_json(record) + b"\n")
        os.chmod(opaque_path, 0o600)
        profile = {
            "schema_version": "benchmark-admission-profile-v1",
            "purpose": "admission_planning_not_benchmark_authority",
            "source_kind": "customer_linked_plaid_materialized_draw",
            "scope_contract": SCOPE_CONTRACT,
            "scope_contract_sha256": SCOPE_CONTRACT_SHA256,
            "policy_version": POLICY_VERSION,
            "policy_sha256": POLICY_SHA256,
            "source_snapshot_sha256": candidate_receipt["result_sha256"],
            "candidate_rows": len(rows),
            "distinct_events": len(events),
            "source_strata": dict(sorted(strata.items())),
            "block_stats": _block_stats(blocks),
            "input_exposure": dict(sorted(input_counts.items())),
            "merchant": {
                "present": merchant_present_count,
                "blank": len(rows) - merchant_present_count,
                "known_name": merchant_known_count,
                "unknown_name": merchant_present_count - merchant_known_count,
                "family_reviewed": 0,
            },
            "views": {
                view: {
                    "status": dict(sorted(status_counts[view].items())),
                    "reasons": dict(sorted(reason_counts[view].items())),
                }
                for view in status_counts
            },
            "eligible_view_combinations": dict(sorted(combinations.items())),
            "lineage": {
                "candidate_receipt_sha256": _digest(args.candidates / "receipt.json"),
                "index_receipt_sha256": _digest(args.index / "receipt.json"),
                "index_database_sha256": index_receipt["database_sha256"],
                "inventory_sha256": _digest(args.inventory),
                "legacy_summary_sha256": _digest(args.legacy / "summary.json"),
                "candidate_extractor_sha256": _digest(extractor),
                "candidate_sql_sha256": _digest(extractor_sql),
                "profiler_sha256": _digest(Path(__file__)),
                "policy_sha256": POLICY_SHA256,
                "input_source_rows": input_source_rows,
                "merchant_source_rows": merchant_source_rows,
                "opaque_candidates_sha256": _digest(opaque_path),
            },
            "history_flags": {
                "event_aliases_verified": False,
                "identity_history_complete": False,
                "input_history_complete": False,
                "family_history_complete": False,
                "legacy_index_complete": False,
            },
            "authorizes_consumption": False,
            "rows_reserved_or_labelled": 0,
            "risk_controls": {
                "effective_iam_isolation": "accepted_internal_benchmark_risk",
                "logical_train_selection_separation_required": True,
                "managed_runtime_authority_required": True,
            },
            "next_gate": (
                "verify raw report aliases and historical identity/exposure/family evidence, "
                "then reprofile under runtime authority"
            ),
        }
        (args.output / "profile.json").write_bytes(canonical_json(profile) + b"\n")
        os.chmod(args.output / "profile.json", 0o600)
        print(f"Profiled {len(rows):,} candidate rows; no admission authorized.")
    finally:
        index.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "Admission profile failed; no eligibility or consumption claim is valid."
        ) from None
