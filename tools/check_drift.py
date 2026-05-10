#!/usr/bin/env python3
"""Fail-loud drift check between this Go protocol package and the
hand-mirrored TS / Python type definitions in the sibling SDK repos.

The contract being checked: every exported wire-format struct in
types.go has an equivalent type with matching field names in
agent-sdk-typescript/src/types.ts and agent-sdk-python/src/postgrip_agent/types.py.

What we check (deliberately narrow, since the source of truth is Go):

    * Every exported Go struct in types.go (excluding pure-internal
      helpers like requests/responses unique to the runtime API surface)
      appears with the same name in the TS and Python type files.
    * Every JSON-tagged field on those Go structs has a same-name field on
      the TS interface and the Python TypedDict.

What we *don't* check yet (room for v2):

    * Field types. JSON-shape fidelity (e.g. int vs string) is the most
      common drift class but requires a real cross-language type table.
    * Optional vs required. Same problem.
    * Renames where one side leads. Reported as "missing on side X" — the
      author has to read the diff to understand intent.

Usage:

    python3 tools/check_drift.py                 # check the local checkout
    python3 tools/check_drift.py --from-github   # fetch TS/Python from main

Exit codes: 0 clean, 1 drift detected, 2 tooling failure.
"""
from __future__ import annotations

import argparse
import re
import sys
import urllib.request
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent

# Wire types we actively contract on. Keep this list narrow on purpose —
# every type added here is a commitment that TS / Python will mirror it.
# Server-only request shapes (e.g. CompactRequest, EnrollAgentRequest) and
# unauthenticated bootstrap shapes don't belong here.
TRACKED_TYPES = [
    "Task",
    "TaskResult",
    "TaskEvent",
    "TaskEventInput",
    "EnqueueTaskRequest",
    "FailureInfo",
    "ContinueAsNewResult",
    "ShellExecPayload",
    "ContainerExecPayload",
    "WorkflowRuntimePayload",
    "TimerPayload",
    "ActivityTaskPayload",
    "WorkflowPayload",
    "WorkflowQueryPayload",
    "WorkflowUpdatePayload",
    "WorkflowExecution",
    "WorkflowHistoryEvent",
    "Schedule",
    "ScheduleSpec",
    "ScheduleAction",
    "ScheduleCalendarSpec",
    "RetryPolicy",
]

# Where to fetch type files. The "go" url points at agent-sdk-protocol so the
# script can be run from any of the four repos and pull whichever languages
# aren't on disk. --from-github uses these for everything; otherwise we look
# for sibling working dirs at agent-sdk-{language}/.
#
# Note the asymmetry: Go package files live at module root (idiomatic Go
# layout means consumer imports are
# `github.com/postgrip-io/agent-sdk-protocol`, not `…/src`). TS and Python
# keep `src/` per their idiomatic layouts.
GITHUB_RAW = {
    "go":     "https://raw.githubusercontent.com/postgrip-io/agent-sdk-protocol/main/types.go",
    "ts":     "https://raw.githubusercontent.com/postgrip-io/agent-sdk-typescript/main/src/types.ts",
    "python": "https://raw.githubusercontent.com/postgrip-io/agent-sdk-python/main/src/postgrip_agent/types.py",
}
# Repo-local paths, keyed by --local: the language whose types live in this
# checkout (CI in that repo will set --local to it so a PR's changes are
# checked against the OTHER two languages fetched from github main).
LOCAL_PATHS = {
    "go":     Path("types.go"),
    "ts":     Path("src/types.ts"),
    "python": Path("src/postgrip_agent/types.py"),
}
# Sibling working-dir layout for local development across all four repos.
SIBLING_PATHS = {
    "go":     REPO_ROOT.parent / "agent-sdk-protocol" / "types.go",
    "ts":     REPO_ROOT.parent / "agent-sdk-typescript" / "src" / "types.ts",
    "python": REPO_ROOT.parent / "agent-sdk-python" / "src" / "postgrip_agent" / "types.py",
}

# json:"..." -> field name (strip ",omitempty" etc.)
JSON_TAG_RE = re.compile(r'json:"([^",]+)')

# Go: type X struct { ... }
GO_STRUCT_RE = re.compile(r'^type\s+(\w+)\s+struct\s*\{', re.MULTILINE)
# Go: type X = Y  (alias)
GO_ALIAS_RE = re.compile(r'^type\s+(\w+)\s*=\s*(\w+)\s*$', re.MULTILINE)


def parse_go_types(source: str) -> dict[str, set[str]]:
    """Map every `type X struct { ... }` to the set of JSON-tagged field
    names. Type aliases (`type X = Y`) are resolved transparently so callers
    can ask for either side of the alias and get the same field set."""
    structs: dict[str, set[str]] = {}
    pos = 0
    while pos < len(source):
        m = GO_STRUCT_RE.search(source, pos)
        if m is None:
            break
        name = m.group(1)
        i = m.end() - 1
        assert source[i] == "{"
        depth = 1
        i += 1
        while i < len(source) and depth:
            if source[i] == "{":
                depth += 1
            elif source[i] == "}":
                depth -= 1
            i += 1
        body = source[m.end() : i - 1]
        fields = set(JSON_TAG_RE.findall(body))
        structs[name] = fields
        pos = i

    # Resolve aliases by copying the target's field set under the alias name.
    # Aliases of aliases work because we resolve eagerly until the target is
    # a real struct or unresolvable.
    aliases = {m.group(1): m.group(2) for m in GO_ALIAS_RE.finditer(source)}
    out = dict(structs)
    for alias, target in aliases.items():
        seen = {alias}
        cur = target
        while cur in aliases and cur not in seen:
            seen.add(cur)
            cur = aliases[cur]
        if cur in structs:
            out[alias] = structs[cur]
    return out


# TypeScript: export interface X { ... } | export interface X<...> { ... }
TS_INTERFACE_RE = re.compile(
    r'^export\s+interface\s+(\w+)(?:<[^>]*>)?\s*\{', re.MULTILINE,
)
# field name from a TS line like `  foo?: Bar;` or `  foo_bar: Baz;`
TS_FIELD_RE = re.compile(r'^\s*([a-zA-Z_][a-zA-Z0-9_]*)\??:\s', re.MULTILINE)


def parse_ts_types(source: str) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    pos = 0
    while pos < len(source):
        m = TS_INTERFACE_RE.search(source, pos)
        if m is None:
            break
        name = m.group(1)
        i = m.end() - 1
        assert source[i] == "{"
        depth = 1
        i += 1
        while i < len(source) and depth:
            if source[i] == "{":
                depth += 1
            elif source[i] == "}":
                depth -= 1
            i += 1
        body = source[m.end() : i - 1]
        fields = set(TS_FIELD_RE.findall(body))
        out[name] = fields
        pos = i
    return out


# Python: class X(TypedDict, total=False): ... or class X(TypedDict): ...
PY_CLASS_RE = re.compile(
    r'^class\s+(\w+)\s*\(\s*TypedDict[^)]*\)\s*:', re.MULTILINE,
)
# field on a TypedDict body line like `    foo: int` or `    foo_bar: list[str]`
PY_FIELD_RE = re.compile(r'^\s{4}([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s')


def parse_py_types(source: str) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    lines = source.splitlines()
    i = 0
    while i < len(lines):
        m = PY_CLASS_RE.match(lines[i])
        if not m:
            i += 1
            continue
        name = m.group(1)
        fields: set[str] = set()
        i += 1
        # Body lines are indented at least 4 spaces. A blank line is allowed
        # inside the body (but unindented content terminates the class).
        while i < len(lines):
            line = lines[i]
            if not line.strip():
                i += 1
                continue
            if not line.startswith("    "):
                break
            field_match = PY_FIELD_RE.match(line)
            if field_match:
                fields.add(field_match.group(1))
            i += 1
        out[name] = fields
    return out


def load(path_or_url: str | Path, *, from_github: bool) -> str:
    if from_github:
        with urllib.request.urlopen(path_or_url, timeout=30) as resp:
            return resp.read().decode("utf-8")
    with open(path_or_url, encoding="utf-8") as fh:
        return fh.read()


def diff_field_sets(
    name: str, lang: str, go_fields: set[str], lang_fields: set[str],
) -> Iterable[str]:
    missing = sorted(go_fields - lang_fields)
    extra = sorted(lang_fields - go_fields)
    if missing:
        yield f"  {name}.{lang}: missing fields present in Go: {', '.join(missing)}"
    if extra:
        yield f"  {name}.{lang}: extra fields not present in Go: {', '.join(extra)}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--from-github",
        action="store_true",
        help="fetch all three language type files from main on github (skip sibling working dirs)",
    )
    ap.add_argument(
        "--local",
        choices=("go", "ts", "python"),
        help="language whose type file should be read from this checkout (typically set by CI in the SDK repo of that language). Other two are fetched per --from-github / sibling-working-dir.",
    )
    args = ap.parse_args()

    sources: dict[str, str] = {}
    for lang in ("go", "ts", "python"):
        if args.local == lang:
            try:
                sources[lang] = load(REPO_ROOT / LOCAL_PATHS[lang], from_github=False)
            except FileNotFoundError as e:
                print(f"check_drift: --local={lang} but {e}", file=sys.stderr)
                return 2
        elif args.from_github:
            sources[lang] = load(GITHUB_RAW[lang], from_github=True)
        else:
            try:
                sources[lang] = load(SIBLING_PATHS[lang], from_github=False)
            except FileNotFoundError:
                print(
                    f"check_drift: sibling working dir for {lang} not found at "
                    f"{SIBLING_PATHS[lang]}; retry with --from-github or --local={lang}",
                    file=sys.stderr,
                )
                return 2

    go_types = parse_go_types(sources["go"])
    ts_types = parse_ts_types(sources["ts"])
    py_types = parse_py_types(sources["python"])

    failures: list[str] = []
    for name in TRACKED_TYPES:
        go_fields = go_types.get(name)
        if go_fields is None:
            failures.append(f"  {name}: not found in types.go (TRACKED_TYPES out of date?)")
            continue
        ts_fields = ts_types.get(name)
        if ts_fields is None:
            failures.append(f"  {name}: missing TypeScript interface in agent-sdk-typescript/src/types.ts")
        else:
            failures.extend(diff_field_sets(name, "ts", go_fields, ts_fields))
        py_fields = py_types.get(name)
        if py_fields is None:
            failures.append(f"  {name}: missing Python TypedDict in agent-sdk-python/src/postgrip_agent/types.py")
        else:
            failures.extend(diff_field_sets(name, "py", go_fields, py_fields))

    if failures:
        print("Drift detected:", file=sys.stderr)
        for line in failures:
            print(line, file=sys.stderr)
        print(file=sys.stderr)
        print(
            "Resolve by either updating the missing language to mirror Go "
            "(if the Go change is the source of truth) or rolling back the "
            "Go change. Update tools/check_drift.py:TRACKED_TYPES if a type "
            "was renamed.",
            file=sys.stderr,
        )
        return 1

    print(f"Drift check OK ({len(TRACKED_TYPES)} types verified across go / ts / python).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
