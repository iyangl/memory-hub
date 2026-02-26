---
name: memory-index
description: "注册知识文件到 topics.md 索引（内容由 AI 直接写入目标文件）"
tools: ["Bash", "Write"]
---

## Purpose

Register a knowledge file in the topics.md index. The AI writes file content directly, then calls this command to update the index.

## Input

- `bucket`: pm | architect | dev | qa
- `file`: filename within the bucket (must already exist)
- `--topic`: topic name for topics.md index
- `--summary`: one-line description for topics.md
- `--anchor` (optional): anchor tag for topics.md reference

## Required Flow

### Step 1: Write content directly

Use the file write tool to create or update the target file at `.memory/<bucket>/<file>`.

### Step 2: Register in index

```bash
memory-hub index <bucket> <file> --topic <name> --summary "<description>" [--anchor <anchor>]
```

## Output

JSON envelope with index metadata.

## Error Handling

- `INVALID_BUCKET` → invalid bucket name
- `FILE_NOT_FOUND` → target file does not exist (write the file first)
