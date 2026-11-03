# Sextant observation and replay contract

Sextant is a pure, offline consumer for bounded workload observation
documents. Its schema identifier is `pulpo.sextant-observation.v1`; the
package module is `sextant.observation`. It requires only the Python standard
library and does not import the Pulpo application.

## Document shape

The top-level object contains exactly `schema`, `source_id`, `observed_at_ns`,
`first_sequence`, `event_count`, `calibration`, and `events`. A calibration is
versioned and scoped to one workload and numeric metric. It carries the
baseline workload/model versions, sample count, mean and sample standard
deviation, an investigate-only threshold, and opaque checkpoint/evidence
references. Each event records its contiguous sequence and timestamp, workload
and model versions, metric value, optional reviewed-correct Boolean,
checkpoint reference, and evidence reference.

The parser rejects unknown/missing fields, duplicate JSON keys, malformed or
non-finite numbers, invalid references, timestamp reordering, scope mismatch,
mixed workload/model cohorts, and gaps or reordering inside a batch. A batch
contains 1–16 events and its JSON file is capped at 16 KiB. These limits bound
local parsing and do not establish completeness beyond the supplied batch.

## Signals and interpretation

Accuracy counts only events where `reviewed_correct` is explicitly Boolean;
unreviewed outcomes are excluded. It reports the fraction of reviewed outcomes
marked correct and a Wilson 95% interval. The interval quantifies binomial
sampling uncertainty only under representative/independent-sample assumptions;
it does not establish label quality, source authenticity, or population
accuracy.

Drift compares the batch's metric values against the stated baseline and
reports the observed mean, combined standard error, and standardized mean
delta. Fewer than two observations, zero uncertainty, or non-finite results
remain `Unknown`. Crossing the configured absolute threshold is labeled
`Investigate`; otherwise the result is `Below investigate threshold`. This is
not a p-value, correctness assessment, cause, or automatic action. The
uncertainty estimate assumes comparable independent observations in the same
units; the contract does not validate those assumptions.

`freshness()` classifies the producer-supplied timestamp as recent, stale, or
clock-mismatched, and `SextantReplayGuard` detects duplicate, overlapping, and
gapped batches during one in-memory viewing session. Neither authenticates the
producer or clock; the replay guard is disposable UI bookkeeping, not a
durable replay ledger.

## Trust and integration boundary

The parser validates structure and ordering, not provenance or truth.
`source_id` is a producer-supplied label. References are locators: this package
does not verify referenced checkpoints, evidence, calibration approval, or
human review. A valid-field substitution is not detectable. No signatures,
MACs, transport identity, or completeness proof are provided. A structurally
valid report remains `Recorded`, not `Verified`.

The package reads a local JSON file but has no writer, database, network
transport, canonical state handle, credential, policy, executor, or authority
path. It must not be used to mutate canonical state. The Tk presentation in
Pulpo-Preview depends on its Control Center theme and host page interface and
is intentionally outside this standalone package. A host adapter may render
replay values but must not convert an investigation signal into a claim of
cause, correctness, cryptographic verification, or source authenticity.
