#!/usr/bin/env python3
"""
SIPE Local PoC - Mock Authorization & Protected Resource Server
Conforms to WorkOS auth.md and RFC 8414 metadata discovery.
Runs with standard Python 3 library (no external pip dependencies required).
"""

import http.server
import socketserver
import json
import os
import argparse
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

class SIPEServerHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        host = self.headers.get("Host", f"localhost:{self.server.server_port}")
        base_url = f"http://{host}"

        if self.path == "/auth.md":
            self._serve_file(os.path.join(STATIC_DIR, "auth.md"), "text/markdown; charset=utf-8")
        elif self.path == "/.well-known/oauth-protected-resource":
            prm_path = os.path.join(STATIC_DIR, "oauth-prm.json")
            with open(prm_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["resource"] = f"{base_url}/data"
            data["authorization_servers"] = [base_url]
            data["resource_documentation"] = f"{base_url}/auth.md"
            self._send_json(data)
        elif self.path == "/.well-known/oauth-authorization-server":
            auth_path = os.path.join(STATIC_DIR, "oauth-auth-server.json")
            with open(auth_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["issuer"] = base_url
            data["authorization_endpoint"] = f"{base_url}/oauth/authorize"
            data["token_endpoint"] = f"{base_url}/oauth/token"
            data["jwks_uri"] = f"{base_url}/.well-known/jwks.json"
            data["agent_auth"]["skill"] = f"{base_url}/static/SIPE_SKILL.md"
            data["agent_auth"]["identity_endpoint"] = f"{base_url}/agent/identity"
            data["agent_auth"]["claim_endpoint"] = f"{base_url}/agent/claim"
            data["agent_auth"]["events_endpoint"] = f"{base_url}/agent/events"
            self._send_json(data)
        elif self.path == "/static/SIPE_SKILL.md":
            self._serve_file(os.path.join(STATIC_DIR, "SIPE_SKILL.md"), "text/markdown; charset=utf-8")
        elif self.path == "/data":
            auth_header = self.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer sipe-authenticated-token"):
                self.send_response(401)
                prm_url = f"{base_url}/.well-known/oauth-protected-resource"
                self.send_header("WWW-Authenticate", f'Bearer resource_metadata="{prm_url}"')
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                err = {
                    "error": "unauthorized",
                    "error_description": "Protected resource requires authenticated agent claim per auth.md",
                    "resource_metadata": prm_url
                }
                self.wfile.write(json.dumps(err, indent=2).encode("utf-8"))
            else:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                res = {
                    "status": "success",
                    "message": "Access granted to 4NDR0NET telemetry stream.",
                    "telemetry": {
                        "delta_BCH": 0.4147,
                        "q_EA": -0.7803,
                        "RSB_triples": 187460,
                        "z_score": 29.90,
                        "phase_lock": "VERIFIED"
                    }
                }
                self.wfile.write(json.dumps(res, indent=2).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/agent/claim":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
            try:
                payload = json.loads(body)
            except Exception:
                payload = {"raw": body}
            
            print(f"\n[SERVER] Received Agent Claim: {json.dumps(payload, indent=2)}")
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            response = {
                "token_type": "Bearer",
                "access_token": "sipe-authenticated-token-xyz999",
                "expires_in": 3600,
                "scope": "read:data verify:kernel",
                "message": "Claim accepted. Kernel verification registered."
            }
            self.wfile.write(json.dumps(response, indent=2).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def _serve_file(self, filepath, content_type):
        if not os.path.exists(filepath):
            self.send_response(404)
            self.end_headers()
            return
        with open(filepath, "rb") as f:
            content = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, data):
        content = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

def run(port=8080):
    server_address = ("", port)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(server_address, SIPEServerHandler) as httpd:
        print(f"============================================================")
        print(f"SIPE Mock Protected Server running at http://localhost:{port}")
        print(f"  * Discovery Doc : http://localhost:{port}/auth.md")
        print(f"  * PRM Metadata  : http://localhost:{port}/.well-known/oauth-protected-resource")
        print(f"  * Auth Server   : http://localhost:{port}/.well-known/oauth-authorization-server")
        print(f"  * Protected URL : http://localhost:{port}/data")
        print(f"============================================================")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SIPE PoC Server")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on (default: 8080)")
    args = parser.parse_args()
    run(port=args.port)
