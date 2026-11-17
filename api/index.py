"""Vercel WSGI serverless bridge delegating requests into ArthaLedgerHandler."""
from __future__ import annotations

import io
import sys
import traceback
import urllib.parse
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import ArthaLedgerHandler


class _DummyServer:
    server_name = "vercel"
    server_port = 443


def app(environ, start_response):
    """Standard WSGI callable bridging Vercel Serverless requests into ArthaLedgerHandler."""
    try:
        method = environ.get("REQUEST_METHOD", "GET")
        path = environ.get("PATH_INFO", "/")
        query = environ.get("QUERY_STRING", "")
        full_path = f"{path}?{query}" if query else path

        parsed = urllib.parse.parse_qs(query)
        if "__artha_path__" in parsed:
            real_path = parsed["__artha_path__"][0]
            remaining = [
                f"{urllib.parse.quote_plus(k)}={urllib.parse.quote_plus(v)}"
                for k, vals in parsed.items()
                if k != "__artha_path__"
                for v in vals
            ]
            clean_q = "&".join(remaining)
            full_path = f"{real_path}?{clean_q}" if clean_q else real_path
        elif environ.get("HTTP_X_FORWARDED_URI") and environ["HTTP_X_FORWARDED_URI"].startswith("/api"):
            full_path = environ["HTTP_X_FORWARDED_URI"]
        elif environ.get("REQUEST_URI") and environ["REQUEST_URI"].startswith("/api"):
            full_path = environ["REQUEST_URI"]

        lines = [f"{method} {full_path} HTTP/1.1"]
        for key, val in environ.items():
            if key.startswith("HTTP_"):
                header_name = key[5:].replace("_", "-").title()
                lines.append(f"{header_name}: {val}")
            elif key in ("CONTENT_TYPE", "CONTENT_LENGTH") and val:
                header_name = key.replace("_", "-").title()
                lines.append(f"{header_name}: {val}")

        header_bytes = ("\r\n".join(lines) + "\r\n\r\n").encode("utf-8")
        body_stream = environ.get("wsgi.input")
        content_len = int(environ.get("CONTENT_LENGTH") or 0)
        body_bytes = body_stream.read(content_len) if (body_stream and content_len > 0) else b""

        req_bytes = header_bytes + body_bytes
        rfile = io.BytesIO(req_bytes)
        wfile = io.BytesIO()

        class _MockSocket:
            def makefile(self, mode, *args, **kwargs):
                if "b" in mode:
                    return rfile if "r" in mode else wfile
                return rfile

            def sendall(self, data):
                wfile.write(data)

        ArthaLedgerHandler(_MockSocket(), ("127.0.0.1", 80), _DummyServer())

        res_bytes = wfile.getvalue()
        if not res_bytes:
            start_response("500 Internal Server Error", [("Content-Type", "text/plain")])
            return [b"Empty response from ArthaLedger handler"]

        header_end = res_bytes.find(b"\r\n\r\n")
        if header_end == -1:
            start_response("200 OK", [("Content-Type", "text/html")])
            return [res_bytes]

        headers_part = res_bytes[:header_end].decode("iso-8859-1")
        response_body = res_bytes[header_end + 4:]
        header_lines = headers_part.split("\r\n")
        status_code = header_lines[0].split(" ", 1)[1] if " " in header_lines[0] else "200 OK"
        hop_by_hop = {
            "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
            "te", "trailers", "transfer-encoding", "upgrade",
        }
        response_headers = []
        has_len = False
        for line in header_lines[1:]:
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            kc, vc = k.strip(), v.strip()
            if kc.lower() in hop_by_hop:
                continue
            if kc.lower() == "content-length":
                has_len = True
            response_headers.append((kc, vc))
        if not has_len:
            response_headers.append(("Content-Length", str(len(response_body))))

        start_response(status_code, response_headers)
        return [response_body]
    except Exception:
        tb = traceback.format_exc()
        start_response("500 Internal Server Error", [("Content-Type", "text/plain; charset=utf-8")])
        return [f"ArthaLedger Serverless Exception:\n{tb}".encode("utf-8")]
