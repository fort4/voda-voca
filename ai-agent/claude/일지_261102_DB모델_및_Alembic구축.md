# 작업 일지 — 2026-11-02 DB 모델 및 Alembic 구축

| 항목 | 내용 |
| :--- | :--- |
| 프로젝트 | voda-voca (보다보카) |
| 작성일 | 2026-11-02 |
| 작업 범위 | 설정 로더 및 DB 연결 검증, Alembic 비동기 초기화, SQLAlchemy 모델 6종, 초기 마이그레이션 적용, DB 콜레이션 통일 |
| 선행 문서 | `docs/voda-voca_Requirement_Spec_v1.2_261102.md`, `docs/voda-voca_Data_Design_v1.1_261102.md`, `ai-agent/claude/검토_261102_ADR_핵심아키텍처결정.md` |

---

## 1. 커밋 이력 (본일)

| 커밋 | 메시지 | 내용 |
| :--- | :--- | :--- |
| `ece5a03` | chore: FastAPI 기본 구조, venv 환경 및 테스트 설정 구성 | `src/backend` 골격, requirements, pytest 설정 |
| `1b3ee6b` | feat: Pydantic 설정 로더 및 비동기 MySQL 세션 연동, 헬스체크 검증 | config, session, `/health`, 테스트 |
| (본 커밋) | feat: SQLAlchemy 2.0 모델 6종 정의 및 Alembic 최초 마이그레이션 적용 | Alembic, 모델, 마이그레이션, 본 일지 |

---

## 2. 설정 로더 및 DB 연결 (`1b3ee6b`)

- `src/backend/core/config.py`: `pydantic-settings`의 `BaseSettings`로 `.env`를 읽습니다. 변수명은 기존 파일과 맞춰 `MYSQL_*`를 사용합니다 (요청의 `DB_*`에서 변경, 승인됨).
- `database_url` 속성은 `URL.create`로 `mysql+asyncmy` URL을 만듭니다. 비밀번호의 특수문자가 호스트 부분을 깨뜨리지 않도록 하기 위함입니다.
- `src/backend/db/session.py`: 엔진(`pool_pre_ping=True`, `echo=False`), 세션 팩토리(`expire_on_commit=False`), FastAPI 의존성 `get_db_session`, 종료 시 `dispose_engine`을 둡니다.
- `/health`: `SELECT 1`을 실행합니다. 성공 시 `200 {"status": "ok", "db": "connected"}`, 실패 시 `503 {"status": "error", "db": "disconnected"}`입니다. 실패 응답 형식은 설계상 제가 정했습니다.

---

## 3. Alembic 비동기 초기화

- 명령: `alembic init -t async alembic` (`src/backend/`에서 실행).
- `src/backend/alembic.ini`: `sqlalchemy.url` 줄을 제거했습니다. 접속 정보는 한 곳(`config.py`)에서만 관리하기 위함입니다.
- `src/backend/alembic/env.py`:
  - 온라인 모드는 `get_engine()`을 사용해 애플리케이션과 같은 엔진으로 마이그레이션을 실행합니다.
  - 오프라인 모드는 `get_settings().database_url`을 사용합니다.
  - `target_metadata = Base.metadata`로 연결했습니다. 모든 모델이 `models/__init__.py`에서 등록됩니다.
  - `compare_type=True`를 설정했습니다. 타입 변경도 autogenerate가 감지하게 하기 위함입니다.
  - `src/`를 `sys.path`에 추가합니다. `backend` 패키지를 찾기 위해서입니다.
- 실행 위치: 프로젝트 루트에서 `alembic -c src/backend/alembic.ini <명령>`.

---

## 4. 모델 6종 정의

모든 모델은 `src/backend/models/`에 있으며 CLAUDE.md 헤더를 포함합니다. 기준은 데이터 설계서 v1.1입니다.

| 파일 | 클래스 | 테이블 | 핵심 제약 |
| :--- | :--- | :--- | :--- |
| `user.py` | `User` | `users` | `uk_users_email`, 닉네임 공백 금지 CHECK |
| `session.py` | `AuthSession` | `sessions` | PK `BINARY(32)`(토큰 SHA-256), FK CASCADE, `(user_id)`·`(expires_at)` 인덱스 |
| `wordbook.py` | `Wordbook` | `wordbooks` | `uk_wordbooks_user_name(user_id, name)`, `(user_id, updated_at)` 인덱스 |
| `word.py` | `Word` | `words` | `uk_words_wordbook_term(wordbook_id, term)`, FK CASCADE |
| `bookmark.py` | `Bookmark` | `bookmarks` | `uk_bookmarks_user_word(user_id, word_id)`, FK CASCADE |
| `study_log.py` | `StudyLog` | `study_logs` | 문항별 1행, `(user_id, created_at)` 인덱스, FK CASCADE |

### 4.1 공통 규칙 구현
- `BIGINT UNSIGNED`는 `sqlalchemy.dialects.mysql.BIGINT(unsigned=True)`로 지정합니다. 처음에는 generic `BIGINT`를 가져와 `unsigned`가 적용되지 않았고, 이를 수정했습니다.
- `DATETIME(3)` 컬럼은 `server_default=text("(UTC_TIMESTAMP(3))")`를 씁니다.
- `updated_at`은 `onupdate=utcnow`로 앱에서 갱신합니다. MySQL `ON UPDATE`는 `UTC_TIMESTAMP`를 쓸 수 없기 때문입니다 (데이터 설계서 §2.3).
- 모든 테이블에 `InnoDB`, `utf8mb4`, `utf8mb4_0900_ai_ci`를 지정합니다.
- 제약과 FK 이름은 설계서와 같은 이름(`uk_*`, `idx_*`, `fk_*`, `ck_*`)으로 명시합니다.

### 4.2 `AuthSession` 네이밍 배경
- 테이블명은 `sessions`이지만 클래스명은 `AuthSession`입니다.
- SQLAlchemy의 `Session`(세션 객체)과 이름이 겹치면 `from ... import Session`에서 혼동이 생기고, 실수로 잘못된 객체를 가져올 수 있습니다.
- `AuthSession`은 "로그인 인증 세션 레코드"를 뜻하며 테이블과 1:1로 대응합니다.

### 4.3 `study_logs` 구조
- 단어별 누적 카운터 대신 문항 답안 1건당 1행입니다 (REQ-016 확정).
- 최근 100건 조회는 `WHERE user_id = ? ORDER BY created_at DESC, id DESC LIMIT 100`입니다. 인덱스를 역방향으로 읽습니다.

---

## 5. 마이그레이션 적용 결과

| 항목 | 결과 |
| :--- | :--- |
| 리비전 | `08e3374f8644` `feat: 초기 스키마 6종 테이블 생성` |
| 생성 방식 | `alembic revision --autogenerate` 후 DDL을 검토 |
| 검토 결과 | 생성된 DDL이 데이터 설계서 v1.1과 일치함 |
| 적용 | `alembic upgrade head` 성공 |
| 테이블 | `alembic_version`, `bookmarks`, `sessions`, `study_logs`, `users`, `wordbooks`, `words` (7개, 그중 도메인 6개) |
| 드리프트 | `alembic check`: "No new upgrade operations detected" |
| FK | 7개 모두 `ON DELETE CASCADE` 확인 |
| 인덱스/UNIQUE | 설계서의 유니크 4개, 인덱스 6개 모두 확인 |

### 5.1 DB 콜레이션 통일 (승인 후 실행)
- 발견 경위: `alembic_version` 테이블만 `utf8mb4_unicode_ci`로 생성됐습니다. DB 기본 콜레이션이 compose 변경 전에 만들어진 상태 그대로였기 때문입니다.
- 실행한 DDL:
  ```sql
  ALTER DATABASE voda_voca CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
  ALTER TABLE alembic_version CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
  ```
- 첫 번째 명령은 실행됐고, 두 번째는 셸 체인 문제로 한 번 실행되지 않아 별도로 실행했습니다. 두 번 실행해도 결과는 같습니다.
- 확인 결과:
  - 스키마 기본값: `utf8mb4` / `utf8mb4_0900_ai_ci`
  - 테이블 7개 모두 `utf8mb4_0900_ai_ci`
  - `alembic_version.version_num`: `utf8mb4_0900_ai_ci`, 값 `08e3374f8644`
  - `alembic check`: 드리프트 없음

---

## 6. 테스트 구조 및 의존성 변경

### 6.1 cryptography 추가
- 증상: 헬스체크 테스트에서 `RuntimeError: 'cryptography' package is required for sha256_password or caching_sha2_password auth methods`.
- 원인: MySQL 8.0의 기본 인증 플러그인 `caching_sha2_password`는 비동기 핸드셰이크에서 RSA 암호화를 쓰고, asyncmy는 이를 위해 `cryptography`를 요구합니다.
- 조치: `cryptography==50.0.2`를 `requirements.txt`에 고정했습니다 (승인됨).

### 6.2 httpx.AsyncClient 전환
- 기존: `fastapi.testclient.TestClient`를 사용했습니다.
- 문제: `TestClient`는 자체 이벤트 루프 스레드를 만듭니다. 비동기 엔진의 커넥션 풀은 생성된 루프에 묶여, 테스트마다 루프가 달라지면 "다른 루프에 붙은 커넥션" 오류가 납니다. 또한 Starlette가 `httpx` 사용 방식에 대해 deprecation 경고를 냈습니다.
- 변경: `httpx.ASGITransport` + `httpx.AsyncClient`를 쓰는 `pytest_asyncio.fixture`로 바꿨습니다. 테스트를 `@pytest.mark.asyncio`로 표시합니다.
- 격리: `tests/conftest.py`의 autouse fixture가 각 테스트 종료 후 `dispose_engine()`을 호출합니다.
- 결과: 테스트 5개 통과 (설정 3개, 헬스체크 2개). 헬스체크 테스트는 실제 MySQL에 연결하므로 컨테이너가 떠 있어야 합니다.

---

## 7. 미완료 및 후속 과제

| # | 항목 | 상태 | 비고 |
| :-: | :--- | :--- | :--- |
| 1 | 인증 모듈(Auth) 구현 | 계획 단계 | 다음 단계 |
| 2 | 단어장/단어/북마크/학습 API | 미착수 | 인증 이후 |
| 3 | 비밀번호 최소 길이 정책 | 미정 | 사용자 확인 필요 |
| 4 | 세션 쿠키 `Secure` 속성 기본값 | 미정 | 로컬 HTTP에서는 끄고 `.env`로 제어 예정 |
| 5 | 세션 수명 14일 | 기본값 적용 | 사용자 확인 필요 |
| 6 | 뜻 검색 포함 여부 (F4) | 1차 제외 | 사용자 확인 필요 |
