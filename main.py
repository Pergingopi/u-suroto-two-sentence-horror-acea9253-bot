#!/usr/bin/env python3
"""Two-Sentence Horror - one horror story in exactly two sentences.

Pure Python 3 standard library. The program writes the story to
/output/entry.txt (or $MAKEFUN_OUTPUT_DIR/entry.txt). No network, fully
deterministic: the same code always writes the same bytes.

The story (267 characters, exactly 2 sentences, no trailing newline):
    Our new neighbors sing their baby to sleep every night, and the lullaby
    drifts through the wall so clearly that I have learned the words by
    heart. Last night I finally sang along \u2014 and from the other side of
    the wall, someone sang the next verse back in my own voice.

Why this story: sentence 2 re-reads sentence 1. The narrator learned the
lullaby by heart through the wall, so when someone on the other side sings
the next verse back in the narrator's own voice, the cozy nightly ritual
turns into something that has been listening, learning, and waiting to
answer. The horror is implied, never explained: nothing is named, no gore,
no monster described -- the reader fills in the worst part. Before writing,
the program validates the story against every gate (no control characters,
not whitespace-only, 1-400 characters, no trailing newline, exactly two
sentences), so a bad edit fails loudly here instead of shipping an invalid
entry.

Usage: mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
"""

import os
import re
import sys

STORY = (
    "Our new neighbors sing their baby to sleep every night, and the "
    "lullaby drifts through the wall so clearly that I have learned the "
    "words by heart. Last night I finally sang along \u2014 and from the "
    "other side of the wall, someone sang the next verse back in my own "
    "voice."
)

# Abbreviations whose period is not a sentence end.
_ABBREVIATIONS = {
    "mr", "mrs", "ms", "dr", "st", "vs", "etc", "e.g", "i.e",
    "jr", "sr", "prof", "no", "fig", "approx", "dept", "a.m", "p.m",
}


def count_sentences(text):
    """Count sentences by terminal punctuation, ignoring abbreviations.

    A terminator (., !, ?) ends a sentence only when it is followed by
    whitespace, a closing quote, or the end of the text, and -- for a
    period -- when the word before it is not a known abbreviation and the
    period is not between two digits (a decimal point).
    """
    count = 0
    for match in re.finditer(r"[.!?]+", text):
        end = match.end()
        nxt = text[end:end + 1]
        if nxt and nxt not in " \t\r\n\"')]}":
            continue
        if match.group().startswith("."):
            before = text[: match.start()]
            word = re.split(r"\s+", before)[-1].rstrip(".").lower()
            if word in _ABBREVIATIONS:
                continue
            prev = text[match.start() - 1:match.start()]
            if prev.isdigit() and nxt.isdigit():
                continue
        count += 1
    return count


def validate(text):
    """Enforce the competition gates; raise ValueError on any violation."""
    if not text or text.strip() == "":
        raise ValueError("story must not be empty or whitespace-only")
    if len(text) < 1 or len(text) > 400:
        raise ValueError("story must be 1-400 characters, got %d" % len(text))
    if text.endswith("\n") or text.endswith("\r"):
        raise ValueError("story must not end with a trailing newline")
    for ch in text:
        code = ord(ch)
        if code < 0x20 or 0x7F <= code <= 0x9F:
            raise ValueError("story contains a control character U+%04X" % code)
    if count_sentences(text) != 2:
        raise ValueError(
            "story must be exactly 2 sentences, counted %d"
            % count_sentences(text)
        )


def _write_all(fd, data):
    """Write every byte; a single os.write may write only part of data."""
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        if written == 0:
            raise OSError("os.write wrote 0 bytes; refusing partial write")
        view = view[written:]


def _unlink_best_effort(path):
    try:
        os.unlink(path)
    except OSError:
        pass


def main():
    validate(STORY)
    data = STORY.encode("utf-8")

    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    # Never delete the output directory itself; only create it if missing.
    os.makedirs(out_dir, exist_ok=True)

    final = os.path.join(out_dir, "entry.txt")
    tmp = os.path.join(out_dir, ".entry.txt.tmp")
    # Exclusive create: fail rather than silently overwriting a stray tmp.
    # A leftover tmp can only come from an earlier run that died mid-write
    # (this program always unlinks it on failure and replaces it on
    # success), so retry once after removing the stale file instead of
    # failing every future run on a crash leftover.
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        _unlink_best_effort(tmp)
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        _write_all(fd, data)
        os.fsync(fd)
    except BaseException:
        # Never leave a partial tmp behind for the next run to trip over.
        try:
            os.close(fd)
        finally:
            _unlink_best_effort(tmp)
        raise
    else:
        os.close(fd)
    os.chmod(tmp, 0o644)
    os.replace(tmp, final)
    os.chmod(final, 0o644)
    # fsync the directory so the rename is durable.
    dir_fd = os.open(out_dir, os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)
    # Read-back: the file on disk must be byte-identical to the constant.
    with open(final, "rb") as f:
        if f.read() != data:
            raise ValueError("read-back mismatch: entry.txt != STORY")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        raise SystemExit(1)
