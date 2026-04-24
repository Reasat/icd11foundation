# ICD-11 Foundation preprocessed build
#
# Pipeline:
#   just acquire       — BFS-traverse WHO ICD-11 Foundation API → tmp/icd11foundation_raw.json
#   just extract       — JSON cache → icd11foundation.linkml.yaml
#   just validate      — linkml-validate
#   just verify        — scripts/verify.py (YAML structure, parents, optional raw-json cross-check)
#   just check         — validate + verify (recommended before release)
#   just dependencies  — mondo-source-ingest: linkml-owl 0.5.0 + linkml/linkml-runtime @ main (comma workaround)
#   just data2owl      — YAML → tmp/icd11foundation_for_owl.json (funowl-safe; JSON avoids linkml YAML reparse bugs) → icd11foundation.linkml.owl
#   just reports       — ROBOT measure + sparql/count_classes_by_top_level.sparql → reports/ (needs ROBOT on PATH or ROBOT_JAR)
#   just build         — acquire → extract → validate → verify → data2owl
#   just all           — build + reports (mondo-source-ingest: full pipeline + QC)
#   just iterate       — extract → validate (tight feedback, skips acquire)
#
# Auth: set CLIENT_ID and CLIENT_SECRET in env/.env (see env/.env.example).

schema   := "linkml/mondo_source_schema.yaml"
raw_json := "tmp/icd11foundation_raw.json"
yaml_out := "icd11foundation.linkml.yaml"
json_owl := "tmp/icd11foundation_for_owl.json"
owl_out  := "icd11foundation.linkml.owl"
reports_dir := "reports"
count_sparql := "sparql/count_classes_by_top_level.sparql"

dependencies:
    uv pip install linkml-owl==0.5.0 \
        "linkml @ git+https://github.com/linkml/linkml.git@main#subdirectory=packages/linkml" \
        "linkml-runtime @ git+https://github.com/linkml/linkml.git@main#subdirectory=packages/linkml_runtime"

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
    uv run python scripts/sanitize_literals_for_owl_export.py \
        --input {{yaml_out}} --output {{json_owl}}
    uv run python -m linkml_owl.dumpers.owl_dumper \
        --schema {{schema}} -f json -o {{owl_out}} {{json_owl}}

reports:
    #!/usr/bin/env bash
    set -euo pipefail
    test -f "{{owl_out}}" || { echo "Missing {{owl_out}}. Run just data2owl or just build first." >&2; exit 1; }
    mkdir -p "{{reports_dir}}"
    if [[ -n "${ROBOT_JAR:-}" ]]; then
      java -Xmx4g -jar "${ROBOT_JAR}" measure -i "{{owl_out}}" -m extended -f json -o "{{reports_dir}}/metrics.json"
      java -Xmx4g -jar "${ROBOT_JAR}" query -i "{{owl_out}}" -f tsv --query "{{count_sparql}}" "{{reports_dir}}/top-level-counts.tsv"
    elif command -v robot >/dev/null 2>&1; then
      robot measure -i "{{owl_out}}" -m extended -f json -o "{{reports_dir}}/metrics.json"
      robot query -i "{{owl_out}}" -f tsv --query "{{count_sparql}}" "{{reports_dir}}/top-level-counts.tsv"
    else
      echo "ROBOT not found. Install https://robot.obolibrary.org or set ROBOT_JAR to robot.jar path." >&2
      exit 1
    fi
    echo "Wrote {{reports_dir}}/metrics.json and {{reports_dir}}/top-level-counts.tsv" >&2

build: acquire extract validate verify data2owl

all: build reports

iterate: extract validate

release:
    @echo "Tag and upload via GitHub Actions (workflow_dispatch on release.yml) or:"
    @echo "  gh release create v$(date +%Y-%m-%d) {{yaml_out}} {{owl_out}}"

clean:
    rm -f {{yaml_out}} {{owl_out}} {{json_owl}}
    rm -f {{reports_dir}}/metrics.json {{reports_dir}}/top-level-counts.tsv
    rm -rf tmp/
