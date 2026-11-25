"""Local editor, sharing the same rehearsal function as the CLI."""
import json
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from .project import ROOT, example_document, parse_project, rehearse


class EditorHandler(SimpleHTTPRequestHandler):
    def send_json(self, status, value):
        body = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if urlsplit(self.path).path == "/api/example":
            self.send_json(HTTPStatus.OK, example_document())
        else:
            super().do_GET()

    def do_POST(self):
        endpoint = urlsplit(self.path).path
        if endpoint not in ("/api/rehearse", "/api/validate"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length <= 0:
                raise ValueError("请求中缺少工程 JSON")
            project = parse_project(json.loads(self.rfile.read(length)))
            if endpoint == "/api/rehearse":
                sim = rehearse(project.stage, project.show)
                result = {"events": sim.events, "duration_s": sim.time_s}
            else:
                result = {"ok": True}
        except (ValueError, KeyError, RuntimeError, TypeError, OverflowError) as exc:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        self.send_json(HTTPStatus.OK, result)


def serve(port):
    handler = partial(EditorHandler, directory=str(ROOT / "editor"))
    with ThreadingHTTPServer(("127.0.0.1", port), handler) as httpd:
        print(f"编辑器已启动 http://127.0.0.1:{httpd.server_port}/  （Ctrl+C 退出）", flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
