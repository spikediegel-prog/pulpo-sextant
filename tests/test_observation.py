import json
import math
from dataclasses import asdict, replace
from pathlib import Path
import tempfile
import time
import unittest

from sextant import (
    MAX_DOCUMENT_BYTES,
    SCHEMA,
    SextantCalibration,
    SextantEvent,
    SextantObservation,
    SextantReplayGuard,
    freshness,
    load_sextant_observation,
    replay,
)


class SextantReplayTests(unittest.TestCase):
    def setUp(self):
        self.calibration = SextantCalibration(
            calibration_id="cal-v1",
            version="1",
            workload_id="fixture-workload",
            metric_id="latency-ms",
            baseline_workload_version="workload-1",
            baseline_model_version="model-1",
            baseline_sample_count=100,
            baseline_mean=10.0,
            baseline_stddev=1.0,
            investigate_z_threshold=2.0,
            checkpoint_ref="fixture-checkpoint",
            evidence_ref="a" * 64,
        )
        self.events = tuple(
            SextantEvent(
                sequence=index,
                timestamp_ns=index * 1_000_000_000,
                workload_id="fixture-workload",
                workload_version="workload-2",
                model_version="model-2",
                metric_id="latency-ms",
                metric_value=value,
                checkpoint_ref="fixture-checkpoint",
                evidence_ref=hex(index)[2:].rjust(64, "0"),
                reviewed_correct=reviewed,
            )
            for index, value, reviewed in (
                (1, 13.0, True),
                (2, 13.0, True),
                (3, 13.0, False),
                (4, 13.0, None),
            )
        )

    def observation(self, events=None, **changes):
        rows = self.events if events is None else tuple(events)
        observation = SextantObservation(
            source_id="b" * 32,
            observed_at_ns=time.time_ns(),
            first_sequence=rows[0].sequence,
            event_count=len(rows),
            calibration=self.calibration,
            events=rows,
        )
        return replace(observation, **changes)

    def document(self, observation=None):
        observation = observation or self.observation()
        return {
            "schema": SCHEMA,
            "source_id": observation.source_id,
            "observed_at_ns": observation.observed_at_ns,
            "first_sequence": observation.first_sequence,
            "event_count": observation.event_count,
            "calibration": asdict(observation.calibration),
            "events": [asdict(event) for event in observation.events],
        }

    def test_controlled_drift_reports_an_investigation_signal(self):
        result = replay(self.observation())
        self.assertEqual("Investigate", result.drift.status)
        self.assertEqual(4, result.drift.sample_count)
        self.assertEqual(100, result.drift.baseline_sample_count)
        self.assertEqual(13.0, result.drift.observed_mean)
        self.assertAlmostEqual(0.1, result.drift.standard_error)
        self.assertAlmostEqual(30.0, result.drift.standardized_delta)
        self.assertEqual("Recorded", result.drift.classification)
        self.assertEqual("Recorded", result.accuracy.classification)
        self.assertEqual(3, result.accuracy.reviewed_sample_count)
        self.assertEqual(2, result.accuracy.correct_count)
        self.assertAlmostEqual(2 / 3, result.accuracy.accuracy)
        self.assertEqual(5, len(result.checkpoint_refs))
        self.assertEqual(5, len(result.evidence_refs))

    def test_baseline_like_samples_remain_below_threshold(self):
        events = tuple(
            replace(event, metric_value=value)
            for event, value in zip(self.events, (10.0, 10.1, 9.9, 10.0))
        )
        result = replay(self.observation(events))
        self.assertEqual("Below investigate threshold", result.drift.status)

    def test_unreviewed_outcomes_are_excluded_and_small_batches_are_unknown(self):
        events = tuple(replace(event, reviewed_correct=None) for event in self.events)
        result = replay(self.observation(events))
        self.assertEqual(0, result.accuracy.reviewed_sample_count)
        self.assertIsNone(result.accuracy.accuracy)
        one = replay(self.observation(self.events[:1]))
        self.assertEqual("Unknown", one.drift.status)
        self.assertIsNone(one.drift.standard_error)

    def test_zero_uncertainty_remains_unknown(self):
        calibration = replace(self.calibration, baseline_stddev=0.0, baseline_mean=13.0)
        events = tuple(replace(event, metric_value=13.0) for event in self.events)
        observation = replace(self.observation(events), calibration=calibration)
        result = replay(observation)
        self.assertEqual("Unknown", result.drift.status)
        self.assertEqual(0.0, result.drift.standard_error)
        self.assertIsNone(result.drift.standardized_delta)

    def test_extreme_finite_measurements_keep_finite_outputs(self):
        calibration = replace(self.calibration, baseline_mean=-1e100, baseline_stddev=1e100)
        events = tuple(replace(event, metric_value=1e100) for event in self.events)
        result = replay(replace(self.observation(events), calibration=calibration))
        self.assertEqual("Investigate", result.drift.status)
        self.assertTrue(math.isfinite(result.drift.standard_error))
        self.assertTrue(math.isfinite(result.drift.standardized_delta))

    def test_batch_sequence_time_scope_and_cohort_are_validated(self):
        with self.assertRaisesRegex(ValueError, "sequence_gap_or_reordering"):
            self.observation((self.events[0], self.events[2], self.events[3]))
        reordered = (self.events[0], replace(self.events[1], timestamp_ns=0), *self.events[2:])
        with self.assertRaisesRegex(ValueError, "event_timestamp_reordered"):
            self.observation(reordered)
        with self.assertRaisesRegex(ValueError, "mixed_event_cohort"):
            self.observation((self.events[0], replace(self.events[1], model_version="other")))
        with self.assertRaisesRegex(ValueError, "event_calibration_scope_mismatch"):
            self.observation((replace(self.events[0], metric_id="other"),))

    def test_invalid_values_and_references_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid_event_evidence_ref"):
            replace(self.events[0], evidence_ref="z" * 64)
        with self.assertRaisesRegex(ValueError, "invalid_metric_value"):
            replace(self.events[0], metric_value=float("nan"))
        with self.assertRaisesRegex(ValueError, "invalid_metric_value"):
            replace(self.events[0], metric_value=10**1000)
        with self.assertRaisesRegex(ValueError, "invalid_reviewed_outcome"):
            replace(self.events[0], reviewed_correct=1)

    def test_strict_versioned_document_parser(self):
        expected = self.observation()
        document = self.document(expected)
        self.assertEqual(expected, SextantObservation.from_dict(document))
        with self.assertRaisesRegex(ValueError, "fields_invalid"):
            SextantObservation.from_dict({**document, "p3_verified": True})
        with self.assertRaisesRegex(ValueError, "unsupported_sextant_schema"):
            SextantObservation.from_dict({**document, "schema": "pulpo.sextant-observation.v0"})

    def test_local_loader_rejects_malformed_duplicate_and_oversized_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "observation.json"
            expected = self.observation()
            document = self.document(expected)
            path.write_text(json.dumps(document), encoding="utf-8")
            self.assertEqual(expected, load_sextant_observation(path))
            path.write_text("{malformed", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid_sextant_document"):
                load_sextant_observation(path)
            path.write_text(
                json.dumps(document) + " " * MAX_DOCUMENT_BYTES,
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "too_large"):
                load_sextant_observation(path)
            duplicate = json.dumps(document)[:-1] + ',"schema":"pulpo.sextant-observation.v1"}'
            path.write_text(duplicate, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate_json_key"):
                load_sextant_observation(path)

    def test_valid_field_substitution_is_not_authenticated(self):
        document = self.document()
        document["events"][0]["metric_value"] = 9999.0
        observation = SextantObservation.from_dict(document)
        self.assertEqual(9999.0, observation.events[0].metric_value)

    def test_freshness_and_ephemeral_replay_guard(self):
        observation = self.observation()
        self.assertEqual("recent source timestamp", freshness(observation, observation.observed_at_ns))
        self.assertEqual("stale", freshness(observation, observation.observed_at_ns + 30_000_000_001))
        self.assertEqual("clock mismatch", freshness(observation, observation.observed_at_ns - 5_000_000_001))
        guard = SextantReplayGuard()
        first = self.observation(self.events[:2])
        guard.accept(first)
        with self.assertRaisesRegex(ValueError, "replay_or_overlap"):
            guard.accept(first)
        guard.reset()
        self.assertTrue(guard.accept(first))


if __name__ == "__main__":
    unittest.main()
