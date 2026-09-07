#!/usr/bin/env python3
"""Update the stub binary revision and hashes in briefcase.toml.

Usage::

    python scripts/update_stub_hashes.py <stub-revision>

For the given stub binary revision, this script will:

1. Update ``stub_binary_revision`` in ``{{ cookiecutter.format }}/briefcase.toml``.
2. Download every windows stub binary variant (GUI/Console x AMD64/ARM64)
   for every Python version tag currently listed in the file's hash dicts.
3. Compute the sha256 of each downloaded binary, and update the corresponding
   ``stub_binary_hash`` entry.
4. If a binary can't be found (HTTP 403/404) for a given Python tag, that tag's
   entry is removed from the relevant hash dict entirely (rather than being left
   with a stale or placeholder hash).
5. Delete the temporary downloads.

The stub binaries are published publicly at:

    https://briefcase-support.s3.amazonaws.com/python/<python-tag>/windows/<filename>.zip

where ``<filename>`` is one of:

    Console-Stub-<python-tag>-amd64-b<revision>.zip    (console app, AMD64)
    GUI-Stub-<python-tag>-amd64-b<revision>.zip        (GUI app, AMD64)
    Console-Stub-<python-tag>-arm64-b<revision>.zip    (console app, ARM64)
    GUI-Stub-<python-tag>-arm64-b<revision>.zip        (GUI app, ARM64)
"""

from __future__ import annotations

import hashlib
import re
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = "https://briefcase-support.s3.amazonaws.com/python"

TEMPLATE_ROOT = Path(__file__).resolve().parent.parent
BRIEFCASE_TOML = TEMPLATE_ROOT / "{{ cookiecutter.format }}" / "briefcase.toml"

# console_app -> app_prefix
APP_PREFIX = {
    True: "Console",
    False: "GUI",
}

# Matches a jinja `{% if ... %}` line that toggles console_app.
CONSOLE_IF_RE = re.compile(r"{%-?\s*if\s+(not\s+)?cookiecutter\.console_app\s*-?%}")
# Matches a jinja `{% if ... %}` line that toggles host_arch.
ARCH_IF_RE = re.compile(
    r'{%-?\s*if\s+cookiecutter\.host_arch\s*==\s*"(?P<arch>AMD64|ARM64)"\s*-?%}'
)
ELSE_RE = re.compile(r"{%-?\s*else\s*-?%}")
ENDIF_RE = re.compile(r"{%-?\s*endif\s*-?%}")

# Matches a `"<python-tag>": "stub_binary_hash = 'sha256:<hash-or-xxx>'",` dict entry.
HASH_ENTRY_RE = re.compile(
    r'^(?P<indent>\s*)"(?P<tag>\d+\.\d+)":\s*'
    r'"stub_binary_hash = \'sha256:(?P<hash>[0-9a-fA-F]+|xxx)\'",\s*$'
)

REVISION_RE = re.compile(r'(stub_binary_revision = ")\d+(")')

OTHER_ARCH = {
    "AMD64": "ARM64",
    "ARM64": "AMD64",
}


def stub_filename(app_prefix: str, python_tag: str, arch: str, revision: str) -> str:
    return f"{app_prefix}-Stub-{python_tag}-{arch.lower()}-b{revision}.zip"


def stub_url(python_tag: str, filename: str) -> str:
    return f"{BASE_URL}/{python_tag}/windows/{filename}"


def download_hash(url: str, dest_dir: Path) -> str | None:
    """Download `url` into `dest_dir` and return its sha256 hex digest.

    Returns None if the resource doesn't exist (HTTP 403/404).
    """
    dest_path = dest_dir / Path(url).name
    try:
        with urllib.request.urlopen(url) as response, dest_path.open("wb") as f:
            hasher = hashlib.sha256()
            while chunk := response.read(65536):
                hasher.update(chunk)
                f.write(chunk)
    except urllib.error.HTTPError as e:
        if e.code in (403, 404):
            return None
        raise
    finally:
        dest_path.unlink(missing_ok=True)

    return hasher.hexdigest()


def find_dict_blocks(lines: list[str]) -> dict[tuple[str, bool], tuple[int, int]]:
    """Walk the jinja if/else/endif structure and find the line range of each
    stub_binary_hash dict, keyed by (host_arch, console_app).

    Returns a mapping of (host_arch, console_app) -> (start_line, end_line)
    (inclusive, 0-indexed) covering the dict entry lines for that variant.
    """
    # Stack of [var_name, current_value, block_start_of_current_branch]
    stack: list[list] = []
    blocks: dict[tuple[str, bool], tuple[int, int]] = {}

    def current_state() -> tuple[str | None, bool | None]:
        arch = None
        console_app = None
        for var_name, value, _ in stack:
            if var_name == "arch":
                arch = value
            elif var_name == "console_app":
                console_app = value
        return arch, console_app

    for i, line in enumerate(lines):
        m = ARCH_IF_RE.search(line)
        if m:
            stack.append(["arch", m.group("arch"), i])
            continue

        m = CONSOLE_IF_RE.search(line)
        if m:
            negate = bool(m.group(1))
            stack.append(["console_app", not negate, i])
            continue

        if ELSE_RE.search(line):
            if stack:
                var_name, value, _ = stack[-1]
                if var_name == "arch":
                    stack[-1][1] = OTHER_ARCH[value]
                else:
                    stack[-1][1] = not value
                stack[-1][2] = i
            continue

        if ENDIF_RE.search(line):
            if stack:
                stack.pop()
            continue

        if HASH_ENTRY_RE.match(line):
            arch, console_app = current_state()
            if arch is not None and console_app is not None:
                key = (arch, console_app)
                if key not in blocks:
                    blocks[key] = (i, i)
                else:
                    start, _ = blocks[key]
                    blocks[key] = (start, i)

    return blocks


def update_revision(text: str, revision: str) -> str:
    new_text, count = REVISION_RE.subn(rf"\g<1>{revision}\g<2>", text, count=1)
    if count == 0:
        raise ValueError("Could not find stub_binary_revision in briefcase.toml")
    return new_text


def update_hashes(text: str, revision: str) -> str:
    lines = text.splitlines(keepends=True)
    blocks = find_dict_blocks(lines)

    with tempfile.TemporaryDirectory(prefix="briefcase-stub-hashes-") as tmp:
        dest_dir = Path(tmp)

        # Collect the set of python tags currently present, from any block.
        all_tags = set()
        for start, end in blocks.values():
            for i in range(start, end + 1):
                m = HASH_ENTRY_RE.match(lines[i])
                if m:
                    all_tags.add(m.group("tag"))

        # Lines to delete (missing binaries), tracked by index.
        lines_to_delete: set[int] = set()

        for (arch, console_app), (start, end) in blocks.items():
            app_prefix = APP_PREFIX[console_app]
            variant_name = (
                f"{arch}, {'console' if console_app else 'GUI'}"
            )

            for i in range(start, end + 1):
                m = HASH_ENTRY_RE.match(lines[i])
                if not m:
                    continue

                python_tag = m.group("tag")
                filename = stub_filename(app_prefix, python_tag, arch, revision)
                url = stub_url(python_tag, filename)

                print(f"Downloading {variant_name} {python_tag} stub: {url}")
                digest = download_hash(url, dest_dir)

                if digest is None:
                    print(f"  -> not found; removing {python_tag} from {variant_name} dict")
                    lines_to_delete.add(i)
                else:
                    print(f"  -> sha256:{digest}")
                    new_line = (
                        f"{m.group('indent')}\"{python_tag}\": "
                        f"\"stub_binary_hash = 'sha256:{digest}'\",\n"
                    )
                    lines[i] = new_line

    return "".join(line for i, line in enumerate(lines) if i not in lines_to_delete)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {argv[0]} <stub-revision>", file=sys.stderr)
        return 2

    revision = argv[1]

    text = BRIEFCASE_TOML.read_text()
    text = update_revision(text, revision)
    text = update_hashes(text, revision)
    BRIEFCASE_TOML.write_text(text)

    print(f"Updated {BRIEFCASE_TOML} to stub binary revision {revision}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
