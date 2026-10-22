# 칭찬 릴레이

칭찬을 받은 사람이 다음 바통을 이어받아 또 다른 사람을 칭찬하는 작은 웹앱이에요. 가장 최근 칭찬의 "받는 사람"(선택 칸)이 지금 바통을 든 사람이 되고, 글쓰기 칸의 "보내는 사람"에 미리 채워져요.

## 실행하기

파이썬 기본 모듈만 써서 따로 설치할 것이 없어요.

```bash
python3 server.py
```

그다음 브라우저에서 http://localhost:8080 을 열어요. 다른 포트나 DB 파일을 쓰려면 `python3 server.py --port 9000 --db data/test.db`처럼 켜요. 끌 때는 터미널에서 `Ctrl+C`를 눌러요.

## 확인하기

수업 확인 도구로 API 약속을 검사해요. 임시 포트와 임시 DB로 서버를 띄워서, 서버를 다시 켠 뒤에도 글이 남는지까지 봐요.

```bash
python3 ~/Downloads/dbinc-ai-course/labs/guestbook/smoke_test.py --app server.py
```

| 파일 | 하는 일 |
| --- | --- |
| `server.py` | 로컬 전용이에요. 화면(`index.html`)을 보여 주고, 칭찬을 SQLite DB(`data/praise.db`의 `entries` 표)에 저장하고 읽어 와요 |
| `api/entries.py` | 배포(Vercel)용 함수예요. 같은 API 약속으로 Supabase에 저장해요. 입력 검사 코드는 `server.py`도 같이 써요 |
| `index.html` | 바통, 글쓰기 칸, 칭찬 목록이 있는 화면이에요 |
| `supabase/schema.sql` | Supabase에 `entries` 표를 만드는 SQL이에요 |
| `.vercelignore` | Vercel에 `index.html`과 `api/`만 올리게 해요 |

## 배포하기 (Vercel + Supabase)

```
브라우저 ─ index.html (Vercel 정적 파일)
   │  fetch /api/entries
   ▼
api/entries.py (Vercel Python 함수) ─ 비밀 키는 Vercel 환경 변수에만
   ▼
Supabase Postgres의 entries 표
```

1. **Supabase**: 새 프로젝트를 만들고, SQL Editor에 `supabase/schema.sql`을 붙여 넣어 Run을 눌러요. 그다음 Project Settings → API에서 Project URL과 **secret 키**(예전 이름 service_role)를 복사해요.
2. **GitHub**: 이 폴더를 커밋하고 새 GitHub 저장소에 올려요.
3. **Vercel**: Add New → Project에서 그 저장소를 가져와요. Framework Preset은 Other로 둬요. 배포하기 전에 Environment Variables에 아래 두 값을 넣어요.
   - `SUPABASE_URL`: Project URL (예: `https://abcd1234.supabase.co`)
   - `SUPABASE_SECRET_KEY`: secret 키
4. 배포가 끝나면 받은 주소로 확인 도구를 돌려요. 검사용 글 3개가 Supabase에 남아요.

```bash
python3 ~/Downloads/dbinc-ai-course/labs/guestbook/smoke_test.py --url https://내-앱.vercel.app
```

- secret 키는 표를 마음대로 다룰 수 있는 열쇠예요. Vercel 환경 변수에만 넣고, `index.html`이나 커밋하는 파일에는 절대 적지 않아요.
- `/api/entries`가 아닌 없는 주소는 Vercel이 자체 404 화면으로 답해요. 상태 코드는 404라서 확인 도구는 통과해요.

## API

[PRD.md](PRD.md)의 약속을 따라요.

| 요청 | 하는 일 |
| --- | --- |
| `GET /api/entries` | 200과 `{"entries": [...]}`, 최신 글부터 최대 200개를 돌려줘요 |
| `POST /api/entries` | `{"name", "message", "to"}`를 저장하고 201과 `{"entry": {...}}`를 돌려줘요. `to`는 빼도 돼요 |

- `name`(보내는 사람)과 `to`(받는 사람)는 40자, `message`(칭찬 내용)는 500자까지예요. 앞뒤 공백은 지워요.
- 실패하면 `{"error": "설명"}`으로 답해요. 잘못된 값과 깨진 JSON은 400, 8KiB가 넘는 본문은 413, JSON이 아닌 형식은 415, 없는 주소는 404예요.
