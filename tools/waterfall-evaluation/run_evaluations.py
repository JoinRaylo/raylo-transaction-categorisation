"""Run the complete permitted evaluation inventory against a local verified bundle.

Quality only: fixed inference clock, no network, no training or serving mutations.
Raw inputs never enter reports. Private row diagnostics support paired comparisons.
The same file and helpers are mirrored in research/tools/waterfall-evaluation/.
"""

import argparse
import csv
import importlib.metadata
import io
import os
import platform
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from evaluation_metrics import compare_runs, summarise
from ob_txn_categoriser.runtime import load_runtime
from ob_txn_categoriser.settings import Settings
from raylo_txncat.classifier import Classifier, Deadline
from raylo_txncat.classifier_types import ClassifierInput
from raylo_txncat.evalsets import EvaluationRegistry, require_evaluation_source
from raylo_txncat.hashing import canonical_json, sha256, strict_json_loads
from raylo_txncat.release import ReleaseIdentity, RuntimeConfig, config_hash
from raylo_txncat.seed_selection import parse_validation
from raylo_txncat.tiers import DeterministicTiers
from raylo_txncat.types import ProviderCategory, Transaction
from raylo_txncat.waterfall import Waterfall, research_overlay
from verify_evaluation_report import verify as verify_metrics

HERE = Path(__file__).resolve().parent
SCHEMA = "waterfall-evaluation-v1"


def save(path, obj):
    path.write_bytes(canonical_json(obj) + b"\n")


def inventory_sources(monorepo, research, inventory_path):
    inventory = strict_json_loads(inventory_path.read_bytes())
    registry_path = monorepo / "lib/raylo-txncat/contracts/eval_registry.json"
    raw = registry_path.read_bytes()
    if sha256(raw) != inventory["base_registry_sha256"]:
        raise ValueError("base registry changed: review the inventory")
    if raw != (research / "eval_registry.json").read_bytes():
        raise ValueError("research/monorepo registry drift")
    registry_data = strict_json_loads(raw)
    registry_data["entries"] += inventory["additional_entries"]
    registry = EvaluationRegistry.model_validate(registry_data)
    eligible = {e.dataset_id for e in registry.entries if e.role in {"development", "validation"}}
    if eligible != set(inventory["tasks"]):
        raise ValueError("inventory must cover every repeatable set exactly once")
    if not set(inventory["tasks"].values()) <= {
        "transactions",
        "v4_context_join",
        "merchant_dictionary",
        "head_validation",
        "head_and_t5",
    }:
        raise ValueError("unknown evaluation task")
    sources, metadata = {}, {}
    for entry in registry.entries:
        if entry.dataset_id not in eligible:
            metadata[entry.dataset_id] = {"status": "excluded_confirmation", "role": entry.role}
            continue  # Do not even open locked/retired files for this run.
        path = research / entry.path
        if not path.resolve().is_relative_to(research.resolve()):
            raise ValueError("evaluation path escapes research root")
        verified = require_evaluation_source(registry, path, purpose=entry.role)
        if verified.dataset_id != entry.dataset_id:
            raise ValueError("evaluation file identity differs from declared dataset")
        raw = path.read_bytes()
        if sha256(raw) != entry.sha256:
            raise ValueError("evaluation source changed during read")
        parsed = (
            parse_validation(raw)
            if entry.format == "chat_jsonl"
            else list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
        )
        if not parsed:
            raise ValueError("empty evaluation dataset")
        sources[entry.dataset_id] = parsed
        metadata[entry.dataset_id] = {
            "status": "pending",
            "registry_entry": entry.model_dump(mode="json"),
            "source_rows": len(parsed),
            "task": inventory["tasks"][entry.dataset_id],
        }
    return inventory, sources, metadata


def context_key(row):
    return (
        row["merchant_raw"],
        row["description_raw"],
        str(abs(Decimal(row["amount"])).normalize()),
        row["direction"],
    )


def join_v4(rows, context):
    """Exact many-to-one context join; never silently choose a conflicting context."""
    lookup = {}
    for row in context:
        key = context_key(row)
        value = (row["provider"], row["native_category_raw"])
        if key in lookup and lookup[key] != value:
            raise ValueError("conflicting v4 provider context")
        lookup[key] = value
    result = []
    for row in rows:
        if context_key(row) not in lookup:
            raise ValueError("missing v4 provider context")
        provider, native = lookup[context_key(row)]
        result.append(dict(row, provider=provider, native_category=native))
    if len(result) != len(rows):
        raise ValueError("v4 context join changed row count")
    return result


def adapt(name, task, source, sources, general):
    if task == "v4_context_join":
        source = join_v4(source, sources["gold_v4_eyeball"])
    rows = []
    for index, original in enumerate(source):
        if task == "head_validation":
            row = {
                "merchant_raw": original["vendor"],
                "description_raw": original["description"],
                "amount": str(original["amount"]),
                "direction": "credit" if original["is_credit"] else "debit",
                "gold_leaf": original["leaf"],
            }
        else:
            row = dict(original)
        gold = row["gold_leaf"]
        if gold not in general:
            raise ValueError(f"unknown gold category at {name} row {index + 1}")
        merchant_only = task == "merchant_dictionary"
        merchant = row["merchant"] if merchant_only else row["merchant_raw"]
        description = None if merchant_only else row["description_raw"]
        amount = None if merchant_only else abs(Decimal(row["amount"]))
        direction = "unknown" if merchant_only else row["direction"]
        provider = row.get("provider", "unknown")
        if amount is not None and (not amount.is_finite() or direction not in {"credit", "debit"}):
            raise ValueError(f"invalid amount/direction at {name} row {index + 1}")
        native = row.get("native_category", row.get("native_category_raw"))
        if task in {"transactions", "v4_context_join"}:
            if provider not in {"plaid", "equifax"} or native is None:
                raise ValueError(f"missing provider context at {name} row {index + 1}")
        provenance = row.get("tier") or row.get("gold_source") or row.get("source") or "unspecified"
        # A bounded source tag, never the free-form notes, reviewer ID or narrative.
        if len(provenance) > 100:
            provenance = "long_source_tag_omitted"
        inputs = {
            "merchant_raw": merchant,
            "description_raw": description,
            "direction": direction,
            "amount": str(amount.normalize()) if amount is not None else None,
            "provider": provider,
            "native_category": native,
        }
        rows.append(
            dict(
                inputs,
                dataset=name,
                row_id=f"{name}:{index + 1}",
                gold_leaf=gold,
                input_hash=sha256(canonical_json(inputs)),
                label_provenance=provenance,
                merchant_state="filled" if merchant.strip() else "blank",
                alt_leaf=row.get("alt_leaf") or None,
            )
        )
    return rows


@dataclass
class MemoHead:
    """Per-run raw-head memoisation only, shared across overlapping evaluation sets."""

    wrapped: object

    def __post_init__(self):
        self.name = self.wrapped.name
        self.cache = {}

    def predict_batch(self, rows):
        missing = list(dict.fromkeys(r for r in rows if r not in self.cache))
        if missing:
            predicted = self.wrapped.predict_batch(missing)
            if len(predicted) != len(missing):
                raise ValueError("head dropped rows")
            self.cache.update(zip(missing, predicted, strict=True))
        return tuple(self.cache[r] for r in rows)


def predictions(head, rows):
    result = []
    for start in range(0, len(rows), 64):
        inputs = [ClassifierInput.from_research(r) for r in rows[start : start + 64]]
        result.extend(head.predict_batch(inputs))
    return result


def diagnostic(row, view, head, leaf, tier, *, rule_id=None, residual=False, raw_leaf=None):
    return {
        k: row[k]
        for k in (
            "dataset",
            "row_id",
            "input_hash",
            "gold_leaf",
            "direction",
            "provider",
            "merchant_state",
            "label_provenance",
        )
    } | {
        "view": view,
        "head": head,
        "leaf": leaf,
        "tier": tier,
        "rule_id": rule_id,
        "residual": residual,
        "raw_leaf": raw_leaf,
    }


def serving_predictions(loaded, tiers, heads, head_name, rows):
    config = RuntimeConfig.model_validate(
        loaded.config.model_dump() | {"classifier_head": head_name}
    )
    identity = ReleaseIdentity(
        image_digest=loaded.identity.image_digest,
        bundle_sha=loaded.identity.bundle_sha,
        config_hash=config_hash(config),
    )
    waterfall = Waterfall(
        tiers,
        Classifier(
            transformer=heads["transformer"], hinge=heads["hinge"], config=config, identity=identity
        ),
    )
    transactions = [
        Transaction(
            transaction_id=row["row_id"],
            account_id="offline-evaluation",
            date=date(2000, 1, 1),
            amount=(
                -Decimal(row["amount"]) if row["direction"] == "credit" else Decimal(row["amount"])
            ),
            currency="GBP",
            merchant_name=row["merchant_raw"],
            description=row["description_raw"],
            transaction_name=None,
            is_pending=False,
            provider_category=ProviderCategory(detailed=row["native_category"]),
        )
        for row in rows
    ]
    result = []
    for start in range(0, len(rows), config.max_transactions):
        batch = waterfall.resolve(
            transactions[start : start + config.max_transactions],
            deadline=Deadline.at_admission(
                config.request_budget_ms, reserve_ms=500, clock=lambda: 100.0
            ),
        )
        if batch.degraded:
            raise ValueError("quality run unexpectedly degraded")
        for source, resolved in zip(
            rows[start : start + config.max_transactions], batch.rows, strict=True
        ):
            wire = resolved.to_result()
            if resolved.transaction_id != source["row_id"]:
                raise ValueError("serving row identity changed")
            result.append(
                diagnostic(
                    source,
                    "serving_plaid",
                    head_name,
                    wire.leaf,
                    resolved.resolved.tier,
                    rule_id=wire.rule_id,
                    residual=resolved.deterministic.classifier_eligible,
                    raw_leaf=resolved.classifier.prediction.leaf if resolved.classifier else None,
                )
            )
    return result


def require_views(grouped, task, rows):
    expected = (
        {("merchant_dictionary", "dictionary")}
        if task == "merchant_dictionary"
        else {("head_only", head) for head in ("transformer", "hinge")}
    )
    if task == "head_and_t5":
        expected |= {("legacy_head_plus_t5", head) for head in ("transformer", "hinge")}
    if task in {"transactions", "v4_context_join"}:
        expected.add(("deterministic_research", "none"))
        expected |= {("research_pipeline", head) for head in ("transformer", "hinge")}
        if any(r["provider"] == "plaid" for r in rows):
            expected |= {("serving_plaid", head) for head in ("transformer", "hinge")}
    if set(grouped) != expected:
        raise ValueError("missing or unexpected required evaluation view")


def evaluate(loaded, tiers, heads, rows, task):
    output = []
    if task == "merchant_dictionary":
        return [
            diagnostic(
                r,
                "merchant_dictionary",
                "dictionary",
                tiers.dictionary.lookup(r["merchant_raw"]),
                "T4_lookup",
            )
            for r in rows
        ]
    deterministic = (
        [
            tiers.resolve(
                r["merchant_raw"],
                r["direction"],
                r["description_raw"],
                r["native_category"],
                r["provider"],
            )
            for r in rows
        ]
        if task in {"transactions", "v4_context_join"}
        else None
    )
    if deterministic is not None:
        output += [
            diagnostic(
                r,
                "deterministic_research",
                "none",
                d.leaf,
                d.tier,
                rule_id=d.rule_id,
                residual=d.classifier_eligible,
            )
            for r, d in zip(rows, deterministic, strict=True)
        ]
    for head_name, head in heads.items():
        pred = predictions(head, rows)
        output += [
            diagnostic(r, "head_only", head_name, p.leaf, "head_prediction", raw_leaf=p.leaf)
            for r, p in zip(rows, pred, strict=True)
        ]
        if task == "head_and_t5":
            for row, p in zip(rows, pred, strict=True):
                rule = next(
                    (
                        rule
                        for rule in tiers.rules
                        if rule.matches(
                            row["merchant_raw"].strip().lower(),
                            row["description_raw"],
                            row["direction"],
                        )
                    ),
                    None,
                )
                output.append(
                    diagnostic(
                        row,
                        "legacy_head_plus_t5",
                        head_name,
                        rule.leaf if rule else p.leaf,
                        f"T5_{rule.rule_id}" if rule else "head_prediction",
                        rule_id=rule.rule_id if rule else None,
                        raw_leaf=p.leaf,
                    )
                )
        if deterministic is not None:
            for row, d, p in zip(rows, deterministic, pred, strict=True):
                resolved = research_overlay(
                    d, p, model_name="hinge-v8" if head_name == "hinge" else "transformer-s123"
                )
                output.append(
                    diagnostic(
                        row,
                        "research_pipeline",
                        head_name,
                        resolved.leaf,
                        resolved.tier,
                        rule_id=resolved.rule_id,
                        residual=d.classifier_eligible,
                        raw_leaf=p.leaf,
                    )
                )
            plaid = [r for r in rows if r["provider"] == "plaid"]
            if any(r["direction"] == "credit" and Decimal(r["amount"]) == 0 for r in plaid):
                raise ValueError("credit zero cannot be represented at the Plaid wire boundary")
            output += serving_predictions(loaded, tiers, heads, head_name, plaid)
    return output


def offline(event, _args):
    if event in {"socket.connect", "socket.getaddrinfo", "urllib.Request"}:
        raise PermissionError("evaluation network access forbidden")


def run_check(name, command, cwd, output, env):
    log_path = output / "checks" / f"{name}.log"
    with log_path.open("wb") as handle:
        result = subprocess.run(command, cwd=cwd, env=env, stdout=handle, stderr=subprocess.STDOUT)
    return {
        "status": "passed" if result.returncode == 0 else "failed",
        "exit_code": result.returncode,
        "command": command,
        "cwd": str(cwd),
        "log_sha256": sha256(log_path.read_bytes()),
    }


def git_identity(root):
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=root)

    # Do not emit unrelated dirty filenames or patch contents from the research checkout.
    return {
        "commit": git("rev-parse", "HEAD").decode().strip(),
        "tracked_dirty": bool(git("diff", "HEAD", "--stat")),
        "tracked_patch_sha256": sha256(git("diff", "HEAD", "--binary")),
    }


def source_hashes(monorepo, research):
    paths = sorted((monorepo / "lib/raylo-txncat/src/raylo_txncat").glob("*.py"))
    paths += sorted((monorepo / "apps/ob-txn-categoriser/src/ob_txn_categoriser").rglob("*.py"))
    paths += [monorepo / "uv.lock", monorepo / "pyproject.toml"]
    for directory in (
        "apps/ob-txn-categoriser/tests",
        "lib/raylo-txncat/tests",
        "apps/ob-txn-categoriser/scripts",
        "lib/raylo-txncat/scripts",
    ):
        paths += sorted((monorepo / directory).rglob("*.py"))
    app = {str(p.relative_to(monorepo)): sha256(p.read_bytes()) for p in paths}
    research_paths = [
        research / p
        for p in (
            "src/final_evaluation.py",
            "src/generate_crosswalk_sql.py",
            "src/score_t5b_residual.py",
            "src/confusion_analysis.py",
            "src/score_waterfall_pipeline.py",
            "sql/apply_crosswalk.sql",
            "taxonomy/taxonomy.csv",
            "taxonomy/merchant_dictionary.csv",
            "taxonomy/rules/deterministic_rules.csv",
            "taxonomy/rules/t2_entity_collisions.csv",
        )
    ]
    research_paths += [research / "requirements.txt"]
    research_paths += sorted((research / "tests").glob("*.py"))
    return {
        "monorepo": app,
        "research": {str(p.relative_to(research)): sha256(p.read_bytes()) for p in research_paths},
    }


def verify_research_inputs(bundle, research):
    # All bundle research sources under src/ and taxonomy/ must match. Model
    # artefacts themselves are verified by the bundle loader's manifest.
    sources = bundle.json("provenance.json")["source_files"]
    checked = 0
    for record in sources:
        if record["path"].startswith(("src/", "taxonomy/")):
            if sha256((research / record["path"]).read_bytes()) != record["sha256"]:
                raise ValueError("research definitions differ from bundle provenance")
            checked += 1
    return checked


def render_report(report):
    lines = [
        "# Repeatable waterfall evaluation",
        "",
        f"Status: **{report['status']}**. Mode: {report['mode']}. "
        f"Evaluated {report['evaluated_at']}.",
        "",
        "No pipeline, model or serving configuration was changed by this run.",
        "",
        "All percentages below use every row in the named view. The research pipeline",
        "uses its original unclassified strings; serving maps T6 abstention to T7/null.",
        "Do not pool these overlapping development/validation populations.",
        "",
        "| Dataset | View | Head | Rows | Specific leaf accuracy | Coverage | Research exact |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for item in report["evaluations"]:
        if item["view"] not in {
            "serving_plaid",
            "research_pipeline",
            "merchant_dictionary",
        } and item["dataset"] not in {"tuning_validation", "gold_transactions_risk_categories"}:
            continue
        metric = item["metrics"]["all"]

        def fmt(x):
            return f"{x:.2%}" if x is not None else "n/a"

        lines.append(
            f"| {item['dataset']} | {item['view']} | {item['head']} | {metric['n']} | "
            f"{fmt(metric['specific_leaf_accuracy'])} | {fmt(metric['coverage'])} | "
            f"{fmt(metric['research_exact_leaf_accuracy'])} |"
        )
    lines += ["", "## Inventory and limitations", ""]
    for name, item in report["datasets"].items():
        lines.append(f"- {name}: {item['status']}. " + item.get("limitation", ""))
    lines += ["", "## Checks", ""]
    for name, result in report["checks"].items():
        lines.append(f"- {name}: {result['status']}.")
    lines += [
        "",
        "## Interpretation",
        "",
        "This is a regression baseline; it does not estimate independent production accuracy.",
        "Historical training overlap and repeated selection limit generalisation claims.",
        "The pipeline benchmark is its preserved historical export; training disjointness has not",
        "been re-established against later training snapshots. Source tags are retained,",
        "not upgraded to human review. Merchant datasets score dictionary lookup only; validation",
        "and legacy risk data cannot establish full serving behaviour without provider context.",
        "Per-leaf precision/F1 treat any nonmatching gold, including unknown gold, as a nonmatch;",
        "Unknown-gold assignments are separately counted; they are not proven false positives.",
        "Macro F1 uses specific leaves with gold support. Empty denominators are null.",
        "GBP, account and date are API scaffolding only; currency eligibility, history features",
        "and Taktile transport are not evaluated. Inference uses a fixed clock: no latency claim.",
        "A passed run means evaluations executed; candidate quality gates require review.",
        "Locked v5/v6 were not scored. The accuracy runner does not open them; research",
        "integrity tests read retired-v5 membership to check exclusions, without scoring.",
        "No deployment or retraining was performed.",
        "",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--monorepo-root", type=Path, required=True)
    parser.add_argument("--research-root", type=Path, required=True)
    parser.add_argument("--research-python", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--bundle-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--baseline", type=Path, help="Prior complete private run directory for comparison"
    )
    args = parser.parse_args()
    mono, research = args.monorepo_root.resolve(), args.research_root.resolve()
    if args.output.resolve().is_relative_to(mono) or args.output.resolve().is_relative_to(research):
        raise ValueError("use a private output directory outside both repositories")
    args.output.mkdir(parents=True, exist_ok=True, mode=0o700)
    if any(args.output.iterdir()):
        raise ValueError("output directory must be empty")
    os.chmod(args.output, 0o700)
    (args.output / "checks").mkdir(mode=0o700)
    inventory_path = HERE / "evaluation_inventory.json"
    inventory, sources, datasets = inventory_sources(mono, research, inventory_path)
    regression_path = HERE / "evaluation_regressions.json"
    regressions = strict_json_loads(regression_path.read_bytes())
    sources["synthetic_credit_regressions"] = regressions["cases"]
    inventory["tasks"]["synthetic_credit_regressions"] = "transactions"
    datasets["synthetic_credit_regressions"] = {
        "status": "pending",
        "task": "transactions",
        "role": "synthetic_diagnostic",
        "source_rows": len(regressions["cases"]),
        "source_sha256": sha256(regression_path.read_bytes()),
        "diagnostic_only": regressions["note"],
    }
    initial_hashes = source_hashes(mono, research)
    harness_paths = [
        HERE / name
        for name in (
            "run_evaluations.py",
            "evaluation_metrics.py",
            "evaluation_inventory.json",
            "evaluation_regressions.json",
            "verify_evaluation_report.py",
        )
    ]
    harness_hashes = {p.name: sha256(p.read_bytes()) for p in harness_paths}
    report = {
        "schema_version": SCHEMA,
        "status": "incomplete",
        "mode": "candidate_comparison" if args.baseline else "baseline",
        "evaluated_at": datetime.now(UTC).isoformat(),
        "datasets": datasets,
        "evaluations": [],
        "checks": {},
        "source_sha256": initial_hashes,
        "harness_sha256": harness_hashes,
        "git": {"monorepo": git_identity(mono), "research": git_identity(research)},
        "command": [sys.executable, *sys.argv],
        "system": {
            "python": sys.version,
            "platform": platform.platform(),
            "packages": {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()},
        },
        "pipeline_changed_by_runner": False,
        "locked_data_scored": False,
        "accuracy_runner_opens_confirmation_files": False,
    }
    save(args.output / "summary.json", report)
    env = os.environ.copy()
    env.update(
        PYTHONDONTWRITEBYTECODE="1",
        TOKENIZERS_PARALLELISM="false",
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        PYTHONPATH=os.pathsep.join(
            [str(mono / "apps/ob-txn-categoriser/src"), str(mono / "lib/raylo-txncat/src")]
        ),
    )
    checks = [
        (
            "app_library_tests",
            [
                sys.executable,
                "-m",
                "pytest",
                "apps/ob-txn-categoriser/tests",
                "lib/raylo-txncat/tests",
                "-q",
                "-o",
                f"cache_dir={args.output / 'checks/pytest-cache'}",
            ],
            mono,
        ),
        (
            "research_tests",
            [
                str(args.research_python),
                "-m",
                "pytest",
                "tests/",
                "-q",
                "-o",
                f"cache_dir={args.output / 'checks/research-pytest-cache'}",
            ],
            research,
        ),
        (
            "lint",
            [
                sys.executable,
                "-m",
                "ruff",
                "check",
                "--no-cache",
                "apps/ob-txn-categoriser",
                "lib/raylo-txncat",
            ],
            mono,
        ),
        (
            "schemas",
            [sys.executable, "apps/ob-txn-categoriser/scripts/export_schema.py", "--check"],
            mono,
        ),
        (
            "deterministic_parity",
            [
                sys.executable,
                "lib/raylo-txncat/scripts/verify_deterministic.py",
                str(args.bundle),
                "--research-root",
                str(research),
                "--report",
                str(args.output / "checks/parity.json"),
            ],
            mono,
        ),
        (
            "real_model_startup",
            [
                sys.executable,
                "apps/ob-txn-categoriser/scripts/verify_startup.py",
                str(args.bundle),
                "--report",
                str(args.output / "checks/startup.json"),
            ],
            mono,
        ),
    ]
    for name, command, cwd in checks:
        print(f"Checking {name}", flush=True)
        report["checks"][name] = run_check(name, command, cwd, args.output, env)
        save(args.output / "summary.json", report)
        if report["checks"][name]["status"] != "passed":
            report["status"] = "failed"
            save(args.output / "summary.json", report)
            raise SystemExit(f"Required check failed: {name}; inspect its private log")
    report["system"]["research_python"] = subprocess.check_output(
        [str(args.research_python), "-c", "import sys; print(sys.version)"], text=True
    ).strip()
    report["system"]["research_packages"] = strict_json_loads(
        subprocess.check_output(
            [
                str(args.research_python),
                "-c",
                "import importlib.metadata as m, json; "
                "print(json.dumps({d.metadata['Name']:d.version for d in m.distributions()}))",
            ]
        )
    )
    sys.addaudithook(offline)
    loaded = load_runtime(
        Settings(
            artefact_bundle=str(args.bundle),
            artefact_bundle_sha=args.bundle_sha,
            image_digest="sha256:" + "c" * 64,
            classifier_degrade="refuse",
        )
    )
    if loaded.models.seed != 123 or loaded.config.t6_abstain_margin != 0.0:
        raise ValueError("review evaluation contract before changing selected head or cutoff")
    tiers = DeterministicTiers.from_bundle(loaded.bundle)
    report["research_source_files_verified"] = verify_research_inputs(loaded.bundle, research)
    report["bundle_manifest"] = loaded.bundle.manifest.model_dump(mode="json")
    report["runtime_config"] = loaded.config.model_dump(mode="json")
    report["quality_runtime_note"] = (
        "Synthetic image identity; fixed clock; degradation refused; not a serving release."
    )
    general = {leaf: row["general_category"] for leaf, row in tiers.taxonomy.rows.items()}
    report["general_mapping"] = general
    transformer, hinge = loaded.models.heads()
    heads = {"transformer": MemoHead(transformer), "hinge": MemoHead(hinge)}
    diagnostics = []
    for name, task in inventory["tasks"].items():
        print(f"Evaluating {name}: {len(sources[name])} rows ({task})", flush=True)
        rows = adapt(name, task, sources[name], sources, general)
        output = evaluate(loaded, tiers, heads, rows, task)
        grouped = defaultdict(list)
        for row in output:
            grouped[(row["view"], row["head"])].append(row)
        require_views(grouped, task, rows)
        for (view, head), evaluated in sorted(grouped.items()):
            expected = (
                sum(r["provider"] == "plaid" for r in rows)
                if view == "serving_plaid"
                else len(rows)
            )
            if len(evaluated) != expected:
                raise ValueError("evaluation lost source rows")
            metrics = summarise(evaluated, general)
            report["evaluations"].append(
                {"dataset": name, "view": view, "head": head, "metrics": metrics}
            )
            if view in {"serving_plaid", "merchant_dictionary"}:
                print(
                    f"  {view}/{head}: "
                    f"{metrics['all']['correct_specific_leaf_n']}/{expected} specific correct",
                    flush=True,
                )
        unsupported = task in {"merchant_dictionary", "head_validation", "head_and_t5"}
        datasets[name].update(
            status="passed",
            full_waterfall_status="unsupported" if unsupported else "passed",
            evaluated_views=[
                {"view": v, "head": h, "n": len(r)} for (v, h), r in sorted(grouped.items())
            ],
            native_missing_rows=sum(r["native_category"] in {None, ""} for r in rows),
            providers=dict(Counter(r["provider"] for r in rows)),
            limitation={
                "merchant_dictionary": (
                    "Merchant labels lack transaction context: dictionary task only; "
                    "no inferred direction/amount. Primary gold used; alternatives not substituted."
                ),
                "head_validation": (
                    "Previously used selection validation; strict historical parser; "
                    "head-only, no provider context or seed reselection."
                ),
                "head_and_t5": (
                    "Legacy risk data lacks provider/category: raw head and historical "
                    "head+T5 only; complete waterfall unsupported."
                ),
                "v4_context_join": (
                    "Provider/category recovered by exact input join to hash-verified "
                    "gold_v4_eyeball; 1:1 output count required."
                ),
                "transactions": (
                    "Original provider/native values, including blanks, retained; "
                    "Plaid serving and mixed-provider research views reported separately."
                ),
            }[task],
        )
        diagnostics.extend(output)
        save(args.output / "summary.json", report)
    if source_hashes(mono, research) != initial_hashes or any(
        sha256(p.read_bytes()) != harness_hashes[p.name] for p in harness_paths
    ):
        raise ValueError("source changed during evaluation; rerun both sides")
    for item in datasets.values():
        if item["status"] not in {"passed", "excluded_confirmation"}:
            raise ValueError("required dataset did not finish")
    private_rows = args.output / "rows.jsonl"
    private_rows.write_bytes(b"".join(canonical_json(r) + b"\n" for r in diagnostics))
    os.chmod(private_rows, 0o600)
    report["private_rows_sha256"] = sha256(private_rows.read_bytes())
    report["private_rows_n"] = len(diagnostics)
    report["independent_validation"] = verify_metrics(report, diagnostics, research)
    report["comparison"] = {"status": "not_applicable_baseline"}
    if args.baseline:
        baseline = strict_json_loads((args.baseline / "summary.json").read_bytes())
        prior_raw = (args.baseline / "rows.jsonl").read_bytes()
        if baseline["status"] != "passed" or sha256(prior_raw) != baseline["private_rows_sha256"]:
            raise ValueError("baseline incomplete or private rows corrupted")
        if baseline["harness_sha256"] != harness_hashes or baseline["general_mapping"] != general:
            raise ValueError("evaluation definition changed: rerun baseline with this harness")
        prior = [strict_json_loads(line) for line in prior_raw.splitlines()]
        comparison, changed = compare_runs(prior, diagnostics, general)
        comparison["status"] = "compared_review_required"
        report["comparison"] = comparison
        changed_path = args.output / "changed_rows.jsonl"
        changed_path.write_bytes(b"".join(canonical_json(r) + b"\n" for r in changed))
        os.chmod(changed_path, 0o600)
        report["comparison"]["private_changed_rows_sha256"] = sha256(changed_path.read_bytes())
        report["comparison"]["baseline_summary_sha256"] = sha256(
            (args.baseline / "summary.json").read_bytes()
        )
    report["status"] = "passed"
    report["completed_at"] = datetime.now(UTC).isoformat()
    save(args.output / "summary.json", report)
    save(
        args.output / "validation.json",
        report["independent_validation"]
        | {"summary_sha256": sha256((args.output / "summary.json").read_bytes())},
    )
    (args.output / "README.md").write_text(render_report(report))
    print(
        f"Complete: {len(inventory['tasks'])} repeatable datasets; "
        f"{len(report['evaluations'])} scored views",
        flush=True,
    )


if __name__ == "__main__":
    main()
