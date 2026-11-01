import os
import sys
import json
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

# Set working directory to APP folder
APP_DIR = Path(__file__).parent.resolve()
os.chdir(APP_DIR)

from runner import run_query_pipeline
from loader import discover_registry_tools

class LangGraphHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(APP_DIR), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/tools":
            tools = discover_registry_tools("registry/tools")
            tools_data = []
            for t in tools:
                tools_data.append({
                    "name": t.name,
                    "description": t.description,
                    "args_schema": t.args_schema.schema() if t.args_schema else {}
                })
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(tools_data).encode("utf-8"))
            return

        # Default static file handling
        if parsed.path in ["", "/"]:
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/run":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            
            try:
                data = json.loads(body)
                query = data.get("query", "").strip()
                if not query:
                    self._send_error_response("Query cannot be empty", 400)
                    return

                # Execute pipeline and capture animation steps
                result = run_query_pipeline(query)

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps(result).encode("utf-8"))
            except Exception as e:
                import traceback
                traceback.print_exc()
                err_str = str(e)
                code = 500
                if any(k in err_str for k in ["429", "RESOURCE_EXHAUSTED", "ResourceExhausted"]) or "quota" in err_str.lower() or "too many requests" in err_str.lower():
                    code = 429
                self._send_error_response(err_str, code)
            return

        self._send_error_response("Not found", 404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _send_error_response(self, message: str, code: int = 500):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "error", "code": code, "message": message}).encode("utf-8"))

def start_server(port: int = 8000, auto_open: bool = False):
    server_address = ("", port)
    try:
        httpd = HTTPServer(server_address, LangGraphHandler)
    except OSError:
        # Port already in use, try port 8001
        port = port + 1
        server_address = ("", port)
        httpd = HTTPServer(server_address, LangGraphHandler)

    url = f"http://localhost:{port}"
    print(f"\n=======================================================")
    print(f" [>>] LangGraph Visualizer running at: {url}")
    print(f" Press Ctrl+C to stop the server.")
    print(f"=======================================================\n")

    if auto_open:
        webbrowser.open(url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        httpd.server_close()

if __name__ == "__main__":
    port = 8000
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])
    start_server(port=port)
