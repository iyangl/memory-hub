from __future__ import annotations

import argparse
import json
import sqlite3
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

DEFAULT_ROOT = Path.home() / ".memory-hub"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Memory Hub debug web viewer")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser.parse_args()


def _db_path(root: Path, project_id: str) -> Path:
    return root / "projects" / project_id / "events.db"


def _list_projects(root: Path) -> List[str]:
    projects_dir = root / "projects"
    if not projects_dir.exists():
        return []
    names = []
    for child in projects_dir.iterdir():
        if not child.is_dir():
            continue
        if (child / "events.db").exists():
            names.append(child.name)
    return sorted(names)


def _connect_readonly(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _fetch_table(
    conn: sqlite3.Connection,
    table: str,
    limit: int,
) -> List[Dict[str, Any]]:
    rows = conn.execute(f"SELECT * FROM {table} ORDER BY rowid DESC LIMIT ?", (limit,)).fetchall()
    return [dict(row) for row in rows]


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: Any) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _html_response(handler: BaseHTTPRequestHandler, status: int, html: str) -> None:
    data = html.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _index_html(project_id: Optional[str], root_dir: Path) -> str:
    pid = project_id or ""
    root_display = str(root_dir)
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Memory Hub Viewer</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 20px; }}
    h1 {{ margin-bottom: 8px; }}
    .section {{ margin-top: 16px; }}
    select, button, input {{ margin-right: 8px; }}
    pre {{ background: #f5f5f5; padding: 12px; overflow: auto; max-height: 320px; }}
    .row {{ margin-bottom: 8px; }}
  </style>
</head>
<body>
  <h1>Memory Hub Viewer</h1>
  <div class=\"row\">
    <strong>Root:</strong>
    <code id=\"rootPath\">{root_display}</code>
  </div>
  <div class=\"row\">
    <label>Project:</label>
    <select id=\"projectSelect\"></select>
    <button onclick=\"applyProject()\">Load</button>
    <label>Limit:</label>
    <input id=\"limitInput\" type=\"number\" value=\"100\" min=\"1\" max=\"1000\" />
  </div>

  <div id=\"emptyState\" class=\"section\" style=\"display:none;\"></div>
  <div id=\"content\"></div>

  <script>
    const projectSelect = document.getElementById('projectSelect');
    const content = document.getElementById('content');
    const emptyState = document.getElementById('emptyState');
    const limitInput = document.getElementById('limitInput');
    const initialProject = {json.dumps(pid)};

    async function loadProjects() {{
      const res = await fetch('/api/projects');
      const data = await res.json();
      projectSelect.innerHTML = '';
      emptyState.style.display = 'none';
      data.projects.forEach(p => {{
        const opt = document.createElement('option');
        opt.value = p;
        opt.textContent = p;
        if (p === initialProject) opt.selected = true;
        projectSelect.appendChild(opt);
      }});
      if (!data.projects.length) {{
        emptyState.style.display = 'block';
        emptyState.innerHTML = `
          <h2>No projects found</h2>
          <p>Current root: <code>{root_display}</code></p>
          <p>If you wrote data from a different environment (WSL vs Windows), start the viewer with the same <code>--root</code>.</p>
        `;
        content.innerHTML = '';
        return;
      }}
      if (data.projects.length && !initialProject) {{
        projectSelect.value = data.projects[0];
      }}
    }}

    function applyProject() {{
      const pid = projectSelect.value;
      const limit = parseInt(limitInput.value || '100', 10);
      const url = new URL(window.location.href);
      url.searchParams.set('project_id', pid);
      url.searchParams.set('limit', String(limit));
      window.history.replaceState(null, '', url.toString());
      loadData(pid, limit);
    }}

    async function loadData(pid, limit) {{
      content.innerHTML = '';
      const sections = [
        ['raw_events', '/api/raw_events'],
        ['turns', '/api/turns'],
        ['memory_facts', '/api/memory_facts'],
        ['decisions', '/api/decisions'],
        ['decision_edges', '/api/decision_edges'],
        ['artifact_links', '/api/artifact_links'],
      ];

      for (const [name, endpoint] of sections) {{
        const res = await fetch(`${{endpoint}}?project_id=${{encodeURIComponent(pid)}}&limit=${{limit}}`);
        const data = await res.json();
        const div = document.createElement('div');
        div.className = 'section';
        div.innerHTML = `<h2>${{name}} (${{data.items.length}})</h2><pre>${{JSON.stringify(data.items, null, 2)}}</pre>`;
        content.appendChild(div);
      }}
    }}

    loadProjects().then(() => {{
      if (projectSelect.value) {{
        const url = new URL(window.location.href);
        const limit = parseInt(url.searchParams.get('limit') || '100', 10);
        limitInput.value = String(limit);
        loadData(projectSelect.value, limit);
      }}
    }});
  </script>
</body>
</html>"""


class ViewerHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/":
            project_id = query.get("project_id", [""])[0] or None
            _html_response(self, 200, _index_html(project_id, self.server.root_dir))  # type: ignore[attr-defined]
            return

        if path == "/api/projects":
            projects = _list_projects(self.server.root_dir)  # type: ignore[attr-defined]
            _json_response(self, 200, {"projects": projects})
            return

        if path.startswith("/api/"):
            self._handle_table_api(path, query)
            return

        _json_response(self, 404, {"error": "not found"})

    def _handle_table_api(self, path: str, query: Dict[str, List[str]]) -> None:
        project_id = query.get("project_id", [""])[0]
        if not project_id:
            _json_response(self, 400, {"error": "project_id is required"})
            return

        limit_raw = query.get("limit", ["100"])[0]
        try:
            limit = max(1, min(int(limit_raw), 1000))
        except ValueError:
            limit = 100

        table_map = {
            "/api/raw_events": "raw_events",
            "/api/turns": "turns",
            "/api/memory_facts": "memory_facts",
            "/api/decisions": "decisions",
            "/api/decision_edges": "decision_edges",
            "/api/artifact_links": "artifact_links",
        }
        table = table_map.get(path)
        if not table:
            _json_response(self, 404, {"error": "unknown api"})
            return

        db_path = _db_path(self.server.root_dir, project_id)  # type: ignore[attr-defined]
        if not db_path.exists():
            _json_response(self, 404, {"error": "db not found"})
            return

        conn = _connect_readonly(db_path)
        try:
            items = _fetch_table(conn, table, limit)
        finally:
            conn.close()

        _json_response(self, 200, {"items": items})

    def log_message(self, format: str, *args: Any) -> None:
        return


class ViewerServer(HTTPServer):
    def __init__(self, server_address, handler_class, root_dir: Path):
        super().__init__(server_address, handler_class)
        self.root_dir = root_dir


def main() -> None:
    args = parse_args()
    server = ViewerServer((args.host, args.port), ViewerHandler, args.root)
    print(f"viewer listening on http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
