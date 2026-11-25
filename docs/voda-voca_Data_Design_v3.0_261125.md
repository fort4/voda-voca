# 데이터 설계서 (Data Design)

| 항목 | 내용 |
| :--- | :--- |
| 프로젝트 | voda-voca (보다보카) |
| 문서 종류 | Data Design (`개발방법론.md` §2.3, 필수 산출물) |
| 기준 문서 | `docs/voda-voca_Requirement_Spec_v2.3_261125.md` (REQ-003, 012, 014~019, 102~109, 122, 129, 131~133, 140~143) |
| 버전 / 상태 | v3.0 / **검토 대기 (Draft)** — DBMS 를 MySQL 8.0 에서 SQLite 로 전환(ADR-010). 테이블·컬럼의 의미는 v2.2 와 같고, 물리 타입·제약·DDL·마이그레이션 이력이 바뀌었다 |
| 작성일 | 2026-11-25 (v2.2: 2026-11-19, v2.1: 2026-11-05, v2.0: 2026-11-02) |
| DBMS | SQLite 3 (단일 파일 `DB_PATH`, 기본 `/data/voca.db`, WAL 모드). 드라이버 `aiosqlite` (ADR-010) |
| 문자셋 / 대소문자 | UTF-8 (SQLite TEXT) / 대소문자 무시가 필요한 컬럼만 `COLLATE NOCASE` (ASCII 한정) |
| 산출물 경로 | `docs/voda-voca_Data_Design_v3.0_261125.md` (이전 버전: `docs/old/voda-voca_Data_Design_v2.2_261119.md` 외 보관) |
| 관련 결정 | `ai-agent/claude/검토_261102_ADR_핵심아키텍처결정.md` (ADR-001 세션, ADR-002 bcrypt), `docs/voda-voca_Decision_Records_v1.0_261119.md` (ADR-004 중앙 제공형 단어장, ADR-005 서버 채점, ADR-006 SRS), `ai-agent/claude/작업계획_261105_통합_설계안.md` |

> **v2.1 요약**: 개인 단어장 모델(`wordbooks`, `words`)을 폐지하고 서버가 제공하는 읽기 전용 카탈로그(`system_vocabularies`, `system_words`)와 사용자별 학습 요약(`user_word_progress`)으로 전환했다. 폐기된 테이블은 마이그레이션 `d1a8e3f5c7b9`(D-2)에서 DROP 되었다. 이 문서의 스키마는 실제 DB(`SHOW CREATE TABLE`)와 `alembic check` 로 대조했다.

> **v3.0 요약 (SQLite 전환, ADR-010)**: 과제 서버 규칙(DB 는 SQLite)에 맞춰 MySQL 8.0 에서 SQLite 로 바꿨다. ① 모든 PK/FK 는 `INTEGER`(rowid 별칭, 자동 증가)이고 `UNSIGNED`·`INTEGER`·`INTEGER` 는 없다. ② `DATETIME` 은 `DATETIME`(UTC, 마이크로초 문자열)이고 기본값은 `strftime` 식이다. ③ 대소문자 무시는 콜레이션 `utf8mb4_0900_ai_ci` 대신 `NOCASE` 를 `nickname`·`system_words.term`·`system_vocabularies.slug` 에 건다(악센트 무시는 사라지고 앱의 정규화가 맡는다). ④ `SELECT ... FOR UPDATE` 행 잠금은 없고 트랜잭션을 `BEGIN IMMEDIATE` 로 시작해 쓰기를 직렬화한다. ⑤ 마이그레이션 12개를 SQLite 초기 리비전 `0001` 하나로 합쳤고 과제용은 **빈 DB 에서 시작**한다. ⑥ §5 DDL 은 `alembic upgrade head` 가 실제로 만든 스키마를 그대로 덤프한 것이다.
>
> **v2.2 요약**: `user_word_progress` 에 간격 반복 컬럼 `interval_step`, `next_review_at` 과 인덱스를 추가했고(`f4c8b2d6a1e7`), `quiz_sessions.source` 에 `due`(오늘 복습)를 추가했다(`a7d3f1c9e5b2`). v2.1 개정 이력(2026-11-06~11-11)은 v2.2 에 포함해 확정했다. 요구사항 REQ-150.

---

## 1. ERD

```mermaid
erDiagram
    users ||--o{ sessions : "로그인 세션 (1:N)"
    users ||--o{ bookmarks : "북마크 (1:N)"
    users ||--o{ study_logs : "문항별 이력 (1:N)"
    users ||--o{ user_word_progress : "단어별 학습 요약 (1:N)"
    users ||--o{ quiz_sessions : "학습 세션 (1:N)"
    users }o--o| system_vocabularies : "학습 중인 단어장 (active_vocabulary_id, 0..1)"
    system_vocabularies ||--o{ system_words : "포함 (1:N)"
    system_vocabularies |o--o{ quiz_sessions : "출제 단어장 (0..1:N, 북마크·오답 복습은 NULL)"
    system_words ||--o{ bookmarks : "북마크 대상 (1:N)"
    system_words ||--o{ study_logs : "학습 대상 (1:N)"
    system_words ||--o{ user_word_progress : "진행 대상 (1:N)"

    users {
        INTEGER id PK
        VARCHAR password_hash
        VARCHAR nickname UK
        INTEGER active_vocabulary_id FK "NULL 허용"
        INTEGER quiz_count "기본 10"
        INTEGER flashcard_count "기본 10"
        INTEGER daily_goal "기본 10"
        DATETIME created_at
        DATETIME updated_at
    }
    sessions {
        BLOB32 id PK
        INTEGER user_id FK
        DATETIME created_at
        DATETIME expires_at
    }
    system_vocabularies {
        INTEGER id PK
        VARCHAR slug UK
        VARCHAR title
        VARCHAR category "자유 문자열 + 인덱스"
        INT level "1~5"
        VARCHAR description
        INT total_words
        INT sort_order
        CHAR content_hash
        VARCHAR source "seed|admin"
    }
    system_words {
        INTEGER id PK
        INTEGER vocabulary_id FK
        VARCHAR term
        VARCHAR meaning
        VARCHAR example
        VARCHAR example_meaning
        INT order_index
        VARCHAR source "seed|admin"
    }
    user_word_progress {
        INTEGER id PK
        INTEGER user_id FK
        INTEGER word_id FK
        INT correct_count
        INT wrong_count
        INT consecutive_correct_count
        BOOLEAN is_memorized
        VARCHAR last_result "CORRECT | WRONG"
        DATETIME last_studied_at
    }
    quiz_sessions {
        INTEGER id PK
        INTEGER user_id FK
        INTEGER vocabulary_id FK "NULL 허용 (복습 세션)"
        VARCHAR source "vocabulary | bookmarks | wrong | due"
        VARCHAR mode "quiz | flashcard"
        JSON questions
        JSON answers
        BOOLEAN is_submitted
        DATETIME expires_at
        DATETIME created_at
    }
    bookmarks {
        INTEGER id PK
        INTEGER user_id FK
        INTEGER word_id FK
        DATETIME created_at
    }
    study_logs {
        INTEGER id PK
        INTEGER user_id FK
        INTEGER word_id FK
        BOOLEAN is_correct
        VARCHAR mode "quiz | flashcard"
        DATETIME created_at
    }
```

> 삭제된 테이블: `wordbooks`, `words` (v2.0 까지 존재). ERD 에서 제거했다.

### 1.1 관계 요약과 삭제 정책

| 관계 | 카디널리티 | 설명 | 삭제 정책 |
| :--- | :---: | :--- | :--- |
| system_vocabularies → system_words | 1:N | 표준 단어장은 여러 단어를 가진다. | CASCADE (`fk_sysword_vocabulary`) |
| users → system_vocabularies (활성) | N:0..1 | `users.active_vocabulary_id`. 학습 중인 단어장 | **SET NULL** (`fk_users_active_vocabulary`) |
| users ↔ system_words (bookmarks) | M:N | `bookmarks` 가 교차 테이블 | CASCADE (양쪽) |
| users ↔ system_words (study_logs) | M:N | 문항 답안 1건당 1행 누적 | CASCADE (양쪽) |
| users ↔ system_words (user_word_progress) | M:N | 사용자×단어 1행의 학습 요약 | CASCADE (양쪽) |
| users → sessions | 1:N | 로그인 세션 | CASCADE |
| users → quiz_sessions | 1:N | 학습 세션 | CASCADE (`fk_quiz_sessions_user`) |
| system_vocabularies → quiz_sessions | 1:N (선택) | 활성 단어장 세션의 원천. 복습 세션은 NULL | CASCADE (`fk_quiz_sessions_vocabulary`) |

---

## 2. 공통 규칙

### 2.1 문자셋 및 대소문자 정책 (REQ-108)
- SQLite 는 문자열을 UTF-8 로 저장하므로 한글, IPA 확장 문자, 이모지에 별도 설정이 필요 없다. 컬럼 길이(`VARCHAR(n)`)는 SQLite 가 강제하지 않으며 **앱(Pydantic 스키마, 시드 검증)이 검증**한다.
- **대소문자 정책**: 대소문자를 무시한 유일성이 필요한 컬럼(`users.nickname`, `system_words.term`, `system_vocabularies.slug`)에만 `COLLATE NOCASE` 를 건다. `UNIQUE` 와 `=` 비교가 모두 이 콜레이션을 따르므로 `Apple` 과 `apple` 은 같은 값이다. (D2 유지)
- **악센트 정책 변경**: `NOCASE` 는 ASCII 만 접는다. MySQL 의 `ai`(악센트 무시)는 사라졌으므로 `café` 와 `cafe` 는 DB 가 구분한다. 시더(`services/system_seed.py`)가 비교 키를 자체 정규화해 같은 표제어로 취급하므로 시드 동작은 그대로다.
- 한글 닉네임은 대소문자 개념이 없어 영향이 없다.

### 2.2 시간대 정책 (REQ-108, REQ-109)
| 구분 | 정책 |
| :--- | :--- |
| 저장 값 | 모든 `DATETIME` 컬럼은 **UTC**로 저장한다 (tzinfo 없는 값). |
| 형식 | SQLAlchemy 가 `YYYY-MM-DD HH:MM:SS.ffffff` 문자열로 저장한다. 날짜 비교와 정렬은 문자열 비교로 정확하다. |
| 기본값 | `DEFAULT (strftime('%Y-%m-%d %H:%M:%f000', 'now'))`. `%f` 는 밀리초(`SS.SSS`)만 주므로 뒤에 `000` 을 붙여 6자리 마이크로초로 맞춘다. **3자리면 SQLAlchemy 가 소수부를 마이크로초 정수로 읽어 0.123초가 0.000123초가 된다** (`test_sqlite_schema.py` 가 고정). |
| 표시 | 응답 직렬화 시 UTC를 Asia/Seoul(KST)로 변환한다. 변환은 프론트엔드 표시 단계에서 수행한다 (REQ-109 확정). |
| 날짜 집계 | KST 날짜가 필요한 통계는 `date(created_at, '+9 hours')` 로 변환한 뒤 묶는다 (`services/stats.py`). |
| 정밀도 | 마이크로초. 세션 마감 시각은 앱이 밀리초로 맞춰 비교한다 (`services/study.py`). |

> **근거**: 시간대 설정이 있는 DB 서버가 없으므로 모든 변환을 앱이 명시적으로 한다. UTC 값을 저장하면 서버 환경(컨테이너 `TZ`)과 무관하게 값이 고정된다.

### 2.3 기본 키 및 공통 컬럼
- PK: `id INTEGER PRIMARY KEY` (rowid 별칭, 자동 증가). SQLite 는 **`INTEGER` 로 선언한 PK 만** rowid 별칭이 되어 자동 증가하므로 `INTEGER` 를 쓰지 않는다. 값 범위는 64비트라 행 수 증가에 충분하다. 모델에서도 `Integer` 로 고정했다 (`test_system_models.py`).
- 생성/수정 시각: `created_at`, `updated_at` (`DATETIME`, UTC). 생성 시각은 §2.2 의 기본값으로 채운다.
- 수정 시각 `updated_at` 은 DB 트리거나 `ON UPDATE` 로 갱신하지 않고 애플리케이션 계층(SQLAlchemy `onupdate`)에서 UTC 시각을 명시적으로 설정한다.
- 소프트 삭제 컬럼(`deleted_at`)은 두지 않는다. 삭제 정책은 하드 삭제다.
- **외래키 강제**: SQLite 는 기본이 꺼져 있어 연결마다 `PRAGMA foreign_keys=ON` 을 건다 (`db/session.py`). 꺼져 있으면 `ON DELETE CASCADE` 가 조용히 동작하지 않는다 (`test_sqlite_engine.py` 가 고정).
- **동시성**: `journal_mode=WAL`, `busy_timeout=5000`, 트랜잭션은 `BEGIN IMMEDIATE` 로 시작한다. 읽기로 시작한 트랜잭션이 나중에 쓰기로 올라갈 때 다른 커밋이 끼면 `busy_timeout` 과 무관하게 즉시 `database is locked` 가 나기 때문이다 (ADR-010).

### 2.4 삭제 연쇄 (REQ-104, REQ-122)
- 사용자 소유 행(`sessions`, `bookmarks`, `study_logs`, `user_word_progress`, `quiz_sessions`)의 FK 는 `ON DELETE CASCADE` 다. **회원 탈퇴(REQ-122)는 `users` 행 하나를 지우면 이들이 DB 수준에서 함께 정리된다.**
- **표준 단어장·단어는 공용 콘텐츠이므로 탈퇴로 지워지지 않는다.** `system_*` 테이블은 `users` 를 참조하지 않는다.
- 표준 단어(`system_words`)가 삭제되면(시드 정리 같은 운영 작업) 그 단어의 북마크, 학습 이력, 학습 요약이 함께 삭제된다. 표준 단어장(`system_vocabularies`)이 삭제되면 단어, 그 단어장 출처 세션이 삭제되고 `users.active_vocabulary_id` 는 `NULL` 이 된다.
- **단어 삭제는 학습 세션을 삭제하지 않는다.** 문항 정보가 `questions` JSON 에 들어 있어 `quiz_sessions` 와 `system_words` 사이에 FK 가 없다. 대신 답을 기록할 때 서비스 계층이 단어 존재를 확인하고, 없으면 409(`QUIZ_WORD_MISSING`)로 막는다 (§3.7).
- 학습 이력은 삭제 후에도 보존하지 않는다 (하드 삭제 정책).

### 2.5 검색 정책
- v2.1 에서 표제어 검색 API 는 제공하지 않는다 (REQ-009 폐기). 단어 목록은 `(vocabulary_id, order_index)` 순서의 페이지 조회다 (§3.3).

---

## 3. 테이블 명세

### 3.1 users (계정) — REQ-001, REQ-002, REQ-003, REQ-110

| 컬럼 | 타입 | NULL | 기본값 | 제약 / 설명 |
| :--- | :--- | :---: | :--- | :--- |
| `id` | INTEGER | N | 자동 증가(rowid) | **PK** |
| `password_hash` | VARCHAR(255) | N | — | bcrypt 해시 (REQ-110, ADR-002). 평문 저장 금지. 60자 고정 길이이며 여유를 두어 255로 정의한다. |
| `nickname` | VARCHAR(50) | N | — | **UNIQUE** (`uk_users_nickname`). 로그인 식별자이자 표시 이름. 앱 검증은 2~30자(공백 제거 후), `COLLATE NOCASE` 로 대소문자를 무시하고 유일하다 (v1.3, v3.0 에서 콜레이션을 NOCASE 로 교체). |
| `created_at` | DATETIME | N | UTC 현재 시각(§2.2) | UTC |
| `updated_at` | DATETIME | N | UTC 현재 시각(§2.2) | UTC, 수정 시 앱에서 갱신 |
| `active_vocabulary_id` | INTEGER | Y | NULL | **FK** → `system_vocabularies.id` `ON DELETE SET NULL` (`fk_users_active_vocabulary`). 학습 중인 표준 단어장 (REQ-142). 가입 시 `beginner-200`(초급 200제)이 자동 지정된다. 마이그레이션 `b1e5c0a7d2f4`. |
| `quiz_count`, `flashcard_count`, `daily_goal` | INTEGER | N | 10 | 학습 개수 설정 (v2.2, REQ-147): 퀴즈·플래시카드 1회 문항 수, 오늘의 목표. `CHECK (> 0)` 만 DB 가 보장하고 **허용 값(10/20/30)은 앱이 검증**한다(`schemas/user_settings.py`). 기존 사용자도 DEFAULT 10. 마이그레이션 `e2b6d4a9f1c3`. |

**인덱스**: `PRIMARY KEY (id)`, `UNIQUE KEY uk_users_nickname (nickname)`, `KEY fk_users_active_vocabulary (active_vocabulary_id)` (FK 자동 생성)

> v1.3 변경: `email` 컬럼과 `uk_users_email` 을 제거하고 `nickname` 을 고유 키로 승격했다 (마이그레이션 `3384caa6f116`). 중복 닉네임이 있으면 마이그레이션은 중단하며 데이터를 임의로 바꾸지 않는다. 내리기 시 제거된 이메일 값은 복구되지 않는다.

**CHECK**: `ck_users_nickname_not_blank` — `length(trim(nickname)) > 0`

> 로그인 세션은 `sessions` 테이블(§3.6)에 저장한다 (ADR-001).

---

### 3.2 system_vocabularies (표준 단어장) — REQ-140, REQ-143

단어장 카탈로그다. 표준 단어장(`source='seed'`)은 서버 시드로만 바뀌고, 관리자 단어장(`source='admin'`)은 관리 API 로 만든다 (REQ-160). 일반 사용자의 쓰기 경로는 없다.

| 컬럼 | 타입 | NULL | 기본값 | 제약 / 설명 |
| :--- | :--- | :---: | :--- | :--- |
| `id` | INTEGER | N | 자동 증가(rowid) | **PK** |
| `slug` | VARCHAR(50) | N | — | **UNIQUE** (`uk_sysvoc_slug`). 시드 멱등 키 (예: `beginner-200`). |
| `title` | VARCHAR(100) | N | — | 표시 이름. 공백만으로 둘 수 없다. |
| `category` | VARCHAR(50) | N | — | **자유 문자열 + 인덱스** (`idx_sysvoc_category`). ENUM/CHECK 를 쓰지 않는다 — 새 카테고리(CONVERSATION, TOEIC 등)를 스키마 변경 없이 시드만으로 추가한다. 현재 `ELEMENTARY`, `SECONDARY`, `CSAT`. 탐색 필터 칩의 근거다. |
| `level` | INT | N | `1` | 난이도 1~5 (`ck_sysvoc_level_range`). |
| `description` | VARCHAR(255) | Y | NULL | 설명 |
| `total_words` | INTEGER | N | `0` | 시더가 실제 단어 수로 갱신하는 비정규화 값 |
| `sort_order` | INT | N | `0` | 카탈로그 노출 순서 |
| `content_hash` | VARCHAR(64) | Y | NULL | 시드 내용의 SHA-256. 같으면 쓰기를 건너뛴다. NULL 이면 아직 적재되지 않은 행이다. |
| `source` | VARCHAR(10) | N | `'seed'` | `'seed'` \| `'admin'`. 값 제한은 앱이 한다. 마이그레이션 `0003` |
| `created_at`, `updated_at` | DATETIME | N | UTC 현재 시각(§2.2) | UTC |

**인덱스**: `PRIMARY KEY (id)`, `UNIQUE uk_sysvoc_slug (slug)`, `KEY idx_sysvoc_category (category)`
**CHECK**: `ck_sysvoc_level_range` (`level BETWEEN 1 AND 5`), `ck_sysvoc_title_not_blank` (`length(trim(title)) > 0`)

### 3.3 system_words (표준 단어와 관리자 등록 단어) — REQ-141, REQ-143, REQ-161

| 컬럼 | 타입 | NULL | 기본값 | 제약 / 설명 |
| :--- | :--- | :---: | :--- | :--- |
| `id` | INTEGER | N | 자동 증가(rowid) | **PK** |
| `vocabulary_id` | INTEGER | N | — | **FK** → `system_vocabularies.id` `ON DELETE CASCADE` (`fk_sysword_vocabulary`) |
| `term` | VARCHAR(100) | N | — | 표제어 |
| `meaning` | VARCHAR(200) | N | — | 뜻 |
| `example` | VARCHAR(500) | Y | NULL | 예문 |
| `example_meaning` | VARCHAR(500) | Y | NULL | 예문의 한글 뜻. **예문이 없으면 항상 NULL** (D14). |
| `pos` | VARCHAR(20) | Y | NULL | 품사 (v2.2 사용, REQ-145). **영문 소문자 단어** (`noun`, `verb`, `adjective`, `adverb`, `preposition`, `conjunction`, `pronoun`, `interjection`). 시드 1,000단어 전부 채운다 (신규 2개 단어장은 v2.2, 기존 3개 단어장 600단어는 v2.2 후속). 컬럼은 NULL 허용으로 남긴다. **API 로 내려가고 화면이 한글 라벨을 입힌다** (REQ-146). 시드 로더는 문자열·20자 이하만 검증하고, 허용 집합은 시드 관문 테스트가 강제한다. 마이그레이션은 없다 (`b1e5c0a7d2f4` 가 이미 만든 컬럼) |
| `phonetic` | VARCHAR(100) | Y | NULL | 발음기호 (v2.2 사용, REQ-144). **슬래시 없는 미국식 IPA 문자열** (예: `ˈæpəl`). 화면이 `/…/` 서식을 입힌다. NULL 이면 화면이 발음기호 요소를 그리지 않는다. 시드 로더가 IPA 문자만 허용하고 한글·슬래시·대괄호·제어 문자·100자 초과를 거부한다. 값이 없는 단어는 NULL 이며 빈 문자열로 저장하지 않는다. 마이그레이션은 없다 (`b1e5c0a7d2f4` 가 이미 같은 규격으로 만들었다) |
| `level` | INTEGER | Y | NULL | 단어 난이도. **확장 필드, 1단계 미사용** |
| `order_index` | INT | N | `0` | 단어장 안의 순서. 미학습 단어는 이 순서로 출제된다 (REQ-012). |
| `source` | VARCHAR(10) | N | `'seed'` | `'seed'` \| `'admin'`. 관리자 등록 단어만 수정·삭제한다. 시드에 같은 표제어(대소문자·악센트 무시, `core/terms.py`)가 들어오면 같은 행을 `'seed'` 로 바꿔 이력을 보존한다. 마이그레이션 `0003` |

**인덱스**: `PRIMARY KEY (id)`, `UNIQUE uk_sysword_vocab_term (vocabulary_id, term)` (`term` 이 `NOCASE` 라 대소문자를 무시하고 유일. 악센트는 시더가 정규화), `KEY idx_sysword_vocab_order (vocabulary_id, order_index)`
**CHECK**: `ck_sysword_not_blank` (`length(trim(term)) > 0 AND length(trim(meaning)) > 0`)

**설계 메모**
- 단어 목록(`GET /api/vocabularies/{id}/words`)은 `WHERE vocabulary_id = ? ORDER BY order_index` 의 OFFSET 페이징이다. 단어장당 수백~천 건이라 keyset 은 도입하지 않는다.
- `words` 와 달리 `user_id` 가 없다 — 공용 콘텐츠이므로 사용자 소유권이 없다(출처만 `source` 로 구분한다).

### 3.4 user_word_progress (사용자별 단어 학습 요약) — REQ-016, REQ-012

사용자×단어 1행. `study_logs` 를 매번 훑지 않고 세션 출제와 숙련 판정을 빠르게 하기 위한 요약이다. 간격 반복(SRS, REQ-150) 상태인 복습 단계와 다음 복습 시각도 이 테이블에 둔다 (v2.2).

| 컬럼 | 타입 | NULL | 기본값 | 제약 / 설명 |
| :--- | :--- | :---: | :--- | :--- |
| `id` | INTEGER | N | 자동 증가(rowid) | **PK** |
| `user_id` | INTEGER | N | — | **FK** → `users.id` `ON DELETE CASCADE` (`fk_uwp_user`) |
| `word_id` | INTEGER | N | — | **FK** → `system_words.id` `ON DELETE CASCADE` (`fk_uwp_word`) |
| `correct_count` | INTEGER | N | `0` | 누적 정답 수 |
| `wrong_count` | INTEGER | N | `0` | 누적 오답 수 |
| `consecutive_correct_count` | INTEGER | N | `0` | 연속 정답 수. 오답이면 0 |
| `is_memorized` | BOOLEAN | N | `0` | 숙련 여부 |
| `last_result` | VARCHAR(7) + CHECK('CORRECT','WRONG') | Y | NULL | 마지막 결과 |
| `last_studied_at` | DATETIME | Y | NULL | 마지막 학습 시각 (UTC) |
| `interval_step` | INTEGER | N | `0` | 복습 단계 0~5 (v2.2). 정답 +1(최대 5), 오답 −2(최소 0) |
| `next_review_at` | DATETIME | Y | NULL | 다음 복습 시각 (UTC, v2.2). 학습 이력이 없으면 NULL. 단계별 간격 0·1·3·7·14·30일이며, 답한 시각이 아니라 **간격일 뒤 한국 날짜 0시**(UTC 로 저장)다 |

**인덱스**: `PRIMARY KEY (id)`, `UNIQUE uk_uwp_user_word (user_id, word_id)`, `KEY idx_uwp_user_result (user_id, last_result)`, `KEY idx_uwp_user_memorized (user_id, is_memorized)`, `KEY idx_uwp_word (word_id)`, `KEY idx_uwp_user_next_review (user_id, next_review_at)`

**숙련 규칙 (`services/progress.py` 의 `apply_result`, 불변 상태 전이)**

| 결과 | 변경 |
| :--- | :--- |
| 정답 | `correct_count += 1`, `consecutive_correct_count += 1`, `last_result = 'CORRECT'`, 연속이 **3 이상**이면 `is_memorized = TRUE` |
| 오답 | `wrong_count += 1`, `consecutive_correct_count = 0`, `is_memorized = FALSE`, `last_result = 'WRONG'` |

**복습 단계 규칙 (`services/srs.py` 의 `schedule_next`, 순수 함수, v2.2, ADR-006)**

| 단계 | 0 | 1 | 2 | 3 | 4 | 5 |
| :--- | :-: | :-: | :-: | :-: | :-: | :-: |
| 다음 복습까지(일) | 0 | 1 | 3 | 7 | 14 | 30 |

정답이면 단계 +1(최대 5), 오답이면 −2(최소 0, `WRONG_STEP_PENALTY`)이며 `next_review_at = (답한 시각이 속한 한국 날짜의 0시) + 새 단계의 간격(일)` 이다(`kst_day_start`). 단 **복습 기한(`next_review_at`)이 되기 전에 맞힌 정답은 단계와 `next_review_at` 을 바꾸지 않는다**(정답 수·연속 정답·숙련은 평소대로 갱신). 오답은 기한과 무관하게 단계를 내린다. `next_review_at` 이 NULL 이면(처음 푸는 단어·옛 데이터) 기한 전이 아니다. 2026-11-19 이전에 저장된 `next_review_at` 은 옛 규칙(답한 시각 기준)이지만 스키마 변경 없이 다음 답부터 새 규칙으로 바뀐다. `is_memorized` 는 이 단계와 별개로 기존 연속 정답 3회 규칙을 유지한다. 마이그레이션 `f4c8b2d6a1e7` 은 학습 이력이 있는 기존 행의 `interval_step` 을 `LEAST(consecutive_correct_count, 5)`, `next_review_at` 을 `last_studied_at + 해당 단계 간격` 으로 채웠다.

**설계 메모**
- 갱신은 `services/study_log.py` 의 `record_result` 가 **`study_logs` INSERT 와 같은 트랜잭션**에서 한다. 행이 없으면 `INSERT ... ON CONFLICT DO NOTHING` 으로 먼저 만들고 갱신한다. 트랜잭션이 `BEGIN IMMEDIATE` 로 시작해 쓰기가 한 번에 하나씩 처리되므로 동시 기록도 정확히 센다 (`test_sqlite_services.py` 가 동시 20건 집계로 검증).
- 이 테이블의 행 유무가 "학습한 단어"의 기준이다. 단어장 진행률(`studied_words`)은 이 테이블에서 센다.

### 3.5 bookmarks (북마크) — REQ-017, REQ-018, REQ-105

| 컬럼 | 타입 | NULL | 기본값 | 제약 / 설명 |
| :--- | :--- | :---: | :--- | :--- |
| `id` | INTEGER | N | 자동 증가(rowid) | **PK** |
| `user_id` | INTEGER | N | — | **FK** → `users.id` `ON DELETE CASCADE` |
| `word_id` | INTEGER | N | — | **FK** → `system_words.id` `ON DELETE CASCADE` (v2.0 까지 `words.id`, 마이그레이션 `c3f7a9d1e8b2` 에서 전환) |
| `created_at` | DATETIME | N | UTC 현재 시각(§2.2) | UTC |

**인덱스**: `PRIMARY KEY (id)`, `UNIQUE uk_bookmarks_user_word (user_id, word_id)`, `KEY idx_bookmarks_word (word_id)`

**설계 메모**
- 대상이 공용 단어이므로 v2.0 의 "단어장 소유자 검증"(D3)은 필요 없다. 없는 `word_id` 는 404 다.
- 북마크 목록은 `bookmarks → system_words → system_vocabularies` 조인으로 단어장 제목을 함께 돌려준다.

### 3.6 study_logs (학습 이력) — REQ-016

문항 답안 1건당 1행. 단어별 누적 요약은 `user_word_progress`(§3.4)가 맡고, 이 테이블은 시간순 원본 기록이다.

| 컬럼 | 타입 | NULL | 기본값 | 제약 / 설명 |
| :--- | :--- | :---: | :--- | :--- |
| `id` | INTEGER | N | 자동 증가(rowid) | **PK** |
| `user_id` | INTEGER | N | — | **FK** → `users.id` `ON DELETE CASCADE` |
| `word_id` | INTEGER | N | — | **FK** → `system_words.id` `ON DELETE CASCADE` (`fk_study_logs_word`) |
| `is_correct` | BOOLEAN | N | — | 정답 1, 오답 0. 플래시카드의 "알아요" = 정답, "헷갈려요" = 오답 |
| `created_at` | DATETIME | N | UTC 현재 시각(§2.2) | UTC. 답을 기록한 시각 |
| `mode` | VARCHAR(20) | N | `'quiz'` | `'quiz'` \| `'flashcard'` (`ck_study_logs_mode`). 마이그레이션 `c3f7a9d1e8b2` 에서 추가 |
| `direction` | VARCHAR(10) | N | `'en_to_ko'` | `'en_to_ko'` \| `'ko_to_en'` (`ck_study_logs_direction`). **문항의 실제 방향**이며 `mixed` 는 값이 아니다. 플래시카드 행은 기본값. 마이그레이션 `0002` (REQ-157, VOCA-FR-026) |
| `format` | VARCHAR(10) | N | `'choice'` | `'choice'` \| `'ox'` (`ck_study_logs_format`). 마이그레이션 `0002` |

**인덱스**: `PRIMARY KEY (id)`, `KEY idx_study_logs_user_created (user_id, created_at)`, `KEY idx_study_logs_word (word_id)`

**설계 메모**
- **기록 방식 (v2.1 변경)**: 세션에서 **답 1건마다** INSERT 한다. 이력 1행과 `user_word_progress` 갱신이 한 트랜잭션이다 (REQ-016, REQ-106). v2.0 의 "제출 시 일괄 INSERT"는 폐기되었다.
- **최근 이력 쿼리**: `WHERE user_id = ? ORDER BY created_at DESC, id DESC LIMIT 100` (`GET /api/study/logs`).
- **오답 판정**: 단어별 `(created_at DESC, id DESC)` 최신 1건이 오답인 단어 (`services/stats.py` 의 `wrong_word_ids`, 윈도 함수 `ROW_NUMBER`). 기간 제한이 없으며 통계의 `wrong_word_count`, 오답 복습 세션, `GET /api/study/wrong-words` 가 같은 규칙을 쓴다.
- **통계 집계**: 누적 정답률, 연속 학습일(KST 날짜 경계), 최근 7일, 단어장별 진행률은 서버가 이 테이블과 `user_word_progress` 에서 직접 센다 (REQ-131). 별도 집계 테이블은 없다.
- **단어 삭제와의 상호작용**: 기록 직전에 단어 존재를 확인하고, 확인 뒤 경쟁으로 FK(`fk_study_logs_word`, `fk_uwp_word`)가 깨지면 롤백하고 409 로 바꾼다.
- **보존 기간**: 삭제 정책을 두지 않는다.

### 3.7 quiz_sessions (학습 세션) — REQ-012, REQ-014~016, REQ-106

학습 세션 1회분의 서버 측 상태다. 테이블 이름은 호환을 위해 `quiz_sessions` 를 유지하지만 퀴즈와 플래시카드 세션을 모두 담는다 (`mode`).

| 컬럼 | 타입 | NULL | 기본값 | 제약 / 설명 |
| :--- | :--- | :---: | :--- | :--- |
| `id` | INTEGER | N | 자동 증가(rowid) | **PK** |
| `user_id` | INTEGER | N | — | **FK** → `users.id` `ON DELETE CASCADE` |
| `vocabulary_id` | INTEGER | Y | NULL | **FK** → `system_vocabularies.id` `ON DELETE CASCADE` (`fk_quiz_sessions_vocabulary`). `source='vocabulary'` 일 때 원천 단어장. 북마크·오답 복습이면 NULL. v2.0 의 `wordbook_id` 를 대체 |
| `source` | VARCHAR(16) | N | — | `'vocabulary'` \| `'bookmarks'` \| `'wrong'` \| `'due'` (`ck_quiz_sessions_source`, `due` 는 v2.2 오늘 복습). API 의 `source=all` 은 `'vocabulary'` 로 저장된다 |
| `mode` | VARCHAR(20) | N | `'quiz'` | `'quiz'` \| `'flashcard'` (`ck_quiz_sessions_mode`) |
| `direction` | VARCHAR(10) | N | `'en_to_ko'` | 요청한 출제 방향 `'en_to_ko'` \| `'ko_to_en'` \| `'mixed'` (`ck_quiz_sessions_direction`). 마이그레이션 `0002` |
| `format` | VARCHAR(10) | N | `'choice'` | 요청한 문제 형식 `'choice'` \| `'ox'` (`ck_quiz_sessions_format`). 마이그레이션 `0002` |
| `questions` | JSON | N | — | 문항 배열. 아래 구조 |
| `answers` | JSON | N | `'{}'` | 기록된 답 `{"문항번호": 값}`. 퀴즈는 선택한 보기 번호(0~3), 플래시카드는 알아요=1 / 헷갈려요=0 |
| `is_submitted` | BOOLEAN | N | — | 모든 문항에 답해 세션이 끝나면 `TRUE` |
| `expires_at` | DATETIME | N | — | UTC. 출제 시각 + 30분이며 **답을 기록할 때마다 30분씩 밀린다**(밀리초 정밀도로 맞춤). 이 시각 이후 새 답은 거부된다 (이미 푼 답은 저장되어 있다) |
| `created_at` | DATETIME | N | UTC 현재 시각(§2.2) | UTC. 출제 시각 |

**`questions` JSON 구조** (문항 1건, 서버 보관용 — 출제 응답에는 일부만 싣는다)

```json
{
  "question_id": 0,
  "word_id": 123,
  "term": "apple",
  "choices": ["사과", "배", "포도", "바나나"],
  "correct_index": 0,
  "example": "I eat an apple.",
  "example_meaning": "나는 매일 아침 사과를 먹는다.",
  "phonetic": "ˈæpəl",
  "pos": "noun"
}
```

- 플래시카드 문항은 `choices` 가 `[]`, `correct_index` 가 `null` 이다.
- **방향·형식 스냅샷 (v3.0 개정, REQ-157)**: 새 문항은 `direction`(문항의 실제 방향), `format`, `prompt`(문제 문구), `meaning`(정답 뜻)을 가진다. OX 문항은 `proposed`(제시 보기)를 더 갖고 `choices` 가 `["O","X"]`, `correct_index` 가 0(O)·1(X)이다. 한→영 문항의 `choices` 는 영단어 4개다. 읽을 때는 `question.get("direction", "en_to_ko")` 처럼 기본값을 둬 이전 세션(키 없음)을 영→한 4지선다로 읽고, `meaning` 이 없으면 `choices[correct_index]` 로 대신한다. 한→영 문항의 `term`·`example` 은 출제 응답에 싣지 않는다.
- **노출 규칙 (v2.1)**: 출제 응답(`POST /api/study/sessions`)은 `question_id`, `word_id`, `term`, `context`(예문)와 퀴즈의 `options` 만 싣는다. `correct_index`, `meaning`, `example_meaning` 은 싣지 않고, **채점 응답**(`POST .../answer`)에서만 공개한다. (플래시카드는 정답이 없으므로 뒷면 뜻을 출제 응답에 함께 싣는다.) v2.0 D11 의 "출제 응답에 정답 포함"은 폐기되었다 (D16).
- `phonetic` (v2.2) 은 **시작 시점의 `system_words.phonetic` 스냅샷**이다. 읽을 때는 `question.get("phonetic")` 로 다뤄, v2.2 이전에 만든 진행 중 세션(키 없음)은 null 로 응답한다. 퀴즈 출제 응답에는 이 값을 싣지 않고(항상 null), 채점 응답과 플래시카드 출제 응답에서만 내려간다 (REQ-144).
- `pos` (v2.2, REQ-146) 도 **시작 시점의 `system_words.pos` 스냅샷**이다. `question.get("pos")` 로 읽어 옛 세션(키 없음)은 null 로 응답한다. 발음기호와 달리 **퀴즈 출제 응답에도 싣는다**.
- `question_id` 는 0부터 시작하는 배열 위치 번호다.

**인덱스**: `PRIMARY KEY (id)`, `KEY idx_quiz_sessions_user (user_id)`, `KEY fk_quiz_sessions_vocabulary (vocabulary_id)` (FK 자동 생성)

**설계 메모**
- **멱등 기록**: 답 기록은 `BEGIN IMMEDIATE` 로 시작한 트랜잭션 안에서 `quiz_sessions` 행을 읽고 처리한다(쓰기 직렬화). 같은 문항에 같은 답을 다시 보내면 이력을 늘리지 않고 같은 응답을 돌려주며, 다른 답이면 409(`QUIZ_ANSWER_LOCKED`)다.
- **출제 규칙** (`services/session_picker.py` 순수 함수 + `services/learning_session.py`): `source=all` 은 워터폴 — 오답 풀 최대 `floor(0.3×N)`, 기학습 복습 `floor(0.1×N)` 선확보, 나머지 미학습(`order_index` 순), 모자라면 복습으로 충원, 숙련 단어는 `include_memorized=false` 일 때 제외(단 SRS 복습 기한이 지난 숙련 단어는 복습 풀로 돌아온다), 출제 후 섞는다. 복습 슬롯은 기한이 지난 단어를 오래 밀린 순으로 먼저 쓰고 기한 전 단어는 모자랄 때만 채운다 (v2.2, REQ-150). `bookmarks`/`wrong` 은 해당 풀에서 무작위로, `due` 는 기한이 도래한 단어(`next_review_at <= 지금`)만으로 고른다.
- **보기 생성**: 오답 3개는 같은 단어장의 다른 단어 뜻을 우선하고 부족하면 전체 표준 단어에서 보충하며 뜻이 같은 보기는 쓰지 않는다. 활성 단어장이 4개 미만이면 퀴즈는 출제하지 않는다 (플래시카드는 허용).
- **만료 정리**: 만료·미완료 행의 물리 삭제는 하지 않는다.

---

### 3.8 sessions (로그인 세션) — REQ-001, REQ-002

세션 쿠키 인증(REQ-001 확정)의 서버 측 저장소다 (ADR-001). 클라이언트 쿠키에는 무작위 토큰 원문을 두고, DB에는 그 토큰의 SHA-256 다이제스트만 저장한다. DB가 노출되어도 유효한 세션 토큰이 노출되지 않도록 하기 위함이다.

| 컬럼 | 타입 | NULL | 기본값 | 제약 / 설명 |
| :--- | :--- | :---: | :--- | :--- |
| `id` | BLOB(32) | N | — | **PK**. 세션 토큰의 SHA-256 다이제스트(원문 32바이트). 쿠키 원문은 저장하지 않는다. |
| `user_id` | INTEGER | N | — | **FK** → `users.id` `ON DELETE CASCADE` |
| `created_at` | DATETIME | N | UTC 현재 시각(§2.2) | UTC. 로그인 시각. |
| `expires_at` | DATETIME | N | — | UTC. 만료 시각. 기본 수명은 로그인 후 14일이다 (절대 만료, 슬라이딩 연장 없음). |

**인덱스**
- `PRIMARY KEY (id)`
- `KEY idx_sessions_user (user_id)`: 사용자별 세션 일괄 삭제(계정 삭제·전체 로그아웃)용.
- `KEY idx_sessions_expires (expires_at)`: 만료 세션 정리 작업용.

**설계 메모**
- **ORM 매핑**: 테이블 이름은 `sessions`이고, ORM 클래스는 `AuthSession`이다. SQLAlchemy의 `Session`과 이름이 겹치는 것을 피하기 위함이다 (`src/backend/models/session.py`). 설계서와 DDL에서는 테이블 이름 `sessions`를 쓰고, 코드에서는 `AuthSession`을 쓴다.
- 인증 시 `WHERE id = ? AND expires_at > (현재 UTC 시각)`으로 조회한다. 만료 세션은 조회되지 않는다.
- 로그아웃은 해당 행을 삭제한다 (REQ-002). 삭제 후에는 같은 쿠키로 접근할 수 없다.
- 만료된 행의 물리 삭제 작업은 1차에서 필요하지 않으나, 행이 누적되면 `idx_sessions_expires`로 배치 삭제한다.
- 쿠키 속성(`HttpOnly`, `SameSite=Lax`, `Secure`)은 `.env`에서 주입한다 (REQ-112). `Secure`는 HTTPS 환경에서만 켠다.

---

### 3.9 시드 데이터 (애플리케이션 데이터) — REQ-143

표준 단어장의 원본은 저장소의 JSON 파일이다 (DB 템플릿 테이블 없음, 사용자별 복제 없음).

| 파일 (`src/backend/data/seeds/`) | 내용 |
| :--- | :--- |
| `vocabularies.json` | 단어장 메타 배열: `slug`, `title`, `category`, `level`, `description`, `sort_order` |
| `words/beginner-200.json` | `beginner-200` (초급 필수 영단어 200, `ELEMENTARY`, level 1) |
| `words/intermediate-200.json` | `intermediate-200` (중급 핵심 영단어 200, `SECONDARY`, level 2) |
| `words/advanced-200.json` | `advanced-200` (고급 심화 영단어 200, `CSAT`, level 3) |
| `words/exam-core-200.json` | `exam-core-200` (시험 대비 핵심 200, `EXAM`, level 3, `sort_order` 4) — v2.2 |
| `words/business-practical-200.json` | `business-practical-200` (실무 비즈니스 영단어 200, `BUSINESS`, level 3, `sort_order` 5) — v2.2 |

- 단어 항목은 `{"term", "meaning", "example", "example_meaning"}` 에 선택 키 `"phonetic"`(v2.2, 슬래시 없는 IPA)과 `"pos"`(v2.2, 영문 소문자 품사)를 더한 것이다. 신규 2개 단어장은 6개 키가 모두 필수(관문 테스트)이고, 기존 3개는 `pos` 가 없다. `phonetic` 키가 없으면 NULL 로 해석한다. 총 **1,000단어**(기존 600 + 신규 400)이며 v2.2 시드는 1,000개 전부 `phonetic` 을 가진다. IPA 는 CMU Pronouncing Dictionary(BSD 계열)에서 변환했다 (출처 고지: 요구사항 명세 §10).
- `services/system_seed.py` 가 앱 시작 시(`lifespan` 의 `init_system_seeds`) 시드를 검증하고 적재한다. **검증에 실패하면 DB 에 아무것도 쓰지 않는다** (`SeedValidationError`).
- **멱등성**: `slug` 가 키다. 파일 내용의 SHA-256 을 `content_hash` 와 비교해 같으면 쓰기를 건너뛴다. 달라지면 단어를 갱신하고 `total_words` 를 실제 개수로 맞춘다. **`content_hash` 입력과 갱신 비교 항목에 `phonetic` 이 포함된다** (v2.2). `pos` 는 **값이 있을 때만** 단어 항목 끝에 덧붙여 해시에 넣고(갱신 비교에는 항상 포함), 그래서 `pos` 가 없는 기존 3개 단어장의 해시는 이전과 바이트 단위로 같다 (골든 해시 테스트로 고정). 키가 없는 것과 명시적 null 은 같은 내용이다. 신규 단어장은 앱 시작 시 한 번 `created` 로 적재되고, 기존 단어장의 `word_id`·`updated_at` 은 바뀌지 않는다. 값이 바뀌면 UPDATE, 시드에서 지우면 NULL 로 되돌린다. 해시 입력이 바뀐 첫 시작에는 세 단어장이 한 번 재적재된다 (실제 변경은 `phonetic` 뿐).
- 새 카테고리·단어장은 파일 추가만으로 늘린다 (스키마 변경 없음).
- 가입 시 `services/auth.py` 의 `signup()` 이 `users` 행을 만들면서 `beginner-200` 을 `active_vocabulary_id` 로 지정한다 (단어 복사 없음).
- **삭제된 자료**: `beginner_200.json` 등 구 시드와 `intermediate_1000.csv` 프리셋은 제거되었다 (REQ-123, REQ-130 폐기).

---

## 4. 요구사항 매핑

| 요구사항 | 반영 테이블 / 컬럼 / 제약 |
| :--- | :--- |
| REQ-001 | `users.nickname` UNIQUE, `users.password_hash` (bcrypt), `users.active_vocabulary_id` 초기값 |
| REQ-002 | `sessions` 전체 |
| REQ-003 | 사용자 소유 행의 `user_id` 조건 (`bookmarks`, `study_logs`, `user_word_progress`, `quiz_sessions`). `system_*` 는 공용 |
| REQ-012 | `quiz_sessions` (`mode`, `source`, `questions`, `answers`), `user_word_progress` (출제 풀 분류), `system_words.order_index` |
| REQ-014, 015 | `quiz_sessions.questions` / `answers`, 보기 생성 규칙 (§3.7) |
| REQ-016 | `study_logs` 전체(`mode` 포함), `user_word_progress` 전체, 같은 트랜잭션 갱신 |
| REQ-017, 018 | `bookmarks` 전체, `uk_bookmarks_user_word` |
| REQ-019 | `quiz_sessions.source = 'bookmarks'` |
| REQ-104 | 모든 FK 의 CASCADE / SET NULL (§1.1, §2.4) |
| REQ-105 | `uk_users_nickname`, `uk_sysvoc_slug`, `uk_sysword_vocab_term`, `uk_bookmarks_user_word`, `uk_uwp_user_word` |
| REQ-106 | 답 1건의 이력 + 진행도 + 세션 갱신을 단일 트랜잭션, 세션 행 잠금 |
| REQ-107 | 모든 DDL 은 Alembic. `alembic check` 불일치 0건 |
| REQ-108, 109 | §2.1, §2.2 |
| REQ-110 | `users.password_hash` |
| REQ-122 | `users` 삭제 시 `sessions`, `bookmarks`, `study_logs`, `user_word_progress`, `quiz_sessions` CASCADE. `system_*` 보존 |
| REQ-129 | `study_logs` 의 단어별 마지막 결과(윈도 함수) → `quiz_sessions.source = 'wrong'` |
| REQ-150 | `user_word_progress.interval_step`, `next_review_at`, `idx_uwp_user_next_review`, `quiz_sessions.source = 'due'` (§3.4, §3.7) |
| REQ-131~133 | `study_logs`, `user_word_progress`, `system_vocabularies.total_words` 서버 집계 |
| REQ-140 | `system_vocabularies` (`category` 인덱스), `user_word_progress` 집계 |
| REQ-141 | `system_words` (`idx_sysword_vocab_order`), `bookmarks` 조인 |
| REQ-142 | `users.active_vocabulary_id` (`ON DELETE SET NULL`) |
| REQ-143 | `system_vocabularies.slug`, `content_hash`, 시드 파일 (§3.9) |
| REQ-145 | `system_vocabularies` 2행 추가(`category` `EXAM`·`BUSINESS`), `system_words.pos`, 시드 파일 2개 (§3.3, §3.9) |

---

## 5. DDL (현행 스키마, `alembic upgrade head` 가 만든 SQLite 스키마를 그대로 덤프)

> 이 절은 손으로 쓰지 않고 `sqlite_master` 에서 덤프했다. 모델과 어긋나면 `alembic check` 가 실패한다.

```sql
CREATE TABLE system_vocabularies (
	id INTEGER NOT NULL, 
	slug VARCHAR(50) COLLATE "NOCASE" NOT NULL, 
	title VARCHAR(100) NOT NULL, 
	category VARCHAR(50) NOT NULL, 
	level INTEGER DEFAULT 1 NOT NULL, 
	description VARCHAR(255), 
	total_words INTEGER DEFAULT 0 NOT NULL, 
	sort_order INTEGER DEFAULT 0 NOT NULL, 
	content_hash VARCHAR(64), 
	created_at DATETIME DEFAULT (strftime('%Y-%m-%d %H:%M:%f000', 'now')) NOT NULL, 
	updated_at DATETIME DEFAULT (strftime('%Y-%m-%d %H:%M:%f000', 'now')) NOT NULL, source VARCHAR(10) DEFAULT 'seed' NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_sysvoc_title_not_blank CHECK (length(trim(title)) > 0), 
	CONSTRAINT ck_sysvoc_level_range CHECK (level BETWEEN 1 AND 5), 
	CONSTRAINT uk_sysvoc_slug UNIQUE (slug)
);

CREATE TABLE system_words (
	id INTEGER NOT NULL, 
	vocabulary_id INTEGER NOT NULL, 
	term VARCHAR(100) COLLATE "NOCASE" NOT NULL, 
	meaning VARCHAR(200) NOT NULL, 
	example VARCHAR(500), 
	example_meaning VARCHAR(500), 
	pos VARCHAR(20), 
	phonetic VARCHAR(100), 
	level INTEGER, 
	order_index INTEGER DEFAULT 0 NOT NULL, source VARCHAR(10) DEFAULT 'seed' NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_sysword_not_blank CHECK (length(trim(term)) > 0 AND length(trim(meaning)) > 0), 
	CONSTRAINT fk_sysword_vocabulary FOREIGN KEY(vocabulary_id) REFERENCES system_vocabularies (id) ON DELETE CASCADE, 
	CONSTRAINT uk_sysword_vocab_term UNIQUE (vocabulary_id, term)
);

CREATE TABLE users (
	id INTEGER NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	nickname VARCHAR(50) COLLATE "NOCASE" NOT NULL, 
	active_vocabulary_id INTEGER, 
	quiz_count INTEGER DEFAULT (10) NOT NULL, 
	flashcard_count INTEGER DEFAULT (10) NOT NULL, 
	daily_goal INTEGER DEFAULT (10) NOT NULL, 
	created_at DATETIME DEFAULT (strftime('%Y-%m-%d %H:%M:%f000', 'now')) NOT NULL, 
	updated_at DATETIME DEFAULT (strftime('%Y-%m-%d %H:%M:%f000', 'now')) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_users_daily_goal_positive CHECK (daily_goal > 0), 
	CONSTRAINT ck_users_flashcard_count_positive CHECK (flashcard_count > 0), 
	CONSTRAINT ck_users_nickname_not_blank CHECK (length(trim(nickname)) > 0), 
	CONSTRAINT ck_users_quiz_count_positive CHECK (quiz_count > 0), 
	CONSTRAINT fk_users_active_vocabulary FOREIGN KEY(active_vocabulary_id) REFERENCES system_vocabularies (id) ON DELETE SET NULL, 
	CONSTRAINT uk_users_nickname UNIQUE (nickname)
);

CREATE TABLE bookmarks (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	word_id INTEGER NOT NULL, 
	created_at DATETIME DEFAULT (strftime('%Y-%m-%d %H:%M:%f000', 'now')) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT fk_bookmarks_user FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	CONSTRAINT fk_bookmarks_word FOREIGN KEY(word_id) REFERENCES system_words (id) ON DELETE CASCADE, 
	CONSTRAINT uk_bookmarks_user_word UNIQUE (user_id, word_id)
);

CREATE TABLE quiz_sessions (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	vocabulary_id INTEGER, 
	source VARCHAR(16) NOT NULL, 
	mode VARCHAR(20) DEFAULT 'quiz' NOT NULL, 
	questions JSON NOT NULL, 
	answers JSON DEFAULT '{}' NOT NULL, 
	is_submitted BOOLEAN NOT NULL, 
	expires_at DATETIME NOT NULL, 
	created_at DATETIME DEFAULT (strftime('%Y-%m-%d %H:%M:%f000', 'now')) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_quiz_sessions_mode CHECK (mode IN ('quiz', 'flashcard')), 
	CONSTRAINT ck_quiz_sessions_source CHECK (source IN ('vocabulary', 'bookmarks', 'wrong', 'due')), 
	CONSTRAINT fk_quiz_sessions_user FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	CONSTRAINT fk_quiz_sessions_vocabulary FOREIGN KEY(vocabulary_id) REFERENCES system_vocabularies (id) ON DELETE CASCADE
);

CREATE TABLE sessions (
	id BLOB NOT NULL, 
	user_id INTEGER NOT NULL, 
	created_at DATETIME DEFAULT (strftime('%Y-%m-%d %H:%M:%f000', 'now')) NOT NULL, 
	expires_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT fk_sessions_user FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE study_logs (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	word_id INTEGER NOT NULL, 
	is_correct BOOLEAN NOT NULL, 
	mode VARCHAR(20) DEFAULT 'quiz' NOT NULL, 
	created_at DATETIME DEFAULT (strftime('%Y-%m-%d %H:%M:%f000', 'now')) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_study_logs_mode CHECK (mode IN ('quiz', 'flashcard')), 
	CONSTRAINT fk_study_logs_user FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	CONSTRAINT fk_study_logs_word FOREIGN KEY(word_id) REFERENCES system_words (id) ON DELETE CASCADE
);

CREATE TABLE user_word_progress (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	word_id INTEGER NOT NULL, 
	correct_count INTEGER DEFAULT 0 NOT NULL, 
	wrong_count INTEGER DEFAULT 0 NOT NULL, 
	consecutive_correct_count INTEGER DEFAULT 0 NOT NULL, 
	is_memorized BOOLEAN DEFAULT 0 NOT NULL, 
	last_result VARCHAR(7), 
	last_studied_at DATETIME, 
	interval_step INTEGER DEFAULT 0 NOT NULL, 
	next_review_at DATETIME, 
	PRIMARY KEY (id), 
	CONSTRAINT fk_uwp_user FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	CONSTRAINT fk_uwp_word FOREIGN KEY(word_id) REFERENCES system_words (id) ON DELETE CASCADE, 
	CONSTRAINT uk_uwp_user_word UNIQUE (user_id, word_id), 
	CONSTRAINT uwp_last_result CHECK (last_result IN ('CORRECT', 'WRONG'))
);

CREATE INDEX idx_sysvoc_category ON system_vocabularies (category);

CREATE INDEX idx_sysword_vocab_order ON system_words (vocabulary_id, order_index);

CREATE INDEX idx_bookmarks_word ON bookmarks (word_id);

CREATE INDEX idx_quiz_sessions_user ON quiz_sessions (user_id);

CREATE INDEX idx_sessions_expires ON sessions (expires_at);

CREATE INDEX idx_sessions_user ON sessions (user_id);

CREATE INDEX idx_study_logs_user_created ON study_logs (user_id, created_at);

CREATE INDEX idx_study_logs_word ON study_logs (word_id);

CREATE INDEX idx_uwp_user_memorized ON user_word_progress (user_id, is_memorized);

CREATE INDEX idx_uwp_user_next_review ON user_word_progress (user_id, next_review_at);

CREATE INDEX idx_uwp_user_result ON user_word_progress (user_id, last_result);

CREATE INDEX idx_uwp_word ON user_word_progress (word_id);
```

### 5.1 마이그레이션 이력

| 리비전 | 내용 |
| :--- | :--- |
| **`0001`** (v3.0) | SQLite 초기 스키마. 위 DDL 의 8개 테이블과 인덱스를 한 번에 만든다. 빈 DB 에서 `alembic upgrade head` 한 번으로 시작하며(VOCA-NFR-003), 컨테이너는 시작할 때 `docker-entrypoint.sh` 가 이를 실행한다. |
| `0002` (v3.0 개정) | `quiz_sessions`·`study_logs` 에 출제 방향·형식 컬럼 (REQ-157) |
| `0003` (v3.0 개정) | `system_vocabularies`·`system_words` 에 `source` 컬럼 (REQ-160·161). **테이블을 재작성하지 않고 `ADD COLUMN`** 만 쓴다: 재작성은 `COLLATE NOCASE` 를 잃고 `ON DELETE CASCADE` 로 학습 이력을 지울 위험이 있다 (ADR-012) |

**이력 압축**: v2.2 까지의 MySQL 리비전 12개(`08e3374f8644` … `a7d3f1c9e5b2`)는 MySQL 전용 구문(`mysql.BIGINT`, `UTC_TIMESTAMP`, `JSON_OBJECT`, `ENGINE=InnoDB`)을 담고 있어 SQLite 에서 실행할 수 없으므로 `0001` 하나로 재작성했다. 옛 리비전 파일은 git 이력(커밋 `d1e58dc` 이전)에, 옛 스키마의 DDL 은 `docs/old/voda-voca_Data_Design_v2.2_261119.md` 에 남아 있다. 기존 MySQL 데이터는 이관하지 않는다(D20).

---

## 6. 확정 결정 기록 (Resolved) 및 후속 과제

### 6.1 확정 결정

| # | 질문 | 확정 결정 | 반영 위치 |
| :-: | :--- | :--- | :--- |
| D1 | 단어장 이름의 사용자별 중복 | **폐기** (v2.1) — 개인 단어장 없음. 단어장 식별은 `slug` UNIQUE | §3.2 |
| D2 | 대소문자 무시 동작 수용 | **수용**. v3.0 부터 `COLLATE NOCASE`(ASCII 한정). `uk_sysword_vocab_term` 에 적용. 악센트 무시는 앱 정규화로 이전 | §2.1, §3.3 |
| D3 | 북마크 소유권 검증 | **폐기** (v2.1) — 대상이 공용 단어라 검증 불필요 | §3.5 |
| D4 | 최근 학습 목록 조회 | 쿼리로 처리. `study_logs (user_id, created_at)` 인덱스 | §3.6 |
| D5 | 검색 성능 | **폐기** (v2.1) — 표제어 검색 API 없음 | §2.5 |
| D6 | 세션 상태 저장 | **DB 테이블** `quiz_sessions`. 만료와 멱등 기록을 DB 로 보장 | §3.7 |
| D7 | 퀴즈 문항 수 규칙 | 기본 15, 최대 30. 활성 단어장 단어가 4개 미만이면 퀴즈 거부 | §3.7 |
| D8 | 오답 보기 범위 | 같은 단어장 우선, 부족하면 전체 표준 단어에서 보충 | §3.7 |
| D9 | 회원 식별 | **닉네임 고유 키**. 마이그레이션 `3384caa6f116` | §3.1 |
| D10 | 기본 단어장 원본 | **v2.1 대체**: 저장소 JSON 시드를 서버가 적재하는 공용 카탈로그. 가입 시 복제하지 않고 `active_vocabulary_id` 만 지정 | §3.9 |
| D11 | 퀴즈 정답 노출 | **v2.1 대체 → D16** | §3.7 |
| D12 | 오답 복습 원천 | **v2.1 대체**: 단어별 **마지막 결과가 오답**인 단어 (기간 제한 없음) | §3.6 |
| D13 | 추천 1,000제 | **폐기** (v2.1) | — |
| D14 | 예문 뜻 저장 | 예문이 없으면 예문 뜻은 저장하지 않는다 (NULL). 시드 검증 규칙 | §3.3 |
| D15 | 통계 집계 범위 | **v2.1 대체**: 서버가 전체 이력에서 집계 (최근 100건 제한 없음) | §3.6 |
| D16 | 정답 노출 (v2.1) | 출제 응답에는 정답·해설을 싣지 않고, 채점 응답에서만 공개한다 | §3.7 |
| D17 | 숙련 판정 (v2.1) | 연속 정답 3회 = 숙련, 오답 1회면 연속 0·숙련 해제 | §3.4 |
| D18 | 개인 데이터 이관 (v2.1) | 이관하지 않고 초기화. `words` 의 id 가 `system_words` 와 대응되지 않으며 개발 DB 였다 | §5.1 |
| D20 | DBMS 전환 (v3.0) | **SQLite 채택**. 과제 서버 규칙(DB 는 SQLite). 과제용은 빈 DB 에서 시작하고 기존 MySQL 데이터는 이관하지 않는다. MySQL 이중 지원은 하지 않는다 (ADR-010) | §2, §5 |
| D21 | 행 잠금 대체 (v3.0) | `SELECT ... FOR UPDATE` 대신 모든 트랜잭션을 `BEGIN IMMEDIATE` 로 시작해 쓰기를 직렬화한다. 대가: 읽기 요청도 쓰기 잠금을 잠깐 잡는다 | §2.3 |
| D19 | 간격 반복 저장 (v2.2) | `user_word_progress` 에 `interval_step`(0~5)·`next_review_at` 컬럼으로 둔다. 별도 테이블을 만들지 않으며 `is_memorized` 는 단계로 흡수하지 않는다 (ADR-006) | §3.4 |

### 6.2 후속 과제

| # | 과제 | 내용 | 조치 주체 |
| :-: | :--- | :--- | :--- |
| F1 | 서버 기본 collation 정합 | **폐기 (v3.0)** — MySQL 서버가 없다 | 폐기 |
| F2 | 간격 반복 | **완료 (v2.2, REQ-150)**: `interval_step`, `next_review_at` 추가, `due` 출처 | 완료 |
| F3 | 확장 필드 | `system_words.level` 만 DDL 에 있고 미사용 (`phonetic` 은 REQ-144, `pos` 는 REQ-145 로 v2.2 부터 사용). `pos` 의 API·화면 노출은 REQ-146 으로 완료 | 후속 |
| F4 | 만료 세션 정리 | `quiz_sessions` 물리 삭제 배치 | 후속 |

---

## 7. 변경 이력

| 버전 | 날짜 | 내용 | 작성 |
| :--- | :--- | :--- | :--- |
| v3.0 개정 | 2026-11-26 | `system_vocabularies.source`, `system_words.source` 추가(마이그레이션 `0003`, REQ-160·161), §1·§3.2·§3.3·§5 갱신 | Claude |
| v3.0 개정 | 2026-11-25 | **출제 방향·형식 컬럼(REQ-157, 마이그레이션 `0002`)**: `quiz_sessions.direction`·`format`, `study_logs.direction`·`format` 추가(NOT NULL, 기본 `en_to_ko`·`choice`, CHECK 제약). 기존 행은 기본값으로 채워진다. `questions` 스냅샷 키 `direction`·`format`·`prompt`·`meaning`·`proposed` 추가 | Claude |
| **v3.0** | 2026-11-25 | **SQLite 전환(ADR-010)**: 타입(INTEGER PK/FK, DATETIME UTC 마이크로초, VARCHAR+CHECK), 대소문자 정책(`NOCASE`), 시간 기본값(`strftime`), 외래키 PRAGMA, `BEGIN IMMEDIATE` 동시성, §5 DDL 을 실제 스키마 덤프로 교체, 마이그레이션 12개를 `0001` 하나로 압축. 테이블·컬럼 의미 변경 없음. D20~D21 추가, F1 폐기 | Claude |
| v2.2 개정 | 2026-11-19 | **SRS 복습 시각 규칙 개정(REQ-150)**: `next_review_at` 을 한국 날짜 0시로 맞추고 기한 전 정답은 단계·시각 유지. §3.4 규칙·컬럼 설명 갱신. **스키마·마이그레이션 변경 없음** | Claude |
| v2.2 | 2026-11-19 | v2.1 개정분(2026-11-06~11-11)을 v2.2 로 확정, 파일명 `v2.2_261119` (구버전 `docs/old/` 보관). **간격 반복 반영(REQ-150)**: `user_word_progress.interval_step`·`next_review_at`·인덱스(`f4c8b2d6a1e7`), `quiz_sessions.source` 에 `due`(`a7d3f1c9e5b2`), D19, F2 완료, §3.4 복습 단계 규칙, DDL·마이그레이션 이력 갱신 | Claude |
| v2.1 개정 | 2026-11-10 | `system_words.pos` 를 API·화면에 노출 (REQ-146). `quiz_sessions.questions` 스냅샷 키 `pos` 추가(퀴즈 출제에도 싣는 점이 `phonetic` 과 다름, 옛 세션은 키 없음→null). 스키마·마이그레이션 변경 없음 | Claude |
| v2.1 개정 | 2026-11-10 | 기존 600단어에 `pos` 를 채움. 기존 3개 단어장의 `content_hash` 가 바뀌어 시작 시 `system_words` 가 UPDATE 된다 (`word_id` 불변, 진행 기록 유지). 허용 품사 `pronoun`·`interjection` 추가. 스키마·마이그레이션 변경 없음 | Claude |
| v2.1 개정 | 2026-11-10 | `users` 에 학습 개수 설정 컬럼 3종 추가 (REQ-147, `e2b6d4a9f1c3`). 기본 10, 허용 값은 앱이 검증. 스냅샷·다른 테이블 변경 없음 | Claude |
| v2.1 개정 | 2026-11-10 | 시험 대비·실무 비즈니스 단어장 2개 추가(REQ-145, v2.2 카탈로그 확충): 시드 파일 2개·총 1,000단어, `system_words.pos` 사용 개시(영문 소문자, API 미노출), `content_hash` 에 `pos` 를 값이 있을 때만 포함해 기존 해시 불변. 카테고리 값 `EXAM`·`BUSINESS`. **스키마·마이그레이션 변경 없음** | Claude |
| v2.1 개정 | 2026-11-06 | `system_words.phonetic` 사용 개시 (REQ-144, v2.2 발음기호). 저장 형식(슬래시 없는 미국식 IPA, VARCHAR(100), NULL 허용)과 시드 검증, `content_hash`·갱신 규칙에 `phonetic` 포함, `quiz_sessions.questions` 스냅샷 키 `phonetic` 추가(옛 세션은 키 없음→null). **스키마·마이그레이션 변경 없음** (컬럼은 `b1e5c0a7d2f4` 에서 이미 같은 규격) | Claude |
| v2.1 | 2026-11-05 | 중앙 제공형 단어장 전환 반영. `wordbooks`, `words` 제거(`d1a8e3f5c7b9`), `system_vocabularies`, `system_words`, `user_word_progress` 신설, `users.active_vocabulary_id` 추가, `study_logs`/`bookmarks` FK 를 `system_words` 로 전환, `study_logs.mode`, `quiz_sessions` 의 `vocabulary_id`·`mode`·`answers` 반영, 출제 응답 정답 비노출(D16), 숙련 규칙(D17), 시드 구조 개정. ERD·DDL 은 실제 DB 와 대조. 요구사항 명세 v2.1 과 정합 | Claude |
| v2.0 | 2026-11-02 | `words.example_meaning` 추가, 퀴즈 문항 JSON `example_meaning`, 시드 형식 명시, D14~D15 | Claude |
| v1.4 이하 | 2026-11-02 | `docs/old/voda-voca_Data_Design_v1.4_261102.md` 등 보관본 참조 | Claude |
