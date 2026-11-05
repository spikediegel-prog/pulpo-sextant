# Sextant

Sextant is a standalone, standard-library Python package for validating and
replaying bounded workload-observation documents. It reports accuracy and
calibrated drift as **recorded signals only**. It does not establish source
authenticity, correctness, causality, or event completeness, and it has no
connection to canonical application state.

## Install and use

The package has no third-party runtime dependencies. From a checkout, install
it with pip (Python 3.11 or later):

```console
pip install .
```

Then import the public API with Python:

```python
from sextant import load_sextant_observation, replay

observation = load_sextant_observation("observation.json")
report = replay(observation)
print(report.drift.status, report.accuracy.accuracy)
```

A worked example lives in `examples/observation.json`. Replay it with the
tiny demo, which prints accuracy and drift lines in the format from
[docs/SEXTANT.md](docs/SEXTANT.md):

```console
python3 examples/demo.py
```

Run the test suite with:

```console
python -m unittest discover -s tests -v
```

## Contract

The versioned document schema is `pulpo.sextant-observation.v1`. The strict
parser rejects unknown or missing fields, malformed values, duplicate JSON
keys, invalid ordering, and event batches larger than 16 events. A snapshot
document is limited to 16 KiB. See [docs/SEXTANT.md](docs/SEXTANT.md) for
field semantics, trust limitations, and the host integration boundary.

The `sextant` package is offline and read-only. It has no database, network,
filesystem writer, credentials, signing key, or authority interface. Its
loader reads a local JSON file only; it does not authenticate the file or
verify referenced checkpoints/evidence. In particular, a structurally valid
substitution remains undetectable without an independently trusted
authenticator.

The existing Pulpo Control Center Tk page is host-specific and is not included
here. Pulpo-Preview owns the Tk page; this package supplies replay results
only. A host may adapt the pure replay results for display, but must keep the
observation provider, UI, and canonical-state authority separate. An
investigation signal is not proof of cause or correctness.
