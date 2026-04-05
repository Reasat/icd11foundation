# ICD-11 Foundation preprocessed build
#
# Pipeline:
#   just acquire    — BFS-traverse WHO ICD-11 Foundation API → tmp/icd11foundation_raw.json
#   just extract    — JSON cache → icd11foundation.linkml.yml
#   just validate   — linkml-validate
#   just verify     — scripts/verify.py (YAML structure, parents, optional raw-json cross-check)
#   just check      — validate + verify (recommended before release)
#   just data2owl   — icd11foundation.linkml.yml → icd11foundation.linkml.owl
#   just build      — full pipeline: acquire → extract → validate → data2owl
#   just iterate    — extract → validate (tight feedback, skips acquire)
#
# Auth: set CLIENT_ID and CLIENT_SECRET in env/.env (see env/.env.example).

schema   := "linkml/mondo_source_schema.yaml"
raw_json := "tmp/icd11foundation_raw.json"
yaml_out := "icd11foundation.linkml.yml"
owl_out  := "icd11foundation.linkml.owl"

acquire:
    uv run python scripts/acquire.py --output {{raw_json}}

extract:
    uv run python scripts/extract.py --input {{raw_json}} --output {{yaml_out}}

validate:
    uv run python -m linkml.validator.cli -s {{schema}} -C OntologyDocument {{yaml_out}}

verify:
    uv run python scripts/verify.py --yaml {{yaml_out}} --raw-json {{raw_json}}

check: validate verify

data2owl:
    uv run python -m linkml_owl.dumpers.owl_dumper \
        --schema {{schema}} -f yaml -o {{owl_out}} {{yaml_out}}

build: acquire extract validate data2owl

iterate: extract validate

release:
    @echo "Tag and upload via GitHub Actions (workflow_dispatch on release.yml) or:"
    @echo "  gh release create v$(date +%Y-%m-%d) {{yaml_out}} {{owl_out}}"

clean:
    rm -f {{yaml_out}} {{owl_out}}
    rm -rf tmp/
