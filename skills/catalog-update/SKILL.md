---
name: catalog-update
description: "更新代码模块索引（catalog/modules/* 和 topics.md 代码模块部分）"
tools: ["Bash"]
---

## Purpose

Update the code module index from AI-generated JSON. Only touches the code modules section of topics.md, not the knowledge files section.

## Input

JSON via stdin with schema:

```json
{
  "modules": [
    {
      "name": "module-name",
      "summary": "One-line description",
      "files": [
        {"path": "src/file.py", "description": "What this file does"}
      ]
    }
  ]
}
```

## Required Flow

```bash
memory-hub catalog-update <<'EOF'
<modules JSON>
EOF
```

Automatically triggers `catalog.repair` after completion.

## Output

JSON envelope with `data.modules_written`, `data.modules_deleted`, and repair results.

## Error Handling

- `NO_INPUT` → no stdin provided
- `INVALID_JSON` → stdin is not valid JSON
- `INVALID_SCHEMA` → `modules` is not an array
