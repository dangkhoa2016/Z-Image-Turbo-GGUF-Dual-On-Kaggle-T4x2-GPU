#!/usr/bin/env python3
"""Validate bilingual Markdown navigation across the project's docs directory.

The contract is intentionally exact: both languages have the same visible
switch, the active language is bold, and the inactive language is a real
relative link to its peer. This catches documentation style regressions that
existence-only language-pair checks previously missed.
"""
from pathlib import Path


def validate_docs_language_switches(docs_root, expected_pairs=None):
    docs_root = Path(docs_root)
    files = sorted(docs_root.glob("*.md"))
    pairs = {}
    for path in files:
        if path.name.endswith(".vi.md"):
            key = path.name[:-6]
            language = "vi"
        else:
            key = path.stem
            language = "en"
        assert language not in pairs.setdefault(key, {}), ("Duplicate document",path)
        pairs[key][language] = path
    if expected_pairs is not None:
        assert len(pairs) == expected_pairs, ("Unexpected number of document pairs",len(pairs))
    for key, group in pairs.items():
        assert set(group) == {"en", "vi"}, ("Missing language",key,group)
        for lang,path in group.items():
            lines = path.read_text(encoding="utf-8").splitlines()
            assert len(lines) >= 5, ("Short document",path)
            assert lines[0].startswith("# ") and lines[1] == "", ("Heading layout",path)
            expected = (
                f"> 🌐 Language / Ngôn ngữ: **English** | [Tiếng Việt]({group['vi'].name})"
                if lang == "en" else
                f"> 🌐 Language / Ngôn ngữ: [English]({group['en'].name}) | **Tiếng Việt**"
            )
            assert lines[2] == expected, ("Inconsistent language switch",path,lines[2])
            assert lines[3] == "", ("Missing blank line after language switch",path)
            assert lines.count(expected) == 1, ("Repeated language switch",path)
            for candidate in lines[4:12]:
                assert not candidate.startswith((
                    "> Language:", "> Ngôn ngữ:", "> Language / Ngôn ngữ:",
                    "> 🌐 Language / Ngôn ngữ:", "[English](", "[Tiếng Việt]("
                )), ("Duplicate legacy switch",path,candidate)
            # Resolve only the exact peer within docs/, with no redirect/fallback.
            peer = (docs_root / group["vi"].name if lang == "en"
                    else docs_root / group["en"].name)
            assert peer.is_file() and peer.parent == docs_root,("Broken language-switch link",path)
    return {"pairs":len(pairs),"documents":len(files)}


if __name__ == "__main__":
    result = validate_docs_language_switches(
        Path(__file__).resolve().parents[1] / "docs", expected_pairs=14)
    print("MARKDOWN_LANGUAGE_SWITCH_AUDIT_PASS",result)