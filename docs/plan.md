# ICD-11 Foundation — Pipeline Plan

Architecture background and the mondo-source-ingest **source format decision tree** are in
the skill reference
[`plan.md`](https://github.com/monarch-initiative/mondo-ingest/blob/master/.cursor/skills/mondo-source-ingest/plan.md)
(monarch-initiative/mondo-ingest). This file is the **source-specific** contract for ICD-11
Foundation.

## Source

| Field         | Value                                            |
|---------------|--------------------------------------------------|
| Name          | ICD-11 Foundation                                |
| Publisher     | World Health Organization (WHO)                  |
| Official API  | https://id.who.int/icd/entity                    |
| Auth          | WHO OAuth2 client credentials (`CLIENT_ID`, `CLIENT_SECRET`) |
| Format        | JSON-LD (application/json, API-Version: v2)      |
| Release IDs   | Returned by root entity field `releaseId` (e.g. `2024-01`); versioned via `?version=<id>` |
| License       | WHO Terms of Use                                 |

## Intake (mondo-source-ingest Phase 1)

| Question | Answer |
|----------|--------|
| **Q1 — Source location** | `https://id.who.int/icd/entity` (versioned: `?version=<release_id>`). Traversal starts at the root entity URI. |
| **Q2 — Source format** | JSON over HTTPS (`Accept: application/json`, `API-Version: v2`). |
| **Q3 — Authentication** | Yes — OAuth2 client credentials (`CLIENT_ID`, `CLIENT_SECRET`); see `env/.env.example`. |
| **Q4 — Versioning** | Versioned snapshots via WHO release id (e.g. `2026-01`); `acquire.py` accepts `--release <id>` and records `release_id` in the consolidated JSON. |

## Source analysis (mondo-source-ingest Phase 4)

Decisions below follow the skill’s mapping dialogue (labels, definitions, synonyms, hierarchy,
obsolete terms, exclusions, cross-references, IRI scheme). SPARQL / ROBOT preprocessing
(**Phase 4.8**) does not apply — this is a **non-OWL** API source.

| Step | Decision |
|------|----------|
| **4.1 Labels** | `title.@value` → `rdfs:label` (`label`). Entities without a title are skipped. |
| **4.2 Definitions** | `definition.@value` → `obo:IAO_0000115` (`definition`). Optional in the API. |
| **4.3 Synonyms** | `fullySpecifiedName`, `synonym`, `narrowerTerm`, `inclusion`, `exclusion` → synonym slots as **`Synonym`** objects (mondo-source-ingest v0.4.0). No generated-from-label synonym unless the API provides text (we do not invent synonyms beyond API fields). |
| **4.4 Hierarchy** | `parent[]` entity URIs → `parents` as `icd11.foundation:<id>` CURIEs; only parents present in the traversed entity set are kept. `http://` → `https://` normalization. |
| **4.5 Obsolete terms** | Foundation entity JSON has **no** `owl:deprecated` (or equivalent) flag in the keys returned for this ingest. **`deprecated` is omitted** in YAML unless we add a future field mapping. |
| **4.5b Non-disease exclusion** | **No subtree exclusion list** — the full traversed Foundation graph is emitted; chapter links (`relatedEntitiesInMaternalChapter`, etc.) are not treated as `skos:exactMatch` (they are same-vocabulary related entities, not external ontology codes). |
| **4.6 Cross-references** | **`skos_exact_match` is left empty.** The API payload does not include `hasDbXref`-style external ontology codes on Foundation entities. Internal `relatedEntities*` URIs are **not** mapped to `skos:exactMatch` (they are not “exact” matches to other ontologies). |
| **4.7 IRI / CURIE** | Class IRIs: `https://id.who.int/icd/entity/<entity_id>`. CURIE: `icd11.foundation:<entity_id>` with prefix in `linkml/mondo_source_schema.yaml`. |
| **4.9 Term counts** | Compare counts to prior releases via `docs/release_notes.md` and `entity_count` in raw JSON. A lower count than “~84 K” may reflect a **specific release id** or API graph change — always record `release_id` in YAML `version`. |

## Phase 2 scaffold (inventory)

This repo is **non-OWL** (JSON API → `extract.py`). The following **mondo-source-ingest**
scaffold items apply:

| Item | Status |
|------|--------|
| `.github/workflows/build.yml`, `release.yml` | Present |
| `docs/plan.md`, `docs/pipeline_incidents.md`, `docs/release_notes.md` | Present |
| `env/.env.example` | Present (`CLIENT_ID`, `CLIENT_SECRET`) |
| `linkml/mondo_source_schema.yaml`, `src/icd11foundation/datamodel.py` | Present |
| `scripts/acquire.py`, `extract.py`, `verify.py` | Present |
| `justfile`, `pyproject.toml`, `uv.lock`, `README.md` | Present |
| `Makefile`, `project.Makefile`, `odk.sh`, `sparql/`, `reports/` | **N/A** (OWL-only) |
| `config/property-map.sssom.tsv` | **Removed** — unused for this pipeline |

## Source Type

**Non-OWL** — raw source is a REST JSON API. The pipeline goes:

```
acquire.py → icd11foundation_raw.json → extract.py → icd11foundation.linkml.yaml → linkml-owl → icd11foundation.linkml.owl
```

## Traversal

The Foundation is a directed graph with ~84,000 entities. `acquire.py` performs a
breadth-first traversal starting from the root entity. Each node response is cached to
`tmp/cache/<encoded-uri>/response.json`. Re-runs skip already-cached nodes.

## Field Mappings

| ICD-11 API field              | LinkML field        | Notes                                     |
|-------------------------------|---------------------|-------------------------------------------|
| `@id` (URI)                   | `id` (CURIE)        | `icd11.foundation:<entity_id>`            |
| `title.@value`                | `label`             | Required; nodes without label are skipped |
| `definition.@value`           | `definition`        | `obo:IAO_0000115`                         |
| `fullySpecifiedName.@value`   | `exact_synonyms`    | `Synonym` objects; added only when different from `title` |
| `synonym[].label.@value`      | `exact_synonyms`    | `oboInOwl:hasExactSynonym` (via `owl.template`)           |
| `narrowerTerm[].label.@value` | `narrow_synonyms`   | `oboInOwl:hasNarrowSynonym`                                 |
| `inclusion[].label.@value`    | `narrow_synonyms`   | Inclusions are narrower concepts                           |
| `exclusion[].label.@value`    | `related_synonyms`  | `oboInOwl:hasRelatedSynonym`                               |
| `parent[]` (URIs)             | `parents` (CURIEs)  | http→https; filtered to entities in set  |
| *(none in API)*             | `skos_exact_match`  | **Omitted** — no external xref fields on Foundation entities (see Phase 4.6). |

## ID Scheme

CURIEs use the `icd11.foundation` prefix:

```
https://id.who.int/icd/entity/1234567890  →  icd11.foundation:1234567890
```

Parent URIs from the API use `http://`; these are normalized to `https://` before lookups.

## Design Decisions

1. **BFS caching:** WHO API calls are expensive and the graph has ~84 K nodes; persistent
   per-node caching makes incremental runs and CI restarts fast.
2. **Skipping unlabelled nodes:** Entities with no `title` field are skipped (typically
   phantom/retired codes).
3. **`is_root`:** Not emitted in YAML (mondo-source-ingest v0.4.0: internal-only in other
   pipelines; hierarchy is fully described by `parents`).
4. **`data2owl`:** `linkml-owl` is attempted. If it fails on the full dataset (rdflib N3
   parser limitation on large files), `icd11foundation.linkml.yaml` is released as the
   sole artifact; see `docs/pipeline_incidents.md` and `docs/report.md`.

## LinkML schema (mondo-source-ingest)

`linkml/mondo_source_schema.yaml` follows the **mondo-source-ingest** skill template (v0.4.0):
synonym slots use `range: Synonym` with `owl.template` in `slot_usage`, top-level `slots:`
with `annotations: owl:` for `linkml-owl`, `id` range `uriorcurie`, required `version`
(`owl:versionInfo`), no `is_root` slot, no `ifabsent` on `deprecated`, and prefix
`icd11.foundation:` → `https://id.who.int/icd/entity/`.

Regenerate Pydantic after schema edits:

```bash
gen-pydantic linkml/mondo_source_schema.yaml > src/icd11foundation/datamodel.py
```

## CI

`.github/workflows/build.yml` runs on pushes and pull requests to `main` when relevant
paths change (`justfile`, `linkml/**`, `scripts/**`, `src/**`, `pyproject.toml`, `uv.lock`,
`docs/**`, `.github/workflows/**`).

GitHub Actions restores `tmp/cache` between runs (`actions/cache@v4`, key
`icd11foundation-api-cache-${{ hashFiles('scripts/acquire.py') }}`) so the first run
pays the full traversal cost; later runs reuse cached WHO API responses.

## Structural verification

After `linkml-validate`, run `scripts/verify.py`:

```bash
uv run python scripts/verify.py --yaml icd11foundation.linkml.yaml --raw-json tmp/icd11foundation_raw.json
```

Optional explicit upstream id: `--expected-version 2026-01`. With `--raw-json`, `release_id`
from the acquire output is used as the expected version when `--expected-version` is omitted.

`just verify` runs the YAML + raw-json invocation; `just check` runs `validate` then `verify`.

`just build` runs `acquire` → `extract` → `validate` → **`verify`** → `data2owl` so Phase 9
structural checks run in the default full local pipeline before OWL derivation.

## Release automation (mondo-source-ingest Phase 8)

**Policy:** **Manual releases only** — `.github/workflows/release.yml` is triggered with
`workflow_dispatch` and requires a `release_tag` input. There is **no** `schedule` (cron)
and **no** automatic release on `push` to `main`, because a cold acquire of the full
Foundation graph is expensive and should not run on a fixed cadence without operator review.

**CI on every change:** `.github/workflows/build.yml` runs on pull requests and pushes to
`main` (path-filtered) and performs acquire → extract → validate → verify → data2owl (with
non-fatal `data2owl`), uploading artefacts for inspection.

To change this policy (e.g. add a monthly scheduled release), update `release.yml` and
record the rationale here.
