#!/usr/bin/env python3
"""
Headache Log API Server
Serves static files and provides the headache log REST API.
"""

import http.server
import json
import os
import time
import urllib.parse
from pathlib import Path

PORT = int(os.environ.get("PORT", "5000"))
DATA_FILE = os.environ.get("DATA_FILE", "/app/data/headache-log.json")
STATIC_DIR = Path(__file__).parent.parent / "static"


def load_data():
    """Load existing headache entries, upgrading legacy formats."""
    # Try primary path first, fall back to local data/ if not readable
    paths_to_try = [
        DATA_FILE,
        str(Path(__file__).parent.parent / "data" / "headache-log.json")
    ]
    for path in paths_to_try:
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, IOError):
                continue
            # Upgrade legacy flat-entry format
            if data and isinstance(data[0], str):
                data = [{"id": str(i + 1), "start": t, "end": None} for i, t in enumerate(data)]
            # Upgrade old {id, timestamp} format
            if data and isinstance(data[0], dict) and "timestamp" in data[0] and "type" not in data[0]:
                data = [{"id": e["id"], "start": e["timestamp"], "end": None} for e in data]
            return data
    return []


def save_data(data):
    """Save headache entries to disk."""
    # Try configured path first, fall back to local data/ if not writable
    data_dir = os.path.dirname(DATA_FILE)
    try:
        os.makedirs(data_dir, exist_ok=True)
        Path(DATA_FILE).touch()
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except PermissionError:
        # Fall back to local ./data/ directory (local dev without Docker)
        fallback_dir = Path(__file__).parent.parent / "data"
        fallback_dir.mkdir(exist_ok=True)
        fallback_file = fallback_dir / "headache-log.json"
        fallback_file.touch()
        with open(fallback_file, "w") as f:
            json.dump(data, f, indent=2)


def ts():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


class Handler(http.server.BaseHTTPRequestHandler):
    """HTTP handler for static files + API endpoints."""

    def log_message(self, fmt, *args):
        # Suppress default logging unless debugging
        pass

    def send_json(self, code, body):
        body = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Connection", "close")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_static(self, path):
        """Serve a static file from the static directory."""
        file_path = STATIC_DIR / path if path != "/" else Path("headache.html")
        if not file_path.exists():
            file_path = STATIC_DIR / "headache.html"

        if not file_path.exists() or not file_path.is_file():
            self.send_error(404, "File not found")
            return

        mime_types = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css",
            ".js": "application/javascript",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon",
        }
        ext = file_path.suffix.lower()
        mime = mime_types.get(ext, "application/octet-stream")

        with open(file_path, "rb") as f:
            content = f.read()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/health":
            self.send_json(200, '{"status":"ok"}')
            return

        if path in ("/", "/index.html", "/headache.html"):
            self.serve_static("headache.html")
            return

        if path == "/headache-log" and self.command == "GET":
            data = load_data()
            self.send_json(200, json.dumps(data))
            return

        # Static asset
        if "/" in path:
            self.serve_static(path.lstrip("/"))
            return

        self.send_error(404, "Not found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Read POST body
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b""

        if path == "/headache-log-add":
            self._add_entry(post_data)
        elif path == "/headache-log-end":
            self._end_entry()
        elif path == "/headache-log-edit":
            self._edit_entry(post_data)
        elif path == "/headache-log-import":
            self._import_csv(post_data)
        else:
            self.send_json(404, '{"error":"unknown endpoint"}')

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        entry_id = query.get("id", [""])[0]

        if path == "/headache-log-delete":
            self._delete_entry(entry_id)
        else:
            self.send_json(404, '{"error":"unknown endpoint"}')

    def _get_entry(self, entry_id):
        data = load_data()
        for ep in data:
            if ep.get("id") == entry_id:
                return ep, data
        return None, data

    def _add_entry(self, post_data):
        """Start a new headache episode."""
        data = load_data()
        fields = {}
        try:
            fields = urllib.parse.parse_qs(post_data.decode("utf-8"))
        except Exception:
            pass

        entry_type = (fields.get("type") or [None])[0]
        pain = (fields.get("pain") or [None])[0]
        notes = (fields.get("notes") or [None])[0]

        if entry_type in ("", "null", "none"):
            entry_type = None
        if pain in ("", "null", "none"):
            pain = None
        if notes in ("", "null", "none"):
            notes = None
        if pain is not None:
            try:
                pain = int(pain)
            except Exception:
                pain = None

        entry = {
            "id": str(int(time.time() * 1000)),
            "start": ts(),
            "end": None,
            "type": entry_type,
            "pain": pain,
            "notes": notes,
        }
        data.append(entry)
        save_data(data)
        self.send_json(200, json.dumps({"ok": True, "id": entry["id"], "timestamp": entry["start"]}))

    def _end_entry(self):
        """Close the most recent open headache episode."""
        data = load_data()
        found = None
        for ep in reversed(data):
            if ep.get("end") is None:
                ep["end"] = ts()
                found = ep
                break
        if found:
            save_data(data)
        self.send_json(200, json.dumps({"ok": True, "id": found["id"] if found else None}))

    def _delete_entry(self, entry_id):
        data = load_data()
        data = [e for e in data if e.get("id") != entry_id]
        save_data(data)
        self.send_json(200, json.dumps({"ok": True}))

    def _edit_entry(self, post_data):
        """Update an existing entry: start, end, type, pain, notes."""
        fields = {}
        try:
            fields = urllib.parse.parse_qs(post_data.decode("utf-8"))
        except Exception:
            pass

        entry_id = (fields.get("id") or [""])[0]
        new_start = (fields.get("start") or [""])[0]
        new_end = (fields.get("end") or [""])[0]
        entry_type = (fields.get("type") or [None])[0]
        pain = (fields.get("pain") or [None])[0]
        notes = (fields.get("notes") or [None])[0]

        if entry_type in ("", "null", "none"):
            entry_type = None
        if pain in ("", "null", "none"):
            pain = None
        if notes in ("", "null", "none"):
            notes = None
        if not entry_id or not new_start:
            self.send_json(400, json.dumps({"ok": False, "error": "id and start are required"}))
            return

        new_end = new_end or None
        data = load_data()
        found = None
        for ep in data:
            if ep.get("id") == entry_id:
                ep["start"] = new_start
                ep["end"] = new_end
                if entry_type is not None:
                    ep["type"] = entry_type
                if pain is not None:
                    ep["pain"] = int(pain) if pain else None
                if notes is not None:
                    ep["notes"] = notes
                found = ep
                break

        if not found:
            self.send_json(404, json.dumps({"ok": False, "error": "entry not found"}))
            return

        save_data(data)
        self.send_json(200, json.dumps({"ok": True, "entry": found}))

    def _import_csv(self, post_data):
        """Import headache entries from a CSV file."""
        import csv
        import io

        text = ""
        try:
            text = post_data.decode("utf-8")
        except Exception:
            try:
                text = post_data.decode("latin-1")
            except Exception:
                pass

        if not text.strip():
            self.send_json(400, json.dumps({"ok": False, "error": "Empty or unreadable file"}))
            return

        data = load_data()
        existing_ids = {e["id"] for e in data}
        imported = 0
        skipped = 0

        reader = csv.reader(io.StringIO(text))
        header = next(reader, None)
        if not header:
            self.send_json(400, json.dumps({"ok": False, "error": "Empty CSV"}))
            return

        lower_header = [str(col).strip().lower() for col in header]
        col_index = {name: idx for idx, name in enumerate(lower_header)}

        def get_col(row, name, default=None):
            idx = col_index.get(name, -1)
            return row[idx].strip() if idx >= 0 and idx < len(row) else default

        for row in reader:
            if len(row) < 2:
                skipped += 1
                continue

            start_date = get_col(row, "start date") or get_col(row, 0)
            start_time = get_col(row, "start time") or ""
            end_date = get_col(row, "end date") or ""
            end_time = get_col(row, "end time") or ""
            entry_type = get_col(row, "type") or None
            pain = get_col(row, "pain") or None
            notes = get_col(row, "notes") or None

            if not start_date:
                skipped += 1
                continue

            # Combine date + time
            if start_time:
                start = f"{start_date}T{start_time}"
            else:
                # Try parsing as full datetime
                start = start_date
                if "T" not in start and " " in start:
                    parts = start.split(" ")
                    start = f"{parts[0]}T{parts[1]}" if len(parts) > 1 else start

            end = None
            if end_date:
                if end_time:
                    end = f"{end_date}T{end_time}"
                else:
                    end = end_date

            if pain:
                try:
                    pain = int(pain)
                except Exception:
                    pain = None

            entry_id = str(int(time.time() * 1000)) + str(imported)
            entry = {
                "id": entry_id,
                "start": start,
                "end": end,
                "type": entry_type,
                "pain": pain,
                "notes": notes,
            }
            data.append(entry)
            imported += 1

        save_data(data)
        self.send_json(200, json.dumps({"ok": True, "imported": imported, "skipped": skipped}))


if __name__ == "__main__":
    server = http.server.HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Headache Log server running on :{PORT}", flush=True)
    server.serve_forever()