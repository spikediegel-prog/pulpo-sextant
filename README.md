# Sextant

Sextant watches how hard your system is working and tells you if its readings are drifting.

It only watches — it never decides or changes anything. It reports what it saw, so you can check it yourself. It can't tell you whether the readings were true in the first place, or what caused them — only whether they match and whether they've drifted.

Sextant is a small Python package for checking workload-observation records. It reports accuracy and drift as recorded signals only.

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
