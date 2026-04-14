# ICD-11 Foundation — Pipeline incidents

Operational log for errors, deviations from the standard mondo-source-ingest template, and resolutions.

## 2026-04-14 — Schema aligned to mondo-source-ingest v0.4.0

**Change:** `linkml/mondo_source_schema.yaml` was replaced with the shared template: synonym slots use `range: Synonym` with Jinja `owl.template` emission; `is_root` was removed from the schema and from extractor output; `deprecated` no longer uses `ifabsent: "false"` (avoids spurious `owl:deprecated false` axioms). Primary YAML output was renamed to `icd11foundation.linkml.yaml`. `linkml-owl` was bumped to `0.5.0` in `pyproject.toml`.

**Extractor:** `scripts/extract.py` now emits synonym objects (`synonym_text`), uses `QuotingDumper` for YAML serialization, and no longer sets `is_root`.

**Regenerate datamodel after schema edits:**

```bash
gen-pydantic linkml/mondo_source_schema.yaml > src/icd11foundation/datamodel.py
```

## linkml-runtime comma bug (upstream)

If validation fails on synonym text containing commas in inlined lists, install `linkml-runtime` from the `linkml/linkml` monorepo `main` branch (see mondo-source-ingest skill Known Issues). Until then, `uv sync` with pinned `linkml` may still hit `yamlutils._normalize_inlined` errors on large datasets.

## Acquire runtime (no bulk export)

The WHO ICD-11 Foundation API has no bulk export endpoint. A full cold run traverses ~84 K entities and takes several hours. **Resolution:** `acquire.py` caches each node under `tmp/cache/`; CI restores that cache via `actions/cache@v4`.

## data2owl / funowl / rdflib literal parsing

`linkml-owl` can fail when `funowl` builds malformed Turtle for certain literal edge cases (e.g. leading quotes), producing `AssertionError: Quote expected in string`. **Resolution:** CI runs `data2owl` with `|| echo "::warning::"`; the YAML is the primary release artifact. Details and repro: `docs/report.md`, `scripts/repro_funowl_literal_assertion.py`.

## HTTP vs HTTPS

API `parent[]` / `child[]` URIs may use `http://id.who.int/` while requests use `https://`. `acquire.py` and `extract.py` normalize to `https://` before lookups and CURIE generation.

## 2026-04-14 — mondo-source-ingest-update (full skill audit)

**Change:** Audited the repo against **mondo-source-ingest** Phases 1–9 (see **mondo-source-ingest-update** skill). Intake and Phase 4 decisions in `docs/plan.md` were already complete; gaps closed: **Phase 2** — removed unused empty `config/property-map.sssom.tsv` (non-OWL pipeline does not use SSSOM property maps); **Phase 8** — `build.yml` path filters now include `.github/workflows/**` and `docs/**` so workflow and documentation edits trigger CI. Added a **Phase 2 scaffold** inventory table to `docs/plan.md`.

## 2026-04-14 — mondo-source-ingest workflow compliance (documentation + `just build`)

**Change:** `docs/plan.md` now records Phase 1 intake, Phase 4 mapping decisions (including explicit **empty `skos_exact_match`** — WHO Foundation JSON has no external `hasDbXref`-style codes), and Phase 8 release policy (manual `workflow_dispatch` only). `just build` was updated to run **`verify` before `data2owl`**. `extract.py` documents why `skos_exact_match` is not populated. `docs/release_notes.md` includes a compliance section with Phase 9 checklist pointers.
