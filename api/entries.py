# Vercel 함수: /api/entries 약속(PRD.md)을 지키고, 글은 Supabase entries 표에 저장해요.
# 필요한 환경 변수: SUPABASE_URL, SUPABASE_SECRET_KEY (Vercel 프로젝트 설정에 넣어요)
# 입력 검사(read_entry)는 로컬 server.py도 같이 써요.
import json
import os
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

MAX_BODY = 8 * 1024


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def send_json(handler, status, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def now_utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def text_field(body, key, label, max_len, required):
    """앞뒤 공백을 지운 값을 돌려줘요. 문제가 있으면 ValueError(설명)를 일으켜요."""
    value = body.get(key)
    if value is None:
        if required:
            raise ValueError(f"{label}을 적어 주세요.")
        return None
    if not isinstance(value, str):
        raise ValueError(f"{label}은 문자열이어야 해요.")
    value = value.strip()
    if not value:
        if required:
            raise ValueError(f"{label}을 1자 이상 적어 주세요.")
        return None
    if len(value) > max_len:
        raise ValueError(f"{label}은 {max_len}자 이하로 적어 주세요.")
    return value


def read_entry(handler):
    """POST 본문을 읽고 검사해서 {"name", "message", "to"}를 돌려줘요. 문제가 있으면 ApiError를 일으켜요."""
    content_type = (handler.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    if content_type != "application/json":
        handler.close_connection = True
        raise ApiError(415, "JSON 형식(application/json)으로 보내 주세요.")
    try:
        length = int(handler.headers.get("Content-Length") or 0)
    except ValueError:
        length = -1
    if length < 0:
        handler.close_connection = True
        raise ApiError(400, "요청 길이가 올바르지 않아요.")
    if length > MAX_BODY:
        handler.close_connection = True
        raise ApiError(413, "본문은 8KiB 이하로 보내 주세요.")
    try:
        body = json.loads(handler.rfile.read(length).decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise ApiError(400, "JSON이 깨져 있어요.")
    if not isinstance(body, dict):
        raise ApiError(400, "JSON 객체로 보내 주세요.")
    try:
        return {
            "name": text_field(body, "name", "보내는 사람", 40, required=True),
            "message": text_field(body, "message", "칭찬 내용", 500, required=True),
            "to": text_field(body, "to", "받는 사람", 40, required=False),
        }
    except ValueError as e:
        raise ApiError(400, str(e))


# ---- Supabase (REST API, 표준 라이브러리만 써요) ----

SUPABASE_HINTS = {
    401: "SUPABASE_SECRET_KEY 값이 맞는지 확인해 주세요.",
    403: "SUPABASE_SECRET_KEY에 공개 키(anon/publishable)가 아니라 secret 키를 넣어 주세요.",
    404: "SUPABASE_URL 값이나 entries 표(supabase/schema.sql 실행)를 확인해 주세요.",
}

def supabase(method, query="", payload=None):
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SECRET_KEY", "")
    if not url or not key:
        raise ApiError(500, "서버에 Supabase 설정(SUPABASE_URL, SUPABASE_SECRET_KEY)이 없어요.")
    headers = {"apikey": key, "Content-Type": "application/json", "Prefer": "return=representation"}
    if key.startswith("eyJ"):  # 예전 service_role 키(JWT)는 Authorization 머리글도 필요해요.
        headers["Authorization"] = f"Bearer {key}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(f"{url}/rest/v1/entries{query}", data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=8) as response:
            return json.loads(response.read())
    except HTTPError as e:
        detail = e.read()[:300].decode("utf-8", "replace")
        print(f"Supabase {e.code}: {detail}", file=sys.stderr)  # Vercel Logs에서 볼 수 있어요
        hint = SUPABASE_HINTS.get(e.code, "Vercel Logs에서 자세한 내용을 확인해 주세요.")
        raise ApiError(502, f"저장소(Supabase)가 {e.code}로 거절했어요. {hint}")
    except (URLError, TimeoutError, ValueError) as e:
        print(f"Supabase 연결 실패: {e!r}", file=sys.stderr)
        raise ApiError(502, "저장소(Supabase)에 연결하지 못했어요. SUPABASE_URL 값을 확인해 주세요.")


def to_entry(row):
    try:
        created_at = datetime.fromisoformat(row["created_at"]).astimezone(timezone.utc)
        created_at = created_at.isoformat(timespec="seconds")
    except (TypeError, ValueError):
        created_at = row["created_at"]
    entry = {"id": row["id"], "name": row["name"], "message": row["message"], "created_at": created_at}
    if row.get("to_name"):
        entry["to"] = row["to_name"]
    return entry


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if urlsplit(self.path).path != "/api/entries":
            send_json(self, 404, {"error": "찾는 주소가 없어요."})
            return
        try:
            rows = supabase("GET", "?select=id,name,message,to_name,created_at&order=id.desc&limit=200")
        except ApiError as e:
            send_json(self, e.status, {"error": str(e)})
            return
        send_json(self, 200, {"entries": [to_entry(r) for r in rows]})

    def do_POST(self):
        if urlsplit(self.path).path != "/api/entries":
            send_json(self, 404, {"error": "찾는 주소가 없어요."})
            return
        try:
            entry = read_entry(self)
            rows = supabase("POST", payload={
                "name": entry["name"], "message": entry["message"],
                "to_name": entry["to"], "created_at": now_utc(),
            })
        except ApiError as e:
            send_json(self, e.status, {"error": str(e)})
            return
        send_json(self, 201, {"entry": to_entry(rows[0])})
