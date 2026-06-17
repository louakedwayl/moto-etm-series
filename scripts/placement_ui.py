#!/usr/bin/env python3
import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from place_questions import (
    DEFAULT_ASSETS_DIR,
    DEFAULT_WORK_DIR,
    apply_placements,
    build_question_index,
    parse_placement,
)


ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"


def json_response(handler, status, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def parse_lines(text):
    placements = []
    errors = []
    seen = set()

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue

        try:
            question_id, serie_number = parse_placement(line)
        except ValueError as error:
            errors.append({"line": line_number, "text": raw_line, "message": str(error)})
            continue

        key = (question_id, serie_number)
        duplicate = key in seen
        seen.add(key)
        placements.append(
            {
                "line": line_number,
                "question": question_id,
                "serie": serie_number,
                "duplicate": duplicate,
            }
        )

    return placements, errors


def first_statement_text(question):
    statements = question.get("statements", [])
    if statements and isinstance(statements[0], dict):
        return statements[0].get("text", "")
    return ""


class Handler(BaseHTTPRequestHandler):
    server_version = "PlacementUI/1.0"

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            return self.serve_file(WEB_DIR / "index.html", "text/html; charset=utf-8")
        if path == "/app.js":
            return self.serve_file(WEB_DIR / "app.js", "application/javascript; charset=utf-8")
        if path == "/styles.css":
            return self.serve_file(WEB_DIR / "styles.css", "text/css; charset=utf-8")
        if path == "/api/status":
            return self.handle_status()
        if path.startswith("/api/series/"):
            return self.handle_serie(path.rsplit("/", 1)[-1])

        self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/preview":
            return self.handle_preview()
        if path == "/api/apply":
            return self.handle_apply()

        self.send_error(404)

    def log_message(self, format, *args):
        print(format % args, file=sys.stderr)

    def serve_file(self, path, content_type):
        try:
            body = path.read_bytes()
        except FileNotFoundError:
            self.send_error(404)
            return

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json_body(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw or "{}")

    def handle_status(self):
        data_dir = self.server.work_dir / "data"
        series = []
        for path in sorted(data_dir.glob("serie*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            series.append(
                {
                    "id": data.get("id", path.stem),
                    "file": str(path.relative_to(self.server.work_dir)),
                    "count": len(data.get("questions", [])),
                }
            )
        json_response(self, 200, {"series": series})

    def handle_serie(self, serie_id):
        try:
            if not serie_id.startswith("serie"):
                serie_id = f"serie{int(serie_id)}"
            if not serie_id.removeprefix("serie").isdigit():
                raise ValueError("serie invalide")

            path = self.server.work_dir / "data" / f"{serie_id}.json"
            if not path.exists():
                return json_response(
                    self,
                    404,
                    {"error": f"{serie_id} introuvable", "serie": serie_id, "questions": []},
                )

            data = json.loads(path.read_text(encoding="utf-8"))
            questions = []
            for question in data.get("questions", []):
                questions.append(
                    {
                        "id": question.get("id"),
                        "scene": question.get("scene", ""),
                        "type": question.get("type", "question"),
                        "question": question.get("question", ""),
                        "text": question.get("question") or first_statement_text(question),
                    }
                )
        except Exception as error:
            return json_response(self, 400, {"error": str(error)})

        json_response(
            self,
            200,
            {
                "id": data.get("id", serie_id),
                "file": str(path.relative_to(self.server.work_dir)),
                "count": len(questions),
                "questions": questions,
            },
        )

    def handle_preview(self):
        try:
            payload = self.read_json_body()
            placements, errors = parse_lines(payload.get("text", ""))
        except Exception as error:
            return json_response(self, 400, {"error": str(error)})

        json_response(self, 200, {"placements": placements, "errors": errors})

    def handle_apply(self):
        try:
            payload = self.read_json_body()
            placements_preview, errors = parse_lines(payload.get("text", ""))
            if errors:
                return json_response(self, 400, {"errors": errors})

            placements = [(item["question"], item["serie"]) for item in placements_preview]
            question_index = build_question_index(self.server.assets_dir)
            added, skipped, moved = apply_placements(
                self.server.work_dir,
                question_index,
                placements,
                move=bool(payload.get("move")),
                dry_run=bool(payload.get("dryRun")),
            )
        except Exception as error:
            return json_response(self, 400, {"error": str(error)})

        json_response(
            self,
            200,
            {
                "added": [{"question": question_id, "serie": serie} for question_id, serie in added],
                "skipped": [
                    {"question": question_id, "serie": serie, "reason": reason}
                    for question_id, serie, reason in skipped
                ],
                "moved": [
                    {"question": question_id, "from": str(path.relative_to(self.server.work_dir))}
                    for question_id, path in moved
                ],
                "dryRun": bool(payload.get("dryRun")),
            },
        )


class Server(ThreadingHTTPServer):
    def __init__(self, server_address, handler_class, work_dir, assets_dir):
        super().__init__(server_address, handler_class)
        self.work_dir = work_dir
        self.assets_dir = assets_dir


def main():
    parser = argparse.ArgumentParser(description="UI locale pour placer les questions dans les series.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    parser.add_argument("--assets-dir", type=Path, default=DEFAULT_ASSETS_DIR)
    args = parser.parse_args()

    server = Server((args.host, args.port), Handler, args.work_dir, args.assets_dir)
    print(f"UI disponible sur http://{args.host}:{args.port}")
    print("Ctrl+C pour arreter.")
    server.serve_forever()


if __name__ == "__main__":
    main()
