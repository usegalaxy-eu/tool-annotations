#!/usr/bin/env python3
"""
Add every tool from the big public Galaxy servers to tool_tag_mappings.yml,
tagged with the tool panel section it lives in.

Only adds: existing tags (including manually curated ones) are never removed.
New tools are inserted in sorted position; existing entries keep their order.
"""

import json
import re
import sys
import urllib.request
from collections import Counter
from pathlib import Path

import yaml

SERVERS = ["https://usegalaxy.eu", "https://usegalaxy.org", "https://usegalaxy.org.au"]
MAPPING_FILE = Path(__file__).resolve().parent.parent / "tool_tag_mappings.yml"
SAFE_UNQUOTED_RE = re.compile(r"[A-Za-z0-9_.-]+")
# shortcut: only catches versions starting with a digit, extend if a ToolShed tool uses another scheme
VERSIONED_TOOLSHED_ID_RE = re.compile(r"[^/]+/repos/[^/]+/[^/]+/[^/]+/\d[^/]*")

# Section names that should not become tags as they are: map them to an existing
# tag, or to None to skip the section. Spellings that only differ in case or
# punctuation (e.g. "QIIME2" and "QIIME 2") are merged automatically.
TAG_ALIASES = {
    "Blast +": "NCBI Blast",
    "CloudMap (deprecated)": None,
    "Digital Humanities": "Humanities",
    "Fetch Alignments/Sequences": "Fetch Sequences / Alignments",
    "Gemini Tools": "Gemini",
    "Local Tools": None,
    "NCBI BLAST+": "NCBI Blast",
    "RNA Analysis (deprecated)": None,
}


class UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate keys instead of silently keeping the last one."""

    def construct_mapping(self, node, deep=False):
        keys = Counter(self.construct_object(key, deep=deep) for key, _ in node.value)
        duplicates = [key for key, count in keys.items() if count > 1]
        if duplicates:
            raise ValueError(f"duplicate keys: {duplicates}")
        return super().construct_mapping(node, deep=deep)


def load(text: str) -> dict[str, list[str]]:
    data = yaml.load(text, Loader=UniqueKeyLoader)
    tool_tags = data.get("tool_tags") if isinstance(data, dict) else None
    if not isinstance(tool_tags, dict):
        raise ValueError("expected a top-level 'tool_tags' mapping")  # noqa: TRY004
    for tool_id, tags in tool_tags.items():
        if not (
            isinstance(tool_id, str)
            and isinstance(tags, list)
            and tags
            and all(isinstance(tag, str) and tag for tag in tags)
        ):
            raise ValueError(
                f"{tool_id!r} must map to a list of tag strings, got {tags!r} "
                "(quote values like 1.0 or yes)"
            )
    return tool_tags


def strip_version(tool_id: str) -> str:
    if VERSIONED_TOOLSHED_ID_RE.fullmatch(tool_id):
        return tool_id.rsplit("/", 1)[0]
    return tool_id


def normalize(tag: str) -> str:
    return re.sub(r"[^a-z0-9]", "", tag.lower())


def fetch_section_tags(server: str) -> dict[str, list[str]]:
    with urllib.request.urlopen(
        f"{server}/api/tools?in_panel=true", timeout=300
    ) as response:
        panel = json.load(response)
    tags: dict[str, list[str]] = {}
    for section in panel:
        if section.get("model_class") != "ToolSection":
            continue
        tag = TAG_ALIASES.get(section["name"], section["name"])
        if tag is None:
            continue
        for elem in section.get("elems") or []:
            if not elem.get("model_class", "").endswith("Tool"):
                continue
            tool_id = elem["id"]
            if elem.get("tool_shed_repository"):
                tool_id = tool_id.rsplit("/", 1)[0]  # drop the version
            tool_tags = tags.setdefault(tool_id, [])
            if tag not in tool_tags:
                tool_tags.append(tag)
    return tags


def merge(
    existing: dict[str, list[str]], new: dict[str, list[str]]
) -> dict[str, list[str]]:
    merged: dict[str, list[str]] = {}
    pending = sorted(tool_id for tool_id in new if tool_id not in existing)
    i = 0
    for tool_id, tags in existing.items():
        while i < len(pending) and pending[i] < tool_id:
            merged[pending[i]] = []
            i += 1
        merged[tool_id] = list(tags)
    for tool_id in pending[i:]:
        merged[tool_id] = []
    for tool_id, tags in new.items():
        for tag in tags:
            if tag not in merged[tool_id]:
                merged[tool_id].append(tag)
    return merged


def strip_versions(tool_tags: dict[str, list[str]]) -> dict[str, list[str]]:
    stripped: dict[str, list[str]] = {}
    for tool_id, tags in tool_tags.items():
        stripped_tags = stripped.setdefault(strip_version(tool_id), [])
        for tag in tags:
            if tag not in stripped_tags:
                stripped_tags.append(tag)
    return stripped


def canonicalize(
    existing: dict[str, list[str]], new: dict[str, list[str]]
) -> dict[str, list[str]]:
    """Spell each new tag the way the file already does, or as first seen."""
    spellings: dict[str, str] = {}
    for tags in [*existing.values(), *new.values()]:
        for tag in tags:
            spellings.setdefault(normalize(tag), tag)
    return {
        tool_id: list(dict.fromkeys(spellings[normalize(tag)] for tag in tags))
        for tool_id, tags in new.items()
    }


def quote(value: str) -> str:
    # Values like "true", "null" or "1.0" are plain-safe characters but would not load back as strings.
    if SAFE_UNQUOTED_RE.fullmatch(value) and yaml.safe_load(value) == value:
        return value
    return json.dumps(value, ensure_ascii=False)


def dump(tool_tags: dict[str, list[str]]) -> str:
    lines = ["tool_tags:"]
    for tool_id, tags in tool_tags.items():
        lines.append(f"  {quote(tool_id)}:")
        lines.extend(f"  - {quote(tag)}" for tag in tags)
    return "\n".join(lines) + "\n"


def main() -> int:
    existing = load(MAPPING_FILE.read_text(encoding="utf-8"))
    new: dict[str, list[str]] = {}
    for server in SERVERS:
        server_tags = fetch_section_tags(server)
        print(f"{server}: {len(server_tags)} tools")
        new = merge(new, server_tags)

    stripped = strip_versions(existing)
    merged = merge(stripped, canonicalize(existing, new))
    output = dump(merged)
    if load(output) != merged:
        raise RuntimeError("serialized YAML did not round-trip")
    lost = [
        tool_id
        for tool_id, tags in existing.items()
        if not set(tags) <= set(merged[strip_version(tool_id)])
    ]
    if lost:
        raise RuntimeError(f"existing tags were lost for: {lost}")

    MAPPING_FILE.write_text(output, encoding="utf-8")
    print(f"{len(merged) - len(stripped)} tools added, {len(merged)} tools total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
