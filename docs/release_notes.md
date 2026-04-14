# ICD-11 Foundation — Release Notes

## mondo-source-ingest-update (2026-04-14)

Second pass using **mondo-source-ingest-update**: confirmed Phases 1–9 against the base skill; `docs/plan.md` intake and Phase 4 mappings unchanged (upstream behaviour unchanged). **Phase 2:** removed unused `config/` stub; **Phase 8:** CI path filters updated (`build.yml`). See [`docs/pipeline_incidents.md`](pipeline_incidents.md).

| Phase 9 check | Result |
|---------------|--------|
| `linkml-validate` | Pass (2026-04-14; 71,565 terms) |
| `scripts/verify.py` | Pass (2026-04-14; 0 broken parent refs) |

## mondo-source-ingest compliance (documented 2026-04-14)

Repository behaviour was aligned with **mondo-source-ingest** (Phase 1 intake, Phase 4
source-analysis decisions, Phase 8 release policy, Phase 9 verification):

| Item | Status |
|------|--------|
| Intake (location, format, auth, versioning) | Documented in [`docs/plan.md`](plan.md) § Intake |
| Phase 4 mappings (labels through IRI scheme; 4.6 `skos_exact_match` empty — no API xrefs) | Documented in [`docs/plan.md`](plan.md) § Source analysis |
| Phase 4.8 (SPARQL/ROBOT) | N/A (non-OWL source) |
| `just build` includes `verify` before `data2owl` | Yes — see `justfile` |
| Release workflow | `workflow_dispatch` only — [`docs/plan.md`](plan.md) § Release automation |

**Phase 9 commands** (run after a full `just build` or `just extract` with existing raw JSON):

```bash
just validate
just verify
# or: just check
```

## 2026-01 (acquired 2026-04-04)

| Field                     | Value |
|---------------------------|-------|
| Official WHO release id   | `2026-01` |
| Acquire date              | 2026-04-04 |
| Total entities (raw JSON) | 71,565 |
| Terms with label          | 71,565 |
| Terms skipped (no label)  | 0 |
| Terms with definition     | 17,963 |
| Terms with exact synonyms | 22,327 |
| Terms with narrow synonyms| 1,949 |
| Terms with related synonyms | 3,409 |
| Terms with parents        | 71,563 |
| Terms with empty `parents` (roots in graph) | 2 |
| linkml-validate result    | Pass (no issues) |
| data2owl result           | **Fail** — `linkml-owl` / `funowl` uses rdflib N3 parsing for literals; some ICD-11 strings contain `^` and trigger `AssertionError: Quote expected in string`. No `icd11foundation.linkml.owl` produced. See `docs/report.md` and `docs/pipeline_incidents.md`. |

## Verification

Full checklist (automated vs manual):

| Check | How | Result |
|-------|-----|--------|
| Title and version present | `scripts/verify.py` | Pass |
| No duplicate term IDs | `verify.py` | Pass |
| `label` non-null for all terms | `verify.py` | Pass |
| All `parents` refs resolve | `verify.py` | Pass (0 broken) |
| `version` matches upstream release identifier | `verify.py` with `--raw-json` (uses `release_id` as expected) | Pass (`2026-01`) |
| `linkml-validate` exits 0 | `just validate` | Pass |
| OWL artefact loads in ROBOT / Protégé | manual | **N/A** — no `.linkml.owl` produced (`data2owl` failed) |
| `robot diff` vs mondo-ingest reference | manual | N/A (not migrating OWL in this release) |

**Commands**

```bash
just validate
just verify
# or: just check   # validate + verify
```

`verify.py` also cross-checks term count vs `tmp/icd11foundation_raw.json` when `--raw-json` is passed (API-acquire sources).

**Manual spot-checks (optional)**

- [ ] Random spot-check: 5 CURIE IDs in the WHO browser — https://icd.who.int/browse/2026-01/foundation/en
- [ ] Random spot-check: 5 definitions verbatim vs API `tmp/cache/.../response.json`
