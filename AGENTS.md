# Agent Guidance

Goal: log every dialog turn to Memory Hub.

## Required
After completing each user request, log the full turn (user + assistant) by calling:

```
python scripts/log_turn_pair.py --project-id memory-hub --session-id codex --user "<USER_TEXT>" --assistant "<ASSISTANT_TEXT>"
```

Notes:
- If the text is long or contains newlines, write it to temp files and use:
  - `--user-file /path/to/user.txt`
  - `--assistant-file /path/to/assistant.txt`
- If logging fails, state the failure in the response.
