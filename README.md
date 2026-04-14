# icd11foundation

Preprocessed ICD-11 Foundation (WHO ICD API) for Mondo source ingest — LinkML YAML plus optional linkml-owl output.

## Setup

1. Register at [WHO ICD API](https://icd.who.int/icdapi) for OAuth2 client credentials.
2. Copy `env/.env.example` → `env/.env` and set `CLIENT_ID` and `CLIENT_SECRET`.
3. Install dependencies: `uv sync`

## Run

```bash
just acquire       # BFS over Foundation API (~hours first run; cached under tmp/cache/)
just extract       # tmp/icd11foundation_raw.json → icd11foundation.linkml.yaml
just validate      # linkml-validate
just verify        # scripts/verify.py — structure, parents, raw-json cross-check
just check         # validate + verify (recommended before release)
just data2owl      # may fail on very large data — see docs/report.md
just build         # acquire → extract → validate → data2owl
just iterate       # extract → validate (skip acquire)
```

## Outputs

| File | Description |
|------|-------------|
| `icd11foundation.linkml.yaml` | Primary artefact for Mondo ingest |
| `icd11foundation.linkml.owl` | linkml-owl–derived OWL (when `data2owl` succeeds) |

## Docs

| Doc | Contents |
|-----|----------|
| [`docs/plan.md`](docs/plan.md) | Pipeline architecture, field mappings, ID scheme, intake (Phase 1), source analysis (Phase 4), release policy (Phase 8) |
| [`docs/release_notes.md`](docs/release_notes.md) | Ontology stats and Phase 9 verification results per release |
| [`docs/pipeline_incidents.md`](docs/pipeline_incidents.md) | Pipeline incidents: errors, deviations, resolutions |
| [`docs/report.md`](docs/report.md) | Known tool limitations (funowl / data2owl) |

## CI secrets

GitHub Actions expects repository secrets `CLIENT_ID` and `CLIENT_SECRET` (same as `env/.env`).
