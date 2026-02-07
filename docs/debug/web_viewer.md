# Web Viewer (Debug Only)

The viewer provides a lightweight, read-only web UI to inspect stored data.

## Start
```bash
python -m viewer --host 127.0.0.1 --port 8765
```

Open:
```
http://127.0.0.1:8765
```

## Notes
- Read-only access (SQLite opened in `mode=ro`).
- Use the project selector to inspect `raw_events`, `turns`, `memory_facts`, `decisions`, `decision_edges`, and `artifact_links`.
- The viewer is optional and only intended for debugging.
