#!/usr/bin/env python3
"""LODO evaluation runner.

Runs the LODO evaluation suite and generates a markdown coverage report.

Usage:
    python scripts/run_lodo_eval.py [--output docs/security/lodo-report.md]
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from spellbook.security.rules import (
    ESCALATION_RULES,
    EXFILTRATION_RULES,
    INJECTION_RULES,
    OBFUSCATION_RULES,
    check_patterns,
)

DATASETS_DIR = Path(__file__).parent.parent / "tests" / "test_security" / "datasets"
ALL_RULE_SETS = [
    ("injection", INJECTION_RULES),
    ("exfiltration", EXFILTRATION_RULES),
    ("escalation", ESCALATION_RULES),
    ("obfuscation", OBFUSCATION_RULES),
]


def load_datasets() -> dict[str, dict]:
    datasets = {}
    for f in sorted(DATASETS_DIR.glob("*.json")):
        datasets[f.stem] = json.loads(f.read_text())
    return datasets


def evaluate(datasets: dict[str, dict]) -> dict:
    results = {}
    for ds_name, ds in datasets.items():
        ds_results = {
            "total_samples": len(ds["samples"]),
            "injection_samples": 0,
            "benign_samples": 0,
            "true_positives": 0,
            "false_negatives": 0,
            "false_positives": 0,
            "true_negatives": 0,
            "by_rule_set": {},
            "missed_samples": [],
        }
        for sample in ds["samples"]:
            is_injection = sample.get("label") == "injection"
            if is_injection:
                ds_results["injection_samples"] += 1
            else:
                ds_results["benign_samples"] += 1

            all_findings = []
            for rule_label, rule_set in ALL_RULE_SETS:
                findings = check_patterns(sample["text"], rule_set, "standard")
                if rule_label not in ds_results["by_rule_set"]:
                    ds_results["by_rule_set"][rule_label] = {
                        "detected": 0,
                        "total_injection": 0,
                    }
                if is_injection:
                    ds_results["by_rule_set"][rule_label]["total_injection"] += 1
                    if findings:
                        ds_results["by_rule_set"][rule_label]["detected"] += 1
                all_findings.extend(findings)

            detected = len(all_findings) > 0
            if is_injection and detected:
                ds_results["true_positives"] += 1
            elif is_injection and not detected:
                ds_results["false_negatives"] += 1
                ds_results["missed_samples"].append(sample["text"][:100])
            elif not is_injection and detected:
                ds_results["false_positives"] += 1
            else:
                ds_results["true_negatives"] += 1

        results[ds_name] = ds_results
    return results


def generate_report(results: dict) -> str:
    lines = ["# LODO Evaluation Report\n"]
    lines.append(
        f"**Generated:** {datetime.now(tz=timezone.utc).isoformat()}\n"
    )

    for ds_name, r in results.items():
        lines.append(f"\n## {ds_name}\n")
        total_inj = r["injection_samples"]
        tp = r["true_positives"]
        fn = r["false_negatives"]
        fp = r["false_positives"]

        det_rate = tp / total_inj if total_inj > 0 else 0
        fp_rate = fp / r["benign_samples"] if r["benign_samples"] > 0 else 0

        lines.append(f"- Total samples: {r['total_samples']}")
        lines.append(f"- Detection rate: {det_rate:.1%} ({tp}/{total_inj})")
        lines.append(
            f"- False positive rate: {fp_rate:.1%} ({fp}/{r['benign_samples']})"
        )
        lines.append(f"- Missed: {fn}\n")

        if r["by_rule_set"]:
            lines.append("| Rule Set | Detected | Total | Rate |")
            lines.append("|----------|----------|-------|------|")
            for rs_name, rs_data in r["by_rule_set"].items():
                total = rs_data["total_injection"]
                det = rs_data["detected"]
                rate = det / total if total > 0 else 0
                lines.append(f"| {rs_name} | {det} | {total} | {rate:.1%} |")

        if r["missed_samples"]:
            lines.append(f"\n### Missed Samples ({len(r['missed_samples'])})\n")
            for s in r["missed_samples"][:10]:
                lines.append(f"- `{s}`")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Run LODO evaluation")
    parser.add_argument("--output", default="docs/security/lodo-report.md")
    args = parser.parse_args()

    datasets = load_datasets()
    if not datasets:
        print("No datasets found in", DATASETS_DIR)
        sys.exit(1)

    results = evaluate(datasets)
    report = generate_report(results)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report)
    print(f"Report written to {output_path}")


if __name__ == "__main__":
    main()
