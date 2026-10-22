# 칭찬 릴레이 서버: 파이썬 기본 모듈만 써요 (설치할 것 없음).
# 실행: python3 server.py  →  http://localhost:8080
# 옵션: --port 9000 (또는 PORT 환경 변수), --db 다른/경로.db
# 로컬에서는 SQLite에 저장해요. 배포(Vercel)에서는 api/entries.py가 Supabase에 저장해요.
import argparse
import os
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from api.entries import ApiError, now_utc, read_entry, send_json

BASE = Path(__file__).resolve().parent
DB_PATH = BASE / "data" / "praise.db"
INDEX = BASE / "index.html"
HOST, PORT = "127.0.0.1", int(os.environ.get("PORT", "8080"))


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                message TEXT NOT NULL,
                "to" TEXT,
                created_at TEXT NOT NULL
            )"""
        )


def to_entry(row):
    entry = dict(row)
    if entry["to"] is None:
        del entry["to"]
    return entry


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlsplit(self.path).path
        if path in ("/", "/index.html"):
            body = INDEX.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/entries":
            with connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM entries ORDER BY id DESC LIMIT 200"
                ).fetchall()
            send_json(self, 200, {"entries": [to_entry(r) for r in rows]})
        else:
            send_json(self, 404, {"error": "찾는 주소가 없어요."})

    def do_POST(self):
        if urlsplit(self.path).path != "/api/entries":
            send_json(self, 404, {"error": "찾는 주소가 없어요."})
            return
        try:
            entry = read_entry(self)
        except ApiError as e:
            send_json(self, e.status, {"error": str(e)})
            return
        with connect() as conn:
            cur = conn.execute(
                'INSERT INTO entries (name, message, "to", created_at) VALUES (?, ?, ?, ?)',
                (entry["name"], entry["message"], entry["to"], now_utc()),
            )
            row = conn.execute("SELECT * FROM entries WHERE id = ?", (cur.lastrowid,)).fetchone()
        send_json(self, 201, {"entry": to_entry(row)})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="칭찬 릴레이 서버")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    args = parser.parse_args()
    DB_PATH = args.db.resolve()
    init_db()
    print(f"칭찬 릴레이 서버가 켜졌어요: http://localhost:{args.port}")
    ThreadingHTTPServer((HOST, args.port), Handler).serve_forever()
