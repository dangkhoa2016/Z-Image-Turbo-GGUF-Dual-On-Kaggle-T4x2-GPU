#!/usr/bin/env python3
"""Regression contract for the exact Markdown language-switch template."""
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from markdown_language_switch import validate_docs_language_switches

result=validate_docs_language_switches(ROOT/"docs",expected_pairs=11)
assert result=={"pairs":11,"documents":22},result


def expect_failure(folder, fragment):
    try:
        validate_docs_language_switches(folder,expected_pairs=1)
    except AssertionError as err:
        assert fragment in str(err),(fragment,err)
    else:
        raise AssertionError("Incorrect bilingual Markdown accepted: "+fragment)


with tempfile.TemporaryDirectory(prefix="zimage-markdown-lang-") as directory:
    docs=Path(directory)
    en=docs/"example.md"
    vi=docs/"example.vi.md"
    en_ok="# Example\n\n> 🌐 Language / Ngôn ngữ: **English** | [Tiếng Việt](example.vi.md)\n\n## Start\n\nBody.\n"
    vi_ok="# Ví dụ\n\n> 🌐 Language / Ngôn ngữ: [English](example.md) | **Tiếng Việt**\n\n## Bắt đầu\n\nNội dung.\n"
    en.write_text(en_ok)
    vi.write_text(vi_ok)
    assert validate_docs_language_switches(docs,expected_pairs=1)=={"pairs":1,"documents":2}
    en.write_text(en_ok.replace("> 🌐 Language / Ngôn ngữ:","> Language:"))
    expect_failure(docs,"Inconsistent language switch")
    en.write_text(en_ok.replace("example.vi.md","missing.vi.md"))
    expect_failure(docs,"Inconsistent language switch")
    en.write_text(en_ok.replace("**English**","[English](example.md)"))
    expect_failure(docs,"Inconsistent language switch")
    en.write_text(en_ok.replace("\n\n## Start","\n> Language: **English**\n\n## Start"))
    expect_failure(docs,"Missing blank line after language switch")
    en.write_text(en_ok)
    vi.unlink()
    expect_failure(docs,"Missing language")
print("MARKDOWN_LANGUAGE_SWITCH_CPU_PASS docs=22 pairs=11 switch_exact "
      "both_directions legacy_rejected missing_peer_rejected malformed_rejected")