# ICD-11 Foundation — Pipeline Report

## Known Limitations and Deviations

### 1. Acquire runtime (~several hours for 84K entities)

The WHO ICD-11 Foundation API has no bulk export endpoint. The full graph
(~84,000 entities as of 2024-01) must be fetched one entity at a time.
Each call takes ~0.3–0.5 s, so a full cold run takes several hours.

**Resolution:** `acquire.py` caches every response to `tmp/cache/`. Re-runs
and CI restarts skip already-cached nodes. The cache is preserved between
pipeline invocations.

### 2. `linkml-owl` / funowl / rdflib (`AssertionError: Quote expected in string at ^`)

`linkml-owl` builds **funowl** `Literal` values; **funowl** normalizes strings by
embedding them in a tiny Turtle triple and parsing with **rdflib** (`Literal._to_n3`
in `funowl/literals.py`). If that Turtle is malformed, rdflib raises an assertion such as:

```
AssertionError: Quote expected in string at ^ in XMLSchema#> . :f a ...
```

The `^` in the message is often a **parser-artefact** (Turtle `^^` datatype syntax), not
proof that your text “only” contains a caret. One concrete bug: if a lexical string
**already starts with `"` or `'`**, funowl **skips** wrapping it in outer quotes, so the
synthetic Turtle is invalid and rdflib fails.

**Minimal repro** (no large YAML):

```bash
uv run python scripts/repro_funowl_literal_assertion.py
```

That script shows the failure with **one** `funowl.Literal('"quoted leading')` and the
same path through `linkml-owl` on a one-term YAML. Full ICD-11 runs can fail for this
and other literal edge cases once the dataset is large enough.

**Resolution:** If `data2owl` fails, the released artifact is `icd11foundation.linkml.yml`
only. The OWL step is non-fatal in CI (`|| echo "::warning::"` fallback). Downstream
Mondo ingest reads the YAML directly.

### 3. HTTP vs HTTPS URI normalization

ICD-11 API entity URIs in `child[]` and `parent[]` arrays use `http://id.who.int/`
while the API itself requires `https://`. `acquire.py` converts http→https for
all outbound requests; `extract.py` converts http→https before parent CURIE generation.

### 4. Non-OWL source type

ICD-11 Foundation is a REST JSON API, not an OWL file. Therefore:
- No ROBOT preprocessing is needed.
- `extract.py` maps JSON-LD fields to the `OntologyTerm` LinkML schema directly.
- `linkml-owl` derives the OWL artifact from the validated YAML.
