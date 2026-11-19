# 시스템 아키텍처 설계서 (Architecture Design)

| 항목 | 내용 |
| :--- | :--- |
| 프로젝트 | voda-voca (보다보카) |
| 문서 종류 | Architecture Design (`개발방법론.md` §2.3, 필수 산출물) |
| 기준 문서 | `docs/voda-voca_Requirement_Spec_v2.2_261119.md` (REQ-101, 102, 106, 107, 112, 116, 117, 121), `docs/voda-voca_Data_Design_v2.2_261119.md`, `docs/voda-voca_API_Integration_Spec_v2.2_261119.md` |
| 버전 / 상태 | v1.0 / **승인 (Approved, 2026-11-19)** |
| 작성일 | 2026-11-19 |
| 기준 코드 | `main` 브랜치, SRS 1~4단계(`source=due` 오늘 복습 포함) 반영 |
| 산출물 경로 | `docs/voda-voca_Architecture_Design_v1.0_261119.md` |
| 관련 결정 | `docs/` 의 Decision Records (ADR-001 세션, ADR-002 bcrypt, ADR-004~) |

> **작성 방법**: 이 문서는 추정 없이 `docker/docker-compose.yml`, `src/backend/main.py`, `core/`, `db/`, `README.md`, `src/frontend/index.html` 과 각 모듈의 소스를 직접 읽어 현재 구현을 기술했다. 설계서가 v1.0 에서야 생긴 것은 방법론 §2.3 이 [필수]로 정한 산출물이 그동안 없었기 때문이며, 이 문서는 **새 설계가 아니라 현행 구조의 기록**이다.

---

## 1. 목적과 범위

보다보카의 **실행 구조**(어떤 프로세스·컨테이너가 어디서 돌고 서로 어떻게 통신하는가)와 **소스 구조**(계층과 의존 방향)를 정의한다. 테이블 규격은 데이터 설계서, 엔드포인트 규격은 인터페이스 정의서, 화면 규격은 UI/UX 설계서가 정하며 이 문서는 되풀이하지 않는다.

## 2. 설계 원칙

| # | 원칙 | 근거 |
| :-: | :--- | :--- |
| P1 | **빌드 없는 프론트엔드**: HTML, ES 모듈, CDN 라이브러리만 쓴다. 번들러·npm 런타임 의존성이 없다 | CLAUDE.md §1 |
| P2 | **단일 출처(same-origin)**: API 와 정적 프론트를 한 FastAPI 프로세스가 서빙한다 | ADR-001 (쿠키 인증, CORS·CSRF 면적 최소화) |
| P3 | **DB 는 컨테이너, 앱은 호스트**: 데이터 계층만 Docker 로 격리한다 | REQ-116, CLAUDE.md §4-7 |
| P4 | **비동기 I/O**: 라우터부터 DB 드라이버까지 async | REQ-101 |
| P5 | **스키마는 Alembic 으로만 변경** | REQ-107 |
| P6 | **서버가 판정, 클라이언트는 표시**: 정답 채점·통계·숙련·SRS 일정은 서버에서 계산한다 | Data Design D16, D17, D15 |
| P7 | **콘텐츠와 학습 상태 분리**: 표준 단어장은 읽기 전용 공용 데이터, 사용자는 진행 상태만 소유 | Data Design D10 |

## 3. 시스템 컨텍스트

```text
 [사용자 브라우저 (모바일 우선, Chrome/Edge 최신)]
        │  HTTP (same-origin, 세션 쿠키 voda_session)
        │  ├─ GET /, /css/*, /js/*     정적 프론트엔드
        │  ├─ /api/*                   REST API (JSON)
        │  └─ GET /health              프로세스·DB 헬스체크
        ▼
 [WSL2 Ubuntu 24.04 호스트]
   └─ uvicorn (FastAPI, 단일 프로세스) :8000
        │  asyncmy (MySQL 프로토콜, .env 의 MYSQL_HOST:MYSQL_PORT)
        ▼
 [Docker 컨테이너 voda-voca-mysql (MySQL 8.0)] :3306
   └─ 볼륨 voda-voca-mysql-data (utf8mb4, utf8mb4_0900_ai_ci, +09:00)

 [외부 CDN] (브라우저가 직접 받음, 서버는 관여하지 않음)
   jsdelivr: Pretendard, Paperlogy, SweetAlert2 / unpkg: Lucide / Tailwind Play CDN
```

- **행위자**: 일반 사용자 한 종류. 관리자 역할은 1차에서 제외했다 (요구사항 Q8).
- **외부 시스템**: 서버가 호출하는 외부 서비스는 없다. 외부 의존은 브라우저가 받는 CDN 자산뿐이다 (§9 제약 참조).
- 발음 듣기는 브라우저의 Web Speech API, 효과음은 Web Audio 합성이라 서버나 음원 파일이 필요 없다.

## 4. 배포(실행) 토폴로지

| 구성요소 | 실행 위치 | 정의 파일 | 포트 | 비고 |
| :--- | :--- | :--- | :-: | :--- |
| MySQL 8.0 | Docker 컨테이너 `voda-voca-mysql` | `docker/docker-compose.yml` | `${MYSQL_PORT:-3306}` | `restart: unless-stopped`, `mysqladmin ping` 헬스체크, 시작 유예 30초 |
| FastAPI 앱 | WSL2 호스트의 `.venv` (uvicorn) | `src/backend/main.py` | 8000 (개발 기본) | **컨테이너화하지 않았다.** Dockerfile 이 없다 |
| 정적 프론트엔드 | 위 FastAPI 프로세스 | `src/frontend/` | 8000 | `StaticFiles(html=True)` 를 `/` 에 마운트 |

기동 순서: `docker compose up -d`(DB, healthy 대기) → `alembic upgrade head` → `uvicorn`. 앱 시작(lifespan) 시 표준 단어장 시드를 DB 에 반영한다.

**설정 주입**: 모든 값은 루트 `.env` 또는 OS 환경 변수 → `core/config.py` 의 `Settings`(pydantic-settings). 저장소에는 `.env.example` 만 둔다 (REQ-112).

| 변수 | 사용처 |
| :--- | :--- |
| `MYSQL_HOST/PORT/DATABASE/USER/PASSWORD` | 앱의 비동기 접속 URL (`URL.create`, 비밀번호 특수문자 안전) |
| `MYSQL_ROOT_PASSWORD`, `TZ` | 컨테이너 초기화·시간대 (앱은 무시) |
| `COOKIE_SECURE` | 세션 쿠키 Secure 속성 (HTTPS 배포 시 true) |
| `SESSION_TTL_DAYS`(기본 14), `BCRYPT_ROUNDS`(기본 12) | 코드 기본값, 필요 시 환경 변수로 덮어씀 |

## 5. 소프트웨어 구조

### 5.1 백엔드 계층

```text
HTTP 요청
  → routers/      얇은 계층: 경로, 인증 의존성, 입력/출력 스키마 연결, 상태 코드 변환
  → services/     비즈니스 규칙: 출제·채점·SRS·통계·북마크·인증. 트랜잭션 경계
  → models/       SQLAlchemy 2.x ORM (비동기)
  → db/session.py 엔진·세션 팩토리, 요청당 1세션 (get_db_session)
  → MySQL
schemas/          Pydantic 요청·응답 모델 (REQ-111). 라우터와 서비스가 공유
core/             config, deps(get_current_user), rate_limit
```

의존 방향은 위에서 아래 한 방향이다. `services/` 는 FastAPI 에 의존하지 않는다 (오류는 `services/errors.py` 의 도메인 예외로 던지고 라우터가 HTTP 로 바꾼다). 이 덕에 `session_picker.py`, `srs.py`, `progress.py` 같은 순수 함수는 DB 없이 단위 테스트한다.

| 라우터 (prefix) | 책임 | 핵심 서비스 |
| :--- | :--- | :--- |
| `/api/auth` | 가입, 로그인, 로그아웃, 내 정보, 탈퇴 | `auth`, `password`, `session` |
| `/api/vocabularies`, `/api/users/me` | 표준 단어장 목록, 단어 목록, 활성 단어장 지정 | `system_vocab` |
| `/api/study/sessions` | 학습 세션 생성, 문항별 답 기록 | `learning_session`, `session_picker`, `progress`, `srs` |
| `/api/study` | 오답 단어, 통계, 학습 이력 | `stats`, `study_log`, `study` |
| `/api/bookmarks` | 북마크 추가·삭제·목록 | `bookmark` |
| `/api/users/me/settings` | 학습 개수·목표 설정 | 서비스 없이 라우터가 `users` 컬럼을 직접 읽고 갱신 (단순 CRUD 예외) |
| `/health` | 프로세스와 DB 연결 확인 | 라우터 직접 (`SELECT 1`) |

라우터 등록 후 **마지막에** 정적 프론트를 `/` 에 마운트한다. 라우트가 먼저 매칭되므로 `/api`, `/health` 는 정적 마운트에 가려지지 않는다.

### 5.2 프론트엔드 구조

```text
index.html ─ <script type="module" src="js/app.js">
js/app.js        부트스트랩, 상단바·하단 탭바·계정 메뉴, 401 처리 등록
js/routes.js     해시 라우트 표 (#/home, #/explore, #/review, #/stats, #/study/session …)
js/core/         DOM 이 없는 순수 로직: api, router, 세션 러너·드라이버, 콤보, 뷰모델, 저장소, 사운드, TTS
js/views/        화면 (core 의 모델을 받아 textContent 로 렌더링)
js/views/components/  북마크 버튼, 해설 시트, 단어 시트, 품사 태그 등
css/app.css      디자인 토큰, 컴포넌트, 다크 모드 (Tailwind Play CDN 과 병용)
tests/           node --test (순수 로직 + 소스 수준 정적 검사)
```

- **규칙**: `core/` 는 DOM 을 건드리지 않는다. 그래서 외부 패키지 없이 `node --test` 로 검증한다 (P1).
- **API 접근**: 모든 호출이 `core/api.js` 하나를 거친다 (쿠키 전송, 오류 본문 정규화, 401/429 처리, 15초 시간 초과).
- **렌더링 보안**: `innerHTML` 을 쓰지 않고 `textContent` 만 쓴다.
- **클라이언트 저장**: 효과음·테마(`voda.sound_muted`, `voda.theme`)만 브라우저 `localStorage` 에 둔다. 학습 설정은 서버에 저장한다.

### 5.3 시드(콘텐츠) 파이프라인

```text
src/backend/data/seeds/vocabularies.json + words/*.json (5종, 1,000단어)
   → 서버 시작 시 services/system_seed.py 가 검증·적재 (멱등)
       단어장은 slug, 단어는 (vocabulary_id, term) 으로 식별
       content_hash 가 같으면 건너뛰고, 다르면 UPDATE (word_id 불변 → 학습 기록 유지)
   → system_vocabularies, system_words (읽기 전용 공용 데이터)
```

시드 파일을 바꾸면 서버 재시작 때 운영 DB 에 반영된다. 파일 추가·수정 전에 DB 백업이 필요하다 (README §3.6).

## 6. 핵심 런타임 흐름

### 6.1 인증 (ADR-001)

```text
로그인 → services/auth: 닉네임 조회, bcrypt 검증 (계정 없어도 해시 비교를 수행)
       → services/session: secrets.token_urlsafe(32) 발급, SHA-256 다이제스트만 sessions.id 에 저장
       → Set-Cookie voda_session (HttpOnly, SameSite=Lax, Secure=COOKIE_SECURE), 절대 만료 14일
이후 요청 → core/deps.get_current_user: 쿠키 → 해시 → sessions 조회(만료 조건) → User
          쿠키 없음·만료·삭제는 모두 같은 401
```

로그인 무차별 대입 방어(REQ-121)는 `core/rate_limit.py` 의 **프로세스 메모리** 슬라이딩 윈도우다 (IP 또는 닉네임 기준 1분 5회). 외부 저장소를 쓰지 않는다.

### 6.2 학습 세션 (출제와 채점)

```text
POST /api/study/sessions {mode, source}
  → learning_session.create_session
      활성 단어장 확인 → session_picker.select_session_words (순수 함수)
        워터폴: 오답 ≤30%, 복습 10% 선확보, 나머지 미학습, 부족 시 복습 충원. 복습 슬롯은 SRS 복습 기한이 지난 단어를 오래 밀린 순으로 먼저 쓴다 (REQ-150)
      → 문항 스냅샷을 quiz_sessions.questions(JSON) 에 저장
      → 응답에는 정답·해설을 싣지 않는다 (D16)
POST /api/study/sessions/{id}/answer
  → record_session_answer (한 트랜잭션, REQ-106)
      채점(서버) → study_logs 추가 → progress.apply_result (연속 정답, 숙련 판정)
                 → srs.schedule_next (복습 단계·다음 복습 시각)
      → 응답에서 처음으로 정답·해설 공개
```

- 문항은 출제 시점에 스냅샷으로 저장하므로, 이후 시드가 바뀌어도 진행 중인 세션이 흔들리지 않는다.
- 한 번 낸 답은 바뀌지 않는다 (멱등 기록은 `quiz_sessions.answers` 로 보장).
- 복습 세션(북마크, 오답, 오늘 복습)은 같은 엔드포인트의 `source` 값(`bookmarks`, `wrong`, `due`)으로 구분하며 활성 단어장을 바꾸지 않는다.

### 6.3 통계

`services/stats.py` 가 전체 이력에서 서버 집계한다 (누적 정답률, 연속 학습일, 최근 7일, 단어장별 숙련도). 날짜 경계는 KST, 저장은 UTC (REQ-109).

## 7. 횡단 관심사

| 관심사 | 방식 | 요구사항 |
| :--- | :--- | :--- |
| 비동기 | FastAPI `async` + SQLAlchemy 2.x 비동기 엔진(asyncmy), `pool_pre_ping=True` | REQ-101 |
| 트랜잭션 | 요청당 세션 1개. 예외 시 rollback 후 close. 답 1건 기록은 단일 트랜잭션 | REQ-106 |
| 입력 검증 | Pydantic 스키마. 비밀번호는 UTF-8 72바이트 이하 사전 검증 (bcrypt 5.x 가 초과 입력에 예외) | REQ-111, ADR-002 |
| 오류 | 도메인 예외 → 라우터에서 HTTP 상태 변환. 401 은 사유 구분 없이 통일. 학습 세션 API 는 `X-Error-Code` 헤더(예: `NO_WORDS_TO_STUDY`)를 추가하고 프론트가 이 값으로 분기 | REQ-002 |
| 보안 | bcrypt, 세션 토큰 해시 저장, HttpOnly 쿠키, 파라미터 바인딩, 사용자별 데이터 격리, `textContent` 렌더링 | REQ-110~113 |
| 시간 | DB UTC 저장, 세션 시간대 +09:00, 표시는 KST | REQ-108, 109 |
| 스키마 변경 | Alembic 마이그레이션 (`src/backend/alembic/`) | REQ-107 |
| 관측성 | `/health` 만 있다. 구조화 로그·메트릭은 없다 | — |

## 8. 테스트 구조

| 대상 | 도구 | 구성 |
| :--- | :--- | :--- |
| 백엔드 통합 | pytest, **실제 MySQL 컨테이너**에 연결 | `src/backend/tests/test_*_api.py`. 테스트 계정은 `tvoda-` 접두사, 테스트 뒤 데이터 정리 |
| 백엔드 단위 | pytest | `*_units.py`: 출제, SRS, 비밀번호, 인증 등 순수 로직 |
| 프론트엔드 | `node --test` (외부 패키지 없음) | `src/frontend/tests/`: 순수 로직 + 화면 배선·디자인 토큰·다크 모드 누락을 소스 수준에서 검사 |

테스트 케이스와 요구사항의 매핑은 Test Specification 에서 정의한다 (별도 산출물).

## 9. 제약, 위험, 후속 과제

| # | 항목 | 내용 | 영향 | 대응 |
| :-: | :--- | :--- | :--- | :--- |
| A1 | 단일 프로세스 가정 | 로그인 제한이 프로세스 메모리에 있어 워커를 늘리면 한도가 워커별로 갈린다 (REQ-121 도 단일 프로세스 한정으로 명시) | 수평 확장 불가 | 확장 시 공유 저장소(Redis 또는 DB 테이블)로 교체 |
| A2 | 앱 미컨테이너화 | Dockerfile 과 앱 서비스가 없다. 배포는 호스트에서 uvicorn 직접 실행 | 재현 가능한 배포·운영 환경 부재 | 운영 배포가 필요해지면 Dockerfile 과 compose 서비스 추가 (사용자 승인 필요한 구조 변경) |
| A3 | 시드 자동 적재 | 서버 시작마다 시드를 DB 에 반영한다 | 잘못된 시드가 즉시 DB 에 들어간다 | 파일 수정 전 백업. 시작 시 검증 실패는 기동을 막는다 |
| A4 | CDN 의존 | Tailwind Play CDN, SweetAlert2, Lucide, 서체를 런타임에 외부에서 받는다. Tailwind Play CDN 은 프로덕션 비권장 | 오프라인·CDN 장애 시 화면이 깨진다 | 운영 전 빌드된 CSS 또는 자체 호스팅 검토 (P1 과 충돌하므로 결정 필요) |
| A5 | 세션 정리 | 만료된 `sessions`, `quiz_sessions` 물리 삭제 배치가 없다 (Data Design F4) | 행이 누적된다 | 후속 |
| A6 | 이어하기 없음 | 진행 중 세션을 다시 조회하는 API 가 없다 | 새로고침하면 이어갈 수 없다 (푼 문항은 기록됨) | 후속 |
| A7 | 관측성 | 구조화 로그, 메트릭, 알림 없음 | p95 300ms(REQ-102) 를 실측할 수단이 없다 | 후속 |
| A8 | CSRF | `SameSite=Lax` 만 쓰고 별도 토큰이 없다 (ADR-001 의 결과 항목) | 단일 도메인에서만 유효한 판단 | 서브도메인·배포 구조가 바뀌면 재검토 |
| A9 | 서체 라이선스 | Paperlogy 상업적 사용 라이선스 확인 필요 | 배포 전 법적 위험 | 배포 전 확인 |

## 10. 요구사항 추적

| 아키텍처 요소 | 요구사항 |
| :--- | :--- |
| FastAPI async + asyncmy | REQ-101 |
| 단일 출처 서빙, 페이지네이션 | REQ-102, 103 |
| FK·UNIQUE·트랜잭션·Alembic | REQ-104~107 |
| utf8mb4, +09:00, UTC 저장 | REQ-108, 109 |
| bcrypt, Pydantic, `.env`, 바인딩 | REQ-110~113 |
| 인메모리 레이트 리미터 | REQ-121 |
| SRS 복습 단계·오늘 복습 (`srs.py`, `source=due`) | REQ-150 |
| Docker MySQL, 단일 명령 기동 | REQ-116, 117 |
| pytest + node --test | REQ-118 |

## 11. 변경 이력

| 버전 | 날짜 | 내용 | 작성 |
| :--- | :--- | :--- | :--- |
| v1.0 | 2026-11-19 | 최초 작성. 현행 구현(`a48958d`) 기준 기록 | Claude |
