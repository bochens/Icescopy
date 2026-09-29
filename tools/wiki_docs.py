#!/usr/bin/env python3
"""Check documentation links and stage a separate GitHub wiki publication.

This utility uses the standard library and never publishes, deletes, or updates
an existing destination. The repository's wiki/ directory remains the source.
"""

from __future__ import annotations

import argparse
import html
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import quote, unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
WIKI = ROOT / "wiki"
REPOSITORY = "https://github.com/bochens/Icescopy"
RAW = "https://raw.githubusercontent.com/bochens/Icescopy"
LINK = re.compile(r"(!?)\[([^\]\n]*)\]\(([^)\n]+)\)")
FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
INLINE_CODE = re.compile(r"(`+)(?!`)(.*?)\1(?!`)")


def link_matches(line):
    """Do not treat literal Markdown examples inside inline code as links."""
    code_spans = [(match.start(), match.end()) for match in INLINE_CODE.finditer(line)]
    return [match for match in LINK.finditer(line)
            if not any(start <= match.start() < end for start, end in code_spans)]


def prose_lines(text):
    """Yield line number and text outside fenced code blocks."""
    fence = None
    for number, line in enumerate(text.splitlines(keepends=True), 1):
        marker = FENCE.match(line)
        if marker:
            value = marker[1]
            if fence is None:
                fence = value
            elif value[0] == fence[0] and len(value) >= len(fence):
                fence = None
            continue
        if fence is None:
            yield number, line


def anchors(path):
    """Read GitHub-style anchors for the headings used by this documentation."""
    result = set()
    for _, line in prose_lines(path.read_text(encoding="utf-8")):
        match = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line)
        if not match:
            continue
        heading = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", match[1])
        heading = html.unescape(re.sub(r"<[^>]+>", "", heading)).lower()
        base = re.sub(r"[^\w\- ]", "", heading).replace(" ", "-")
        anchor = base
        suffix = 0
        while anchor in result:
            suffix += 1
            anchor = f"{base}-{suffix}"
        result.add(anchor)
    return result


def resolve_link(page, target):
    target = target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc:
        return None
    path = (page.parent / unquote(parsed.path)).resolve() if parsed.path else page
    if not path.exists() and not path.suffix:
        candidate = path.with_suffix(".md")
        if candidate.exists():
            path = candidate
    return path, unquote(parsed.fragment)


def check():
    pages = sorted(WIKI.glob("*.md")) + [ROOT / "README.md"]
    errors = []
    checked = 0
    anchor_cache = {}
    line_counts = {}
    for page in pages:
        text = page.read_text(encoding="utf-8")
        for number, line in prose_lines(text):
            for match in link_matches(line):
                resolved = resolve_link(page, match[3])
                if resolved is None:
                    continue
                checked += 1
                path, fragment = resolved
                problem = None
                if not path.is_relative_to(ROOT):
                    problem = "link leaves the repository"
                elif not path.is_file():
                    problem = "target file does not exist"
                elif fragment and path.suffix == ".md":
                    if path not in anchor_cache:
                        anchor_cache[path] = anchors(path)
                    if fragment not in anchor_cache[path]:
                        problem = "heading anchor does not exist"
                elif fragment:
                    location = re.fullmatch(r"L(\d+)(?:-L(\d+))?", fragment)
                    if location:
                        start = int(location[1])
                        end = int(location[2] or start)
                        if path not in line_counts:
                            line_counts[path] = len(path.read_text(encoding="utf-8").splitlines())
                        count = line_counts[path]
                        if not 1 <= start <= end <= count:
                            problem = "source line is out of range"
                if problem:
                    errors.append(f"{page.relative_to(ROOT)}:{number}: {problem}: {match[3]}")
    for error in errors:
        print(error, file=sys.stderr)
    print(f"Checked {checked} local links across {len(pages)} Markdown files; {len(errors)} errors.")
    return not errors


def publication_target(page, target, source_ref, image):
    resolved = resolve_link(page, target)
    if resolved is None:
        return target
    path, fragment = resolved
    suffix = "#" + quote(fragment, safe="-_") if fragment else ""
    parsed = urlsplit(target)
    if not parsed.path:
        return suffix
    if path.parent == WIKI and path.suffix == ".md":
        return quote(path.stem) + suffix
    relative = quote(path.relative_to(ROOT).as_posix(), safe="/")
    ref = quote(source_ref, safe="")
    base = f"{RAW}/{ref}" if image else f"{REPOSITORY}/blob/{ref}"
    return f"{base}/{relative}{suffix}"


def stage(destination, source_ref):
    if not re.fullmatch(r"[0-9a-f]{40}", source_ref):
        raise ValueError("--source-ref must be a full, published Git commit SHA")
    commit = subprocess.run(
        ["git", "rev-parse", "--verify", source_ref + "^{commit}"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if commit.returncode or commit.stdout.strip() != source_ref:
        raise ValueError("--source-ref is not a locally available commit SHA")
    destination = destination.expanduser().resolve()
    if destination.exists():
        raise ValueError("Destination already exists; choose a new staging directory")
    if not check():
        raise ValueError("Fix documentation link errors before staging")
    pages = sorted(WIKI.glob("*.md"))
    committed_files = subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", source_ref], cwd=ROOT, text=True,
    ).splitlines()
    referenced_files = {page.relative_to(ROOT).as_posix() for page in pages}
    for page in pages:
        for _, line in prose_lines(page.read_text(encoding="utf-8")):
            for match in link_matches(line):
                resolved = resolve_link(page, match[3])
                if resolved is not None:
                    referenced_files.add(resolved[0].relative_to(ROOT).as_posix())
    if referenced_files - set(committed_files):
        raise ValueError("Some wiki pages or linked files are absent from --source-ref; commit them first")
    difference = subprocess.run(
        ["git", "diff", "--quiet", source_ref, "--", *sorted(referenced_files)], cwd=ROOT,
    )
    if difference.returncode:
        raise ValueError("Wiki pages or linked files differ from --source-ref; commit/review before staging")
    converted = {}
    for page in pages:
        text = page.read_text(encoding="utf-8")
        replacements = dict(prose_lines(text))
        output = []
        for number, line in enumerate(text.splitlines(keepends=True), 1):
            if number in replacements:
                # Replace from the end so offsets remain valid and preserve
                # code-span examples such as `[label](Some-Page.md)` verbatim.
                for match in reversed(link_matches(line)):
                    target = publication_target(page, match[3], source_ref, bool(match[1]))
                    replacement = f"{match[1]}[{match[2]}]({target})"
                    line = line[:match.start()] + replacement + line[match.end():]
            output.append(line)
        converted[page.name] = "".join(output)
    destination.mkdir(parents=True, exist_ok=False)
    for name, text in converted.items():
        (destination / name).write_text(text, encoding="utf-8")
    print(f"Staged {len(converted)} wiki pages in {destination}. No Git write or publication was performed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="Check local file links, headings, and source line bounds")
    staging = commands.add_parser("stage", help="Create a new, separate publication directory")
    staging.add_argument("--destination", type=Path, required=True)
    staging.add_argument("--source-ref", required=True, help="Published repository commit for source/image links")
    args = parser.parse_args()
    if args.command == "check":
        return 0 if check() else 1
    try:
        stage(args.destination, args.source_ref)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
