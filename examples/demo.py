"""Tiny Sextant demo: replay examples/observation.json and print the signals.

Run from the repository root:

    python3 examples/demo.py

The printed lines use the format from docs/SEXTANT.md. They are recorded
signals only, not proof of cause, correctness, or source authenticity.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sextant import load_sextant_observation, replay


def main() -> None:
    path = Path(__file__).resolve().parent / "observation.json"
    report = replay(load_sextant_observation(path))
    accuracy = report.accuracy
    drift = report.drift
    if accuracy.accuracy is not None:
        print(
            f"{accuracy.correct_count}/{accuracy.reviewed_sample_count} generated "
            f"labels correct \u00b7 Wilson 95% CI: "
            f"{accuracy.wilson_95_low:.0%}\u2013{accuracy.wilson_95_high:.0%}"
        )
    else:
        print("No reviewed outcomes in this batch.")
    if drift.observed_mean is not None and drift.standardized_delta is not None:
        print(
            f"Mean: {drift.observed_mean:.1f} ms \u00b7 Baseline: "
            f"{drift.baseline_mean:.1f} ms \u00b7 z-score: "
            f"{drift.standardized_delta:.2f} (threshold: "
            f"{drift.investigate_z_threshold:.1f}) \u00b7 n={drift.sample_count}"
        )
    print(f"Drift status: {drift.status} \u00b7 freshness: {report.freshness}")


if __name__ == "__main__":
    main()
