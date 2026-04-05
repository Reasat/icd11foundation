#!/usr/bin/env python3
"""
Minimal reproduction of:

    AssertionError: Quote expected in string at ^ in XMLSchema#> . :f a ...

This comes from funowl Literal._to_n3() (used by linkml-owl), not from bad YAML.

Mechanism (funowl.literals.Literal._to_n3):
  - It builds a tiny Turtle triple: :f a <value> .
  - If the string does NOT start with " or ', it wraps: " + v + "
  - If the string ALREADY starts with " or ', it skips wrapping — so an unescaped
    leading quote in the lexical value produces INVALID Turtle. rdflib's N3 parser
    then fails, often with the assertion above (the '^' in the message is from the
    parser state, not necessarily a caret in your text).

Run:
  uv run python scripts/repro_funowl_literal_assertion.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


def repro_funowl_direct() -> None:
    from funowl import Literal

    # One character is enough: a value that starts with ASCII double-quote.
    bad = '"quoted leading'
    Literal(bad)


def repro_linkml_owl_cli(schema: Path) -> None:
    """Same failure path through linkml-owl (definition slot → funowl Literal)."""
    yml = """title: Test
version: '2026-01'
terms:
- id: icd11.foundation:1
  label: Test
  definition: '"quoted leading'
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yml", delete=False, encoding="utf-8"
    ) as f:
        f.write(yml)
        tmp = Path(f.name)
    out = tmp.with_suffix(".owl")
    try:
        r = subprocess.run(
            [
                sys.executable,
                "-m",
                "linkml_owl.dumpers.owl_dumper",
                "-s",
                str(schema),
                "-f",
                "yaml",
                "-o",
                str(out),
                str(tmp),
            ],
            capture_output=True,
            text=True,
        )
        err = (r.stderr or "") + (r.stdout or "")
        if r.returncode == 0:
            raise SystemExit("unexpected success — repro should fail")
        if "Quote expected in string at ^" not in err:
            print(err[-2000:])
            raise SystemExit("failed but different error — inspect output above")
        print("   linkml-owl exited non-zero with the same AssertionError in stderr.\n")
    finally:
        tmp.unlink(missing_ok=True)
        out.unlink(missing_ok=True)


def main() -> None:
    print("1) funowl.Literal directly (should raise AssertionError):\n")
    try:
        repro_funowl_direct()
    except AssertionError as e:
        print(f"   Caught: {e!r}\n")
    else:
        raise SystemExit("expected AssertionError")

    root = Path(__file__).resolve().parents[1]
    schema = root / "linkml" / "mondo_source_schema.yaml"
    if schema.exists():
        print('2) linkml-owl CLI on one-term YAML with definition starting with ":\n')
        repro_linkml_owl_cli(schema)
    else:
        print(f"2) skipped (no schema at {schema})")


if __name__ == "__main__":
    main()
