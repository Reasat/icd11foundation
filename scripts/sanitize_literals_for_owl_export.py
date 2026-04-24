#!/usr/bin/env python3
"""
Rewrite string literals in LinkML YAML so linkml-owl → funowl → rdflib can serialize them.

funowl.Literal only wraps a value in outer \"...\" when the lexical form does *not*
start with ASCII \" or '. Leading U+0022 (or U+0027) is spliced raw into a tiny Turtle
fragment, which breaks rdflib (e.g. AssertionError: Quote expected in string at ^).

This script is **OWL-export only**: it reads the canonical YAML and writes a **temporary**
copy for `owl_dumper`. The released primary YAML is unchanged.

Mitigation: if a string starts with U+0022, replace that code point with U+201C (LEFT
DOUBLE QUOTATION MARK). If it starts with U+0027, replace with U+2018 (LEFT SINGLE
QUOTATION MARK). Visual intent is preserved; the OWL lexical form no longer triggers
the funowl bug.

Example (WHO browse, synonym with leading ASCII quote breaking funowl pre-fix):
https://icd.who.int/browse/2026-01/foundation/en#1000664379

Usage:
    python scripts/sanitize_literals_for_owl_export.py \\
        --input icd11foundation.linkml.yaml \\
        --output tmp/icd11foundation_for_owl.json

Writes **JSON** by default when the output path ends in ``.json`` (recommended): avoids a
second YAML serialization of inlined ``Synonym`` lists, which can trigger
``linkml_runtime`` ``_normalize_inlined`` / ``order_up`` errors (e.g. synonym_text vs key
mismatch) after ``yaml.dump``. Use ``.yaml`` only if you need YAML for debugging.
"""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

# Strings that become OWL annotation literals via linkml-owl / schema templates.
_SYN_KEYS = ("exact_synonyms", "related_synonyms", "narrow_synonyms", "broad_synonyms")


def _coerce_synonyms_for_linkml_runtime(obj: dict[str, Any]) -> int:
    """
    Rewrite ``{"synonym_text": s}`` (sole key) to ``[s]`` for linkml-owl / YAMLRoot.

    linkml_runtime ``yamlutils._normalize_inlined`` treats a **one-key** dict as a special
    case and calls ``Synonym(list_entry)`` with the dict as a **single positional**
    argument. That is not ``Synonym(**dict)`` and breaks ``order_up`` (e.g. *infection
    NOS* / JsonObj mismatch). A **list** entry hits ``Synonym(*list_entry)``, which maps
    correctly to ``synonym_text``. Dicts with extra keys (e.g. ``synonym_type``) are left
    unchanged (``len > 1`` uses the kwargs path).
    """
    n = 0
    for sk in _SYN_KEYS:
        lst = obj.get(sk)
        if not isinstance(lst, list):
            continue
        out: list[Any] = []
        for item in lst:
            if isinstance(item, dict) and set(item.keys()) == {"synonym_text"}:
                st = item["synonym_text"]
                out.append([str(st)])
                n += 1
            else:
                out.append(item)
        obj[sk] = out
    return n


def _fix_funowl_leader(s: str) -> str:
    if s.startswith('"'):
        return "\u201c" + s[1:]
    if s.startswith("'"):
        return "\u2018" + s[1:]
    return s


def _mutate_string_fields(obj: dict[str, Any]) -> int:
    """Return number of strings altered."""
    changed = 0
    for key in ("title", "version", "label", "definition", "id"):
        if key not in obj:
            continue
        val = obj[key]
        if isinstance(val, str):
            new = _fix_funowl_leader(val)
            if new != val:
                obj[key] = new
                changed += 1
    matches = obj.get("skos_exact_match")
    if isinstance(matches, list):
        for i, m in enumerate(matches):
            if isinstance(m, str):
                new = _fix_funowl_leader(m)
                if new != m:
                    matches[i] = new
                    changed += 1
    for sk in _SYN_KEYS:
        lst = obj.get(sk)
        if not isinstance(lst, list):
            continue
        for item in lst:
            if not isinstance(item, dict):
                continue
            st = item.get("synonym_text")
            if isinstance(st, str):
                new = _fix_funowl_leader(st)
                if new != st:
                    item["synonym_text"] = new
                    changed += 1
    return changed


def sanitize_document(data: dict[str, Any]) -> int:
    """Mutate data in place; return total number of string / synonym-shape fixes."""
    total = 0
    total += _mutate_string_fields(data)
    terms = data.get("terms")
    if isinstance(terms, list):
        for term in terms:
            if isinstance(term, dict):
                total += _mutate_string_fields(term)
                total += _coerce_synonyms_for_linkml_runtime(term)
    total += _coerce_synonyms_for_linkml_runtime(data)
    return total


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Copy LinkML YAML with funowl-safe leading quotes (OWL export only)."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Write back to --input (not recommended for release YAML).",
    )
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: input not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    with open(args.input, encoding="utf-8") as f:
        payload = yaml.safe_load(f)
    if not isinstance(payload, dict):
        print("Error: root YAML value must be a mapping", file=sys.stderr)
        sys.exit(1)

    if args.in_place:
        work = payload
    else:
        work = deepcopy(payload)

    n = sanitize_document(work)
    if n:
        print(f"sanitize_literals_for_owl_export: applied {n} adjustment(s)", file=sys.stderr)

    out_path = args.input if args.in_place else args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.suffix.lower() == ".json":
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(work, f, ensure_ascii=False, indent=2)
    else:
        with open(out_path, "w", encoding="utf-8") as f:
            yaml.dump(
                work,
                f,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
            )

    print(f"Written: {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
