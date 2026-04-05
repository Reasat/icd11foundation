# ICD-11 Foundation — Pipeline Plan

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

## Source Type

**Non-OWL** — raw source is a REST JSON API. The pipeline goes:

```
acquire.py → icd11foundation_raw.json → extract.py → icd11foundation.linkml.yml → linkml-owl → icd11foundation.linkml.owl
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
| `fullySpecifiedName.@value`   | `exact_synonyms`    | Added only when different from `title`    |
| `synonym[].label.@value`      | `exact_synonyms`    | `oboInOwl:hasExactSynonym`                |
| `narrowerTerm[].label.@value` | `narrow_synonyms`   | `oboInOwl:hasNarrowSynonym`               |
| `inclusion[].label.@value`    | `narrow_synonyms`   | Inclusions are narrower concepts          |
| `exclusion[].label.@value`    | `related_synonyms`  | `oboInOwl:hasRelatedSynonym`              |
| `parent[]` (URIs)             | `parents` (CURIEs)  | http→https; filtered to entities in set  |

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
3. **`is_root: true`:** Set for entities whose parents are all outside the entity set
   (top-level categories).
4. **data2owl:** `linkml-owl` is attempted. If it fails on the full dataset (rdflib N3
   parser limitation on large files), `icd11foundation.linkml.yml` is released as the
   sole artifact; see `docs/report.md`.

## LinkML schema (mondo-source-ingest)

`linkml/mondo_source_schema.yaml` follows the **mondo-source-ingest** skill template:
top-level `slots:` with `annotations: owl:` for `linkml-owl`, `id` range `uriorcurie`,
required `version` (`owl:versionInfo`), and prefix `icd11.foundation:` →
`https://id.who.int/icd/entity/`.

Regenerate Pydantic after schema edits:

```bash
gen-pydantic linkml/mondo_source_schema.yaml > src/icd11foundation/datamodel.py
```

## CI

GitHub Actions restores `tmp/cache` between runs (`actions/cache@v4`, key
`icd11foundation-api-cache-${{ hashFiles('scripts/acquire.py') }}`) so the first run
pays the full traversal cost; later runs reuse cached WHO API responses.

## Structural verification

After `linkml-validate`, run `scripts/verify.py`:

```bash
uv run python scripts/verify.py --yaml icd11foundation.linkml.yml --raw-json tmp/icd11foundation_raw.json
```

Optional explicit upstream id: `--expected-version 2026-01`. With `--raw-json`, `release_id`
from the acquire output is used as the expected version when `--expected-version` is omitted.

`just verify` runs the YAML + raw-json invocation; `just check` runs `validate` then `verify`.
