import os
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

def _tcp_check(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False

def _get_db_host_port():
    host = os.getenv("DB_HOST", "")
    port_str = os.getenv("DB_PORT", "5432")
    try:
        port = int(port_str)
    except ValueError:
        port = 5432
    return host, port

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/livez":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
            return

        if self.path != "/healthz":
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"not_found")
            return

        host, port = _get_db_host_port()
        ok = bool(host) and _tcp_check(host, port, timeout=2.0)

        if ok:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(503)
            self.end_headers()
            self.wfile.write(b"db_not_ready")

    def log_message(self, format, *args):
        return  # silence logs

def start_health_server():
    srv = HTTPServer(("0.0.0.0", 8081), HealthHandler)
    srv.serve_forever()

def start_health_server_in_background():
    t = threading.Thread(target=start_health_server, daemon=True)
    t.start()
    return True

if __name__ == "__main__":
    start_health_server()

