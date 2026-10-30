# tool-annotations

A central, community-curated mapping of Galaxy tool IDs to tags.

## What This Is

This repository provides a YAML file ([`tool_tag_mappings.yml`](https://github.com/usegalaxy-eu/tool-annotations/blob/main/tool_tag_mappings.yml)) that associates Galaxy tool IDs — identified by their short names for upstream tools (e.g. `Cut1`, `Filter1`) or full ToolShed paths — with human-readable tags (e.g. `"Text Manipulation"`, `"Mapping"`, `"ChemicalToolBox"`, `"Machine Learning"`). It can be used to drive tool search by tag.

Tags are flexible — there is no rigid controlled vocabulary. New tags are welcome.

## Format

```yaml
tool_tags:
  Cut1:
  - "Text Manipulation"
  "toolshed.g2.bx.psu.edu/repos/bgruening/antismash/antismash":
  - Annotation
```

A tool may have multiple tags. Use ToolShed IDs without the version, and quote values that contain anything other than letters, digits, `_`, `.` and `-`.

## Contributing

To add or update tags, submit a PR editing [`tool_tag_mappings.yml`](https://github.com/usegalaxy-eu/tool-annotations/blob/main/tool_tag_mappings.yml). Each tool ID should appear only once under `tool_tags:`.

## Automatic Updates

A weekly GitHub Action runs [`scripts/update_tool_tags.py`](scripts/update_tool_tags.py), which adds all tools in the tool panel sections of usegalaxy.eu, usegalaxy.org and usegalaxy.org.au, tagged with their section name, and opens a PR. It only adds tools and tags; manually added tags are never removed. Section names that differ only in case or punctuation are merged into the spelling already used in the file; other renames, or sections to skip, go in `TAG_ALIASES` in the script.