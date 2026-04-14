#!/usr/bin/env python3
"""
Transform ICD-11 Foundation JSON (from acquire.py) into a LinkML YAML instance.

Field mappings from ICD-11 Foundation API response:

    API field                       → LinkML field
    -------------------------------------------------
    @id (URI)                       → id  (CURIE: icd11.foundation:<entity_id>)
    title.@value                    → label
    definition.@value               → definition
    fullySpecifiedName.@value       → exact_synonyms
    synonym[].label.@value          → exact_synonyms
    narrowerTerm[].label.@value     → narrow_synonyms
    inclusion[].label.@value        → narrow_synonyms
    exclusion[].label.@value        → related_synonyms
    parent[]                        → parents (http → https; URI → CURIE)

`is_root` is not written to YAML (internal-only in other pipelines; omitted here).

**Phase 4.6 (`skos_exact_match`):** WHO Foundation entity JSON (API v2) does not expose
`oboInOwl:hasDbXref` or other ontology cross-reference codes on entities. Enumerated keys
across the full acquired graph are limited to structural/linguistic fields (`title`,
`definition`, `synonym`, `parent`, `child`, `browserUrl`, chapter-related `relatedEntities*`,
`relatedImpairment`, etc.). External mappings (e.g. ICD-10) are not present on this
endpoint, so **`skos_exact_match` is not populated** — the slot exists in the shared schema
for linkml-owl compatibility only.

Usage:
    python scripts/extract.py --input tmp/icd11foundation_raw.json \\
                              --output icd11foundation.linkml.yaml
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from icd11foundation.datamodel import OntologyDocument, OntologyTerm, Synonym

# ── CURIE helpers ──────────────────────────────────────────────────────────────

CURIE_PREFIX = "icd11.foundation"


def _entity_id(uri: str) -> str:
    """Extract numeric Foundation entity id from URI."""
    return uri.rstrip("/").rsplit("/", 1)[-1]


def _to_https(uri: str) -> str:
    return uri.replace("http://id.who.int/", "https://id.who.int/", 1)


def _uri_to_curie(uri: str) -> str:
    eid = _entity_id(uri)
    return f"{CURIE_PREFIX}:{eid}"


# ── YAML: quote strings that break plain YAML scalars ───────────────────────────


class QuotingDumper(yaml.SafeDumper):
    pass


def _represent_str(dumper: yaml.Dumper, data: str) -> yaml.ScalarNode:
    if any(c in data for c in ",:{}") or data.strip() != data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style='"')
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


QuotingDumper.add_representer(str, _represent_str)


# ── Field extraction helpers ───────────────────────────────────────────────────


def _lang_value(field: object | None) -> str | None:
    """Extract plain string from a JSON-LD language-value object, or None."""
    if field is None:
        return None
    if isinstance(field, dict):
        v = field.get("@value")
    elif isinstance(field, str):
        v = field
    else:
        return None
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def _label_list(items: list | None) -> list[str]:
    """Extract .label.@value from a list of synonym-style objects."""
    if not items:
        return []
    out: list[str] = []
    for item in items:
        v = _lang_value(item.get("label") if isinstance(item, dict) else None)
        if v:
            out.append(v)
    return out


def _dedup_synonym_strings(strings: list[str]) -> list[Synonym]:
    seen: set[str] = set()
    out: list[Synonym] = []
    for v in strings:
        if v not in seen:
            seen.add(v)
            out.append(Synonym(synonym_text=v))
    return out


# ── Core transform ─────────────────────────────────────────────────────────────


def _node_to_term(uri: str, data: dict, valid_uris: set[str]) -> OntologyTerm | None:
    label = _lang_value(data.get("title"))
    if not label:
        return None

    eid = _entity_id(uri)
    curie = f"{CURIE_PREFIX}:{eid}"

    definition = _lang_value(data.get("definition"))

    exact_strings: list[str] = []
    fsn = _lang_value(data.get("fullySpecifiedName"))
    if fsn and fsn != label:
        exact_strings.append(fsn)
    exact_strings.extend(_label_list(data.get("synonym")))

    narrow_strings = _label_list(data.get("narrowerTerm")) + _label_list(data.get("inclusion"))
    related_strings = _label_list(data.get("exclusion"))

    parents: list[str] = []
    for p in data.get("parent", []):
        p_https = _to_https(p)
        if p_https in valid_uris:
            parents.append(_uri_to_curie(p_https))

    return OntologyTerm(
        id=curie,
        label=label,
        definition=definition,
        exact_synonyms=_dedup_synonym_strings(exact_strings) or None,
        narrow_synonyms=_dedup_synonym_strings(narrow_strings) or None,
        related_synonyms=_dedup_synonym_strings(related_strings) or None,
        parents=parents or None,
    )


# ── Main ───────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract ICD-11 Foundation JSON → LinkML YAML"
    )
    parser.add_argument("--input", type=Path, required=True, help="Raw JSON from acquire.py")
    parser.add_argument("--output", type=Path, required=True, help="Output LinkML YAML")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    print(f"Reading {args.input}...", file=sys.stderr)
    with open(args.input, encoding="utf-8") as f:
        raw = json.load(f)

    release_id: str = raw.get("release_id", "unknown")
    entities: dict[str, dict] = raw.get("entities", {})
    valid_uris = set(entities.keys())

    print(f"  release: {release_id}, entities: {len(entities)}", file=sys.stderr)

    terms: list[OntologyTerm] = []
    skipped = 0
    for uri, data in entities.items():
        term = _node_to_term(uri, data, valid_uris)
        if term is None:
            skipped += 1
            continue
        terms.append(term)

    if skipped:
        print(f"  skipped {skipped} nodes with no label", file=sys.stderr)

    doc = OntologyDocument(
        title="ICD-11 Foundation",
        version=release_id,
        terms=terms,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = doc.model_dump(exclude_none=True)
    with open(args.output, "w", encoding="utf-8") as f:
        yaml.dump(
            payload,
            f,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
            Dumper=QuotingDumper,
        )

    print(f"Written: {args.output} ({len(terms)} terms)", file=sys.stderr)


if __name__ == "__main__":
    main()
