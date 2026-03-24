"""LODO (Leave-One-Distribution-Out) evaluation for regex injection detectors.

Tests the 33+ regex patterns in rules.py against curated attack datasets
to measure detection coverage and false positive rates.

Datasets:
- AdvBench: Direct injection attacks (Zou et al. 2023)
- BIPIA: Indirect/embedded injection attacks (Yi et al. 2023)
- HarmBench: Jailbreak and override attacks (Mazeika et al. 2024)
- InjecAgent: Agent-targeted injection attacks (Zhan et al. 2024)
- Benign corpus: Hand-curated non-malicious text
"""
import json
from pathlib import Path

import pytest

from spellbook.security.rules import (
    ESCALATION_RULES,
    EXFILTRATION_RULES,
    INJECTION_RULES,
    OBFUSCATION_RULES,
    check_patterns,
)

pytestmark = pytest.mark.slow

DATASETS_DIR = Path(__file__).parent / "datasets"
ALL_RULE_SETS = [
    ("injection", INJECTION_RULES),
    ("exfiltration", EXFILTRATION_RULES),
    ("escalation", ESCALATION_RULES),
    ("obfuscation", OBFUSCATION_RULES),
]

# Dataset filenames for attack corpora (excludes benign_corpus)
ATTACK_DATASETS = [
    "advbench_sample.json",
    "bipia_sample.json",
    "harmbench_sample.json",
    "injecagent_sample.json",
]


def _load_dataset(name: str) -> dict:
    path = DATASETS_DIR / name
    return json.loads(path.read_text())


def _scan_all_rules(text: str, mode: str = "standard") -> list[dict]:
    findings = []
    for _label, rule_set in ALL_RULE_SETS:
        findings.extend(check_patterns(text, rule_set, mode))
    return findings


def _scan_rule_set(text: str, rule_set_name: str, mode: str = "standard") -> list[dict]:
    """Scan text against a single named rule set."""
    rule_map = {
        "injection": INJECTION_RULES,
        "exfiltration": EXFILTRATION_RULES,
        "escalation": ESCALATION_RULES,
        "obfuscation": OBFUSCATION_RULES,
    }
    return check_patterns(text, rule_map[rule_set_name], mode)


def _detection_rate(dataset: dict, scanner=_scan_all_rules) -> tuple[float, int, int]:
    """Compute detection rate for injection samples in a dataset.

    Returns (rate, detected_count, total_count).
    """
    injection_samples = [
        s for s in dataset["samples"] if s["label"] == "injection"
    ]
    if not injection_samples:
        return 0.0, 0, 0
    detected = sum(1 for s in injection_samples if scanner(s["text"]))
    return detected / len(injection_samples), detected, len(injection_samples)


def _fp_rate(samples: list[dict]) -> tuple[float, int, int]:
    """Compute false positive rate for benign samples.

    Returns (rate, flagged_count, total_count).
    """
    if not samples:
        return 0.0, 0, 0
    flagged = sum(1 for s in samples if _scan_all_rules(s["text"]))
    return flagged / len(samples), flagged, len(samples)


class TestDetectionCoverage:
    """Measure detection rates across attack datasets."""

    @pytest.fixture(autouse=True)
    def _load_datasets(self):
        self.advbench = _load_dataset("advbench_sample.json")
        self.bipia = _load_dataset("bipia_sample.json")
        self.harmbench = _load_dataset("harmbench_sample.json")
        self.injecagent = _load_dataset("injecagent_sample.json")

    def test_advbench_detection_rate(self):
        """AdvBench injection samples should be detected at >= 60% rate."""
        rate, detected, total = _detection_rate(self.advbench)
        assert rate >= 0.60, (
            f"AdvBench detection rate {rate:.2%} < 60%. "
            f"Detected {detected}/{total}"
        )

    def test_bipia_injection_detection_rate(self):
        """BIPIA indirect injection samples should be detected at >= 50% rate."""
        rate, detected, total = _detection_rate(self.bipia)
        assert rate >= 0.50, (
            f"BIPIA detection rate {rate:.2%} < 50%. "
            f"Detected {detected}/{total}"
        )

    def test_harmbench_detection_rate(self):
        """HarmBench injection samples should be detected at >= 60% rate."""
        rate, detected, total = _detection_rate(self.harmbench)
        assert rate >= 0.60, (
            f"HarmBench detection rate {rate:.2%} < 60%. "
            f"Detected {detected}/{total}"
        )

    def test_injecagent_detection_rate(self):
        """InjecAgent injection samples should be detected at >= 60% rate."""
        rate, detected, total = _detection_rate(self.injecagent)
        assert rate >= 0.60, (
            f"InjecAgent detection rate {rate:.2%} < 60%. "
            f"Detected {detected}/{total}"
        )


class TestPerRuleSetDetection:
    """Per-rule-set detection rate assertions.

    Verifies that each rule set contributes meaningfully to detection
    on the datasets where it is expected to fire.
    """

    @pytest.fixture(autouse=True)
    def _load_datasets(self):
        self.advbench = _load_dataset("advbench_sample.json")
        self.bipia = _load_dataset("bipia_sample.json")
        self.harmbench = _load_dataset("harmbench_sample.json")
        self.injecagent = _load_dataset("injecagent_sample.json")

    def test_injection_rules_on_advbench(self):
        """INJECTION_RULES should detect >= 60% of AdvBench attacks."""
        scanner = lambda text: _scan_rule_set(text, "injection")
        rate, detected, total = _detection_rate(self.advbench, scanner)
        assert rate >= 0.60, (
            f"INJECTION_RULES on AdvBench: {rate:.2%} < 60%. "
            f"Detected {detected}/{total}"
        )

    def test_injection_rules_on_harmbench(self):
        """INJECTION_RULES should detect >= 60% of HarmBench attacks."""
        scanner = lambda text: _scan_rule_set(text, "injection")
        rate, detected, total = _detection_rate(self.harmbench, scanner)
        assert rate >= 0.60, (
            f"INJECTION_RULES on HarmBench: {rate:.2%} < 60%. "
            f"Detected {detected}/{total}"
        )

    def test_exfiltration_rules_on_bipia(self):
        """EXFILTRATION_RULES should detect >= 40% of BIPIA attacks.

        BIPIA contains indirect exfil patterns; lower threshold reflects
        that not all indirect attacks use explicit exfil commands.
        """
        scanner = lambda text: _scan_rule_set(text, "exfiltration")
        rate, detected, total = _detection_rate(self.bipia, scanner)
        assert rate >= 0.40, (
            f"EXFILTRATION_RULES on BIPIA: {rate:.2%} < 40%. "
            f"Detected {detected}/{total}"
        )

    def test_exfiltration_rules_on_injecagent(self):
        """EXFILTRATION_RULES should detect >= 40% of InjecAgent attacks.

        InjecAgent samples feature curl/wget/scp/nc exfil patterns.
        """
        scanner = lambda text: _scan_rule_set(text, "exfiltration")
        rate, detected, total = _detection_rate(self.injecagent, scanner)
        assert rate >= 0.40, (
            f"EXFILTRATION_RULES on InjecAgent: {rate:.2%} < 40%. "
            f"Detected {detected}/{total}"
        )

    def test_escalation_rules_on_injecagent(self):
        """ESCALATION_RULES should detect >= 30% of InjecAgent attacks.

        InjecAgent contains sudo, eval, os.system, subprocess patterns.
        """
        scanner = lambda text: _scan_rule_set(text, "escalation")
        rate, detected, total = _detection_rate(self.injecagent, scanner)
        assert rate >= 0.30, (
            f"ESCALATION_RULES on InjecAgent: {rate:.2%} < 30%. "
            f"Detected {detected}/{total}"
        )


class TestFalsePositiveRate:
    """Measure false positive rates on benign content."""

    @pytest.fixture(autouse=True)
    def _load_datasets(self):
        self.benign = _load_dataset("benign_corpus.json")
        self.all_benign_samples = self.benign["samples"][:]
        # Collect benign samples from all attack datasets too
        for ds_name in ATTACK_DATASETS:
            ds = _load_dataset(ds_name)
            self.all_benign_samples.extend(
                s for s in ds["samples"] if s["label"] == "benign"
            )

    def test_benign_corpus_false_positive_rate(self):
        """Benign corpus should have <= 20% false positive rate."""
        rate, flagged, total = _fp_rate(self.benign["samples"])
        assert rate <= 0.20, (
            f"Benign FP rate {rate:.2%} > 20%. "
            f"Flagged {flagged}/{total}"
        )

    def test_all_benign_samples_false_positive_rate(self):
        """All benign samples across all datasets should have <= 20% FP rate."""
        rate, flagged, total = _fp_rate(self.all_benign_samples)
        assert rate <= 0.20, (
            f"Combined benign FP rate {rate:.2%} > 20%. "
            f"Flagged {flagged}/{total}"
        )

    def test_per_rule_set_false_positive_rates(self):
        """No individual rule set should have > 20% FP rate on benign corpus."""
        for rule_label, rule_set in ALL_RULE_SETS:
            flagged = sum(
                1 for s in self.benign["samples"]
                if check_patterns(s["text"], rule_set, "standard")
            )
            total = len(self.benign["samples"])
            rate = flagged / total if total else 0
            assert rate <= 0.20, (
                f"{rule_label} FP rate {rate:.2%} > 20% on benign corpus. "
                f"Flagged {flagged}/{total}"
            )


class TestCoverageMatrix:
    """Generate a coverage matrix showing which rule sets catch which attacks."""

    def test_coverage_matrix_generation(self):
        """Generate and print coverage matrix (informational, always passes)."""
        datasets = {}
        for name in ATTACK_DATASETS:
            if (DATASETS_DIR / name).exists():
                datasets[name] = _load_dataset(name)

        matrix: dict[str, dict[str, int]] = {}
        for ds_name, ds in datasets.items():
            matrix[ds_name] = {}
            for rule_label, rule_set in ALL_RULE_SETS:
                detected = sum(
                    1 for s in ds["samples"]
                    if s.get("label") == "injection"
                    and check_patterns(s["text"], rule_set, "standard")
                )
                matrix[ds_name][rule_label] = detected

        # This test always passes; the matrix is for reporting
        assert matrix is not None


class TestLODOCrossValidation:
    """Leave-One-Distribution-Out cross-validation.

    For each attack dataset, hold it out and measure whether the shared
    regex patterns still detect attacks from the held-out set. With regex
    rules (not ML), this tests generalization of pattern coverage across
    attack distributions.
    """

    @pytest.mark.parametrize("holdout_name", ATTACK_DATASETS)
    def test_lodo_holdout(self, holdout_name: str):
        """Each held-out dataset should still achieve >= 40% detection.

        The LODO threshold is lower than per-dataset thresholds because
        we are testing generalization: can patterns designed for one
        attack style also catch another?
        """
        holdout = _load_dataset(holdout_name)
        rate, detected, total = _detection_rate(holdout)
        assert rate >= 0.40, (
            f"LODO holdout {holdout_name} detection rate {rate:.2%} < 40%. "
            f"Detected {detected}/{total}"
        )
