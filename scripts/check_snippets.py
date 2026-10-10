#!/usr/bin/env python3
"""Verify GUIDE.md code snippets against the files they quote.

Contracts (see agentic_development.md "code is the source of truth"):
  * Every fenced code block must carry an annotation on the nearest non-blank
    line above the opening fence:
        <!-- source: PATH -->  -> the block's lines must form an ORDERED
                                  SUBSEQUENCE of PATH's lines. Lines that are
                                  only an elision marker (`...`, `# ...`,
                                  `// ...`, unicode-ellipsis variants) and
                                  blank lines are skipped and need not appear
                                  in PATH.
        <!-- concept -->        -> conceptual example, only the annotation
                                  itself is required.
  * Any other fenced block (missing or unknown annotation) is a FAILURE.

Usage: check_snippets.py [GUIDE.md path]   (default: GUIDE.md in cwd)

Exit 0 iff every block passes; also exit 0, printing "GUIDE.md not present
yet", when the file does not exist (ratchet-friendly while the guide lands).
"""

import pathlib
import re
import sys

# Exact-comment annotations only (a prose paragraph mentioning them is NOT an
# annotation -- it must sit directly above the fence, blank lines aside).
SOURCE_RE = re.compile(r"^<!--\s*source:\s*(.+?)\s*-->$")
CONCEPT_RE = re.compile(r"^<!--\s*concept\s*-->$")

# A fence opens with 3+ backticks or 3+ tildes (max 3 leading spaces, per
# CommonMark) and closes on a run of the SAME char, at least as long, with
# nothing but whitespace after it. Supporting both chars lets concept blocks
# that *demonstrate* ``` fences use ~~~ without confusing this parser.
FENCE_OPEN_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})\s*(\S*)\s*$")
FENCE_CLOSE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})\s*$")

# Elision markers: a block line that is ONLY dots (ASCII or unicode) possibly
# behind a comment leader. Blank block lines are skipped too -- they carry no
# quoted content and authors legitimately trim them.
ELISIONS = {"...", "\u2026", "# ...", "# \u2026", "// ...", "// \u2026"}


def read_lines(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read().replace("\r\n", "\n").split("\n")


def is_elision(line):
    return line.strip() in ELISIONS


class Block(object):
    def __init__(self, start_line, lines):
        self.start_line = start_line  # 1-based line of the opening fence
        self.lines = lines            # content lines (fences excluded)
        self.annotation = None        # ("source", path) | ("concept", None) | None
        self.annotation_line = 0      # 1-based line of the annotation comment


def parse_blocks(guide_lines):
    """Yield Block objects for every fenced code block in the guide."""
    blocks = []
    i, n = 0, len(guide_lines)
    while i < n:
        m = FENCE_OPEN_RE.match(guide_lines[i])
        if not m:
            i += 1
            continue
        marker = m.group(1)
        content, j = [], i + 1
        while j < n:
            c = FENCE_CLOSE_RE.match(guide_lines[j])
            if c and c.group(1)[0] == marker[0] and len(c.group(1)) >= len(marker):
                break
            content.append(guide_lines[j])
            j += 1
        if j >= n:  # unterminated fence: treat rest of file as the block
            pass
        block = Block(i + 1, content)
        # Annotation = nearest non-blank line above the opening fence.
        k = i - 1
        while k >= 0 and guide_lines[k].strip() == "":
            k -= 1
        if k >= 0:
            line = guide_lines[k].strip()
            sm = SOURCE_RE.match(line)
            cm = CONCEPT_RE.match(line)
            if sm:
                block.annotation = ("source", sm.group(1))
                block.annotation_line = k + 1
            elif cm:
                block.annotation = ("concept", None)
                block.annotation_line = k + 1
        blocks.append(block)
        i = j + 1
    return blocks


def check_sourced(block, source_path, failures, guide_name):
    """Ordered-subsequence check of block lines against source_path lines."""
    if not source_path.exists():
        failures.append(
            "%s:%d: source file does not exist: %s"
            % (guide_name, block.start_line, source_path)
        )
        return False
    src_lines = read_lines(source_path)
    src_pos = 0
    ok = True
    for offset, line in enumerate(block.lines):
        if is_elision(line) or line.strip() == "":
            continue
        want = line.rstrip()
        while src_pos < len(src_lines) and src_lines[src_pos].rstrip() != want:
            src_pos += 1
        if src_pos >= len(src_lines):
            failures.append(
                "%s:%d: [%s] line not found (in order) after source line %d: %r"
                % (
                    guide_name,
                    block.start_line + 1 + offset,
                    source_path,
                    src_pos,
                    line[:80],
                )
            )
            ok = False
            # do not cascade: reset to allow later lines to be located
            src_pos = 0
        else:
            src_pos += 1
    return ok


def main(argv):
    if len(argv) > 2:
        print("usage: check_snippets.py [GUIDE.md path]", file=sys.stderr)
        return 2
    guide = pathlib.Path(argv[1] if len(argv) > 1 else "GUIDE.md")
    if not guide.exists():
        print("GUIDE.md not present yet")
        return 0

    guide_name = str(guide)
    guide_lines = read_lines(guide)
    blocks = parse_blocks(guide_lines)

    failures = []
    sourced_ok = sourced_total = concept = 0
    for block in blocks:
        if block.annotation is None:
            failures.append(
                "%s:%d: fenced block without <!-- source: PATH --> or "
                "<!-- concept --> annotation"
                % (guide_name, block.start_line)
            )
            continue
        kind, path = block.annotation
        if kind == "concept":
            concept += 1
        else:
            sourced_total += 1
            if check_sourced(block, (guide.parent / path), failures, guide_name):
                sourced_ok += 1

    for f in failures:
        print("FAIL " + f)
    print(
        "%s: %d/%d sourced blocks verified, %d concept blocks, %d failure(s)"
        % (guide_name, sourced_ok, sourced_total, concept, len(failures))
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
