---
name: memory-write
description: "写入知识文件并自动更新 topics.md 索引"
tools: ["Bash"]
---

## Purpose

Write knowledge content to a bucket file and automatically update the topics.md knowledge index.

## Input

- `bucket`: pm | architect | dev | qa
- `file`: filename within the bucket
- `--topic`: topic name for topics.md index
- `--summary`: one-line description for topics.md
- `--anchor` (optional): anchor tag for topics.md reference
- `--mode` (optional): `append` (default) or `overwrite`
- Content via stdin

## Required Flow

```bash
memory-hub write <bucket> <file> \
  --topic <name> --summary "<description>" \
  [--anchor <anchor>] [--mode append|overwrite] <<'EOF'
<markdown content>
EOF
```

## Output

JSON envelope with `data.bytes_written` and write metadata.

## Error Handling

- `INVALID_BUCKET` → invalid bucket name
- `NO_INPUT` → no stdin content provided
- `EMPTY_CONTENT` → stdin content is empty
