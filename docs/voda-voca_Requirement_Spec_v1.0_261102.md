# 요구사항 명세서 (Requirement Spec) — 초안

| 항목 | 내용 |
| :--- | :--- |
| 프로젝트 | voda-voca (보다보카, 웹 기반 단어장 서비스) |
| 문서 종류 | 요구사항 명세서 (Requirement Spec, `개발방법론.md` §2.2) |
| 버전 / 상태 | v1.0 / **승인 (Approved)** |
| 작성일 | 2026-11-02 |
| 승격 예정 경로 | `docs/voda-voca_Requirement_Spec_v1.0_261102.md` (승인 후 `mv` 및 `git add`) |

> **작성 원칙**: 본 문서의 요구사항 ID는 이후 모든 비즈니스 로직, API, 테스트 케이스의 추적 키로 사용한다 (`개발방법론.md` §3-1).
> 사용자가 명시하지 않은 항목은 **기본값(가정)** 으로 채우고 `[확인 필요]`로 표시했다. 승인 전 §6 질의 사항을 확정한다.

---

## 1. 목적 및 범위

### 1.1 목적
모바일 기기에서도 편하게 사용할 수 있는 웹 단어장 서비스를 제공한다. 사용자는 단어장을 만들고 단어를 관리하며, 플래시카드와 퀴즈로 학습하고, 중요한 단어를 북마크할 수 있다.

### 1.2 범위 (In Scope)
- 다중 사용자 접속 및 사용자별 데이터 분리
- 단어장 및 단어의 CRUD
- 플래시카드 학습 / 객관식 퀴즈 학습
- 단어 북마크 및 북마크 기반 학습
- 모바일 뷰포트 우선 반응형 UI

### 1.3 범위 외 (Out of Scope, 1차 릴리스)
- 단어장 공유 및 협업 편집 `[확인 필요]`
- 소셜 로그인, 이메일 인증 메일 발송 `[확인 필요]`
- 네이티브 앱(iOS/Android) 배포
- 외부 사전 API 연동을 통한 뜻 자동 완성

### 1.4 기술 제약 (CLAUDE.md 기준)
| 계층 | 기술 |
| :--- | :--- |
| Backend | Python FastAPI, SQLAlchemy 2.0 (asyncmy), Alembic |
| Frontend | HTML5, Vanilla JavaScript (ES6+), JSDoc, 빌드 파이프라인 없음 |
| UI | Tailwind CSS (Play CDN), SweetAlert2, Lucide Icons |
| DB | MySQL 8.x (Docker 컨테이너, utf8mb4, Asia/Seoul) |
| 운영 | WSL2 Ubuntu 24.04, Docker Compose, pytest |

---

## 2. 이해관계자 및 사용자 역할

| 역할 | 설명 | 주요 관심사 |
| :--- | :--- | :--- |
| 일반 학습자 (Learner) | 단어장을 만들고 학습하는 주 사용자 | 모바일에서 빠른 학습, 단어 관리 편의 |
| 운영자/개발자 (Operator) | Docker 환경을 구성하고 서비스를 운영 | 컨테이너 기동, 마이그레이션, 로그 확인 |

`[확인 필요]` 관리자(Admin) 역할 도입 여부. 본 초안에서는 제외했다.

---

## 3. 사용자 시나리오 (핵심)

- **S-01 신규 학습자 시작**: 회원 가입 → 로그인 → 첫 단어장 생성 → 단어 5개 추가
- **S-02 이동 중 학습**: 모바일에서 로그인 → 단어장 선택 → 플래시카드로 한 단어씩 넘기며 암기
- **S-03 실력 점검**: 단어장 선택 → 객관식 퀴즈 10문항 → 결과 확인 → 틀린 단어 북마크
- **S-04 중점 복습**: 북마크 목록 → 북마크 단어만 플래시카드 또는 퀴즈 진행

---

## 4. 기능 요구사항 (Functional Requirements)

우선순위: **M** = 필수(Must), **S** = 권장(Should)

### 4.1 계정 (Account)

| ID | 요구사항 | 우선순위 | 상세 기준 (Acceptance Criteria) |
| :--- | :--- | :---: | :--- |
| REQ-001 | 회원 가입 | M | 아이디(이메일 형식), 비밀번호, 닉네임을 입력받아 계정을 생성한다. 중복 이메일은 거부한다. `[확인 필요]` 인증 방식 (세션 쿠키 가정) |
| REQ-002 | 로그인 / 로그아웃 | M | 올바른 자격 증명 시 인증 상태를 부여하고, 로그아웃 시 무효화한다. 실패 시 어떤 항목이 틀렸는지 노출하지 않는다. |
| REQ-003 | 사용자별 데이터 격리 | M | 로그인한 사용자는 본인 소유 단어장/단어/북마크만 조회·수정·삭제할 수 있다. 타 사용자 리소스 접근 시 403 또는 404를 반환한다. |

### 4.2 단어장 (Wordbook)

| ID | 요구사항 | 우선순위 | 상세 기준 (Acceptance Criteria) |
| :--- | :--- | :---: | :--- |
| REQ-004 | 단어장 생성 | M | 단어장 이름(1~50자, 필수)과 설명(0~200자, 선택)을 입력받아 생성한다. |
| REQ-005 | 단어장 목록 조회 | M | 본인 단어장 목록을 최근 수정순으로 페이지 단위 조회한다. 기본 페이지 크기 20 `[확인 필요]`. |
| REQ-006 | 단어장 수정 | M | 이름과 설명을 수정한다. 수정 시각을 갱신한다. |
| REQ-007 | 단어장 삭제 | M | 삭제 시 소속 단어와 북마크도 함께 삭제한다. 삭제 전 확인 모달(SweetAlert2)을 띄운다. `[확인 필요]` 하드 삭제 vs 소프트 삭제 (본 초안: 하드 삭제) |

### 4.3 단어 (Word)

| ID | 요구사항 | 우선순위 | 상세 기준 (Acceptance Criteria) |
| :--- | :--- | :---: | :--- |
| REQ-008 | 단어 추가 | M | 표제어(영문/원어, 1~100자, 필수), 뜻(1~200자, 필수), 예문(0~500자, 선택)을 입력받아 단어장에 추가한다. 동일 단어장 내 표제어 중복은 거부한다. |
| REQ-009 | 단어 목록 조회 및 검색 | M | 단어장 내 단어를 목록으로 보여주고, 표제어 또는 뜻으로 부분 일치 검색을 지원한다. |
| REQ-010 | 단어 수정 | M | 표제어, 뜻, 예문을 수정한다. 수정 후 표제어 중복 규칙을 다시 검증한다. |
| REQ-011 | 단어 삭제 | M | 단어를 삭제하면 해당 단어의 북마크도 함께 삭제한다. |

### 4.4 학습 (Study)

| ID | 요구사항 | 우선순위 | 상세 기준 (Acceptance Criteria) |
| :--- | :--- | :---: | :--- |
| REQ-012 | 플래시카드 학습 | M | 카드 앞면(표제어)을 보여주고, 탭하면 뒷면(뜻·예문)을 뒤집어 보여준다. 좌우 스와이프 또는 버튼으로 이전/다음 카드로 이동한다. |
| REQ-013 | 플래시카드 셔플 | S | 셔플 버튼으로 카드 순서를 무작위로 섞는다. 셔플 해제 시 원래 순서로 복원한다. |
| REQ-014 | 객관식 퀴즈 | M | 표제어를 보여주고 뜻 4지선다 중 하나를 고르게 한다. 오답 3개는 같은 단어장의 다른 단어 뜻에서 무작위로 추출한다. 단어장이 4개 미만이면 퀴즈를 시작할 수 없다는 안내를 띄운다. |
| REQ-015 | 퀴즈 결과 | M | 문항 종료 후 정답 수, 오답 목록, 정답률을 보여준다. |
| REQ-016 | 학습 이력 기록 | S | 단어별 정답/오답 누적 횟수와 마지막 학습 일시를 저장한다. `[확인 필요]` 본 초안 범위에 포함할지 여부 |

### 4.5 북마크 (Bookmark)

| ID | 요구사항 | 우선순위 | 상세 기준 (Acceptance Criteria) |
| :--- | :--- | :---: | :--- |
| REQ-017 | 북마크 토글 | M | 단어 카드 또는 목록에서 북마크를 켜거나 끈다. 같은 단어에 중복 북마크는 생성되지 않는다. |
| REQ-018 | 북마크 목록 조회 | M | 본인 북마크 단어 전체를 단어장 이름과 함께 보여준다. |
| REQ-019 | 북마크 기반 학습 | S | 북마크 목록에서 플래시카드 또는 퀴즈를 시작할 수 있다. 북마크 단어가 4개 미만이면 퀴즈 대신 플래시카드만 허용한다. |

### 4.6 UI / 모바일 (User Interface)

| ID | 요구사항 | 우선순위 | 상세 기준 (Acceptance Criteria) |
| :--- | :--- | :---: | :--- |
| REQ-020 | 모바일 뷰포트 반응형 레이아웃 | M | 360px ~ 430px 폭의 모바일에서 가로 스크롤 없이 모든 주요 화면을 사용할 수 있다. 태블릿·데스크톱에서도 같은 기능을 제공한다. |
| REQ-021 | 터치 인터랙션 | M | 탭, 스와이프 제스처를 지원한다. 300ms 탭 딜레이는 `viewport` 메타 태그와 `touch-action`으로 제거한다. |
| REQ-022 | 알림·확인 UI | M | 브라우저 기본 `alert` / `confirm` 대신 SweetAlert2 모달을 사용한다. |
| REQ-023 | 아이콘 | S | 주요 액션 아이콘은 Lucide Icons로 표시한다. |

---

## 5. 비기능 요구사항 (Non-Functional Requirements)

### 5.1 성능 / 비동기 처리

| ID | 요구사항 | 우선순위 | 상세 기준 |
| :--- | :--- | :---: | :--- |
| REQ-101 | 비동기 API 처리 | M | FastAPI의 `async` 엔드포인트와 SQLAlchemy 2.0 비동기 엔진(asyncmy)을 사용하여 DB I/O 동안 이벤트 루프가 블로킹되지 않아야 한다. |
| REQ-102 | 응답 시간 | M | 동시 사용자 50명 가정 시, 단어·단어장 CRUD API의 p95 응답 시간 300ms 이하 `[확인 필요]` 목표 수치 |
| REQ-103 | 목록 조회 성능 | S | 단어 1,000개를 가진 단어장의 목록 조회는 페이지네이션을 적용한다. |

### 5.2 데이터 무결성 (MySQL)

| ID | 요구사항 | 우선순위 | 상세 기준 |
| :--- | :--- | :---: | :--- |
| REQ-104 | 참조 무결성 | M | 단어장·단어·북마크 간 외래키(FK)를 정의하고, 부모 삭제 시 `ON DELETE CASCADE`로 자식을 함께 정리한다. |
| REQ-105 | 중복 방지 제약 | M | `(wordbook_id, term)` 유일성, `(user_id, word_id)` 북마크 유일성을 DB 제약(UNIQUE)으로 강제한다. 애플리케이션 검사만으로 대체하지 않는다. |
| REQ-106 | 트랜잭션 일관성 | M | 단어장 삭제, 퀴즈 결과 저장 등 여러 행을 변경하는 작업은 단일 트랜잭션으로 수행하여 부분 반영을 막는다. |
| REQ-107 | 스키마 버전 관리 | M | 모든 스키마 변경은 Alembic 마이그레이션으로만 수행한다. 수동 `ALTER`를 금지한다. |
| REQ-108 | 문자셋 및 시간대 | M | DB 문자셋은 `utf8mb4` (`utf8mb4_unicode_ci`), 세션 시간대는 `+09:00`(Asia/Seoul)로 설정한다. 한글과 이모지 저장이 깨지지 않아야 한다. |
| REQ-109 | 시각 저장 기준 | S | 모든 시각 컬럼은 UTC 기준으로 저장하고, 화면 표시 시 Asia/Seoul로 변환한다 `[확인 필요]` DB 세션 시간대(+09:00)와 중 하나로 통일 |

### 5.3 보안

| ID | 요구사항 | 우선순위 | 상세 기준 |
| :--- | :--- | :---: | :--- |
| REQ-110 | 비밀번호 저장 | M | 비밀번호는 bcrypt 또는 argon2로 해시하여 저장한다. 평문 저장을 금지한다. |
| REQ-111 | 입력 검증 | M | 모든 API 입력은 Pydantic 스키마로 검증한다. 길이·형식 제약은 §4의 기준을 따른다. |
| REQ-112 | 설정 값 관리 | M | DB 접속 정보, 비밀 키, 포트는 `.env`로 주입하며 소스 코드에 하드코딩하지 않는다. 저장소에는 `.env.example`만 커밋한다. |
| REQ-113 | SQL 인젝션 방지 | M | ORM 파라미터 바인딩을 사용하고, 문자열 결합으로 SQL을 만들지 않는다. |

### 5.4 모바일 / 접근성

| ID | 요구사항 | 우선순위 | 상세 기준 |
| :--- | :--- | :---: | :--- |
| REQ-114 | 터치 타겟 크기 | M | 버튼과 링크의 터치 영역은 최소 44×44px이다. |
| REQ-115 | 가독성 | S | 본문 글자 크기는 모바일에서 16px 이상을 기본으로 한다. |

### 5.5 운영 / 환경

| ID | 요구사항 | 우선순위 | 상세 기준 |
| :--- | :--- | :---: | :--- |
| REQ-116 | 컨테이너 격리 | M | MySQL은 Docker 컨테이너로 실행하며, 애플리케이션은 컨테이너 네트워크 또는 `.env`에 지정된 호스트/포트로 접속한다. |
| REQ-117 | 로컬 실행 환경 | M | WSL2 Ubuntu 24.04 + Docker Compose 환경에서 단일 명령으로 DB를 기동할 수 있어야 한다. |

### 5.6 품질 / 테스트

| ID | 요구사항 | 우선순위 | 상세 기준 |
| :--- | :--- | :---: | :--- |
| REQ-118 | 자동화 테스트 | M | 백엔드 핵심 로직은 pytest 단위 테스트와 DB 연동 통합 테스트로 검증한다. `[확인 필요]` 커버리지 목표 (본 초안: 핵심 서비스 로직 80%) |
| REQ-119 | 모바일 반응형 검증 | S | 360px, 390px, 430px 폭에서 주요 화면 스크린샷 검증 절차를 테스트 정의서에 포함한다. |
| REQ-120 | 코드 추적성 | M | 구현 코드의 모듈 헤더 또는 커밋 메시지에 관련 요구사항 ID를 명시한다. |

---

## 6. 확인 필요 사항 (Open Questions)

승인 전에 사용자 확인이 필요한 항목이다. 아래 기본값은 사용자의 답변이 있을 때까지 적용된다.

| # | 질문 | 본 초안의 기본값 | 관련 ID |
| :-: | :--- | :--- | :--- |
| Q1 | 인증 방식은 무엇으로 할까요? (세션 쿠키 / JWT) | 세션 쿠키 | REQ-001, REQ-002 |
| Q2 | 단어장을 다른 사용자와 공유할 필요가 있나요? | 1차 제외 | §1.3 |
| Q3 | 단어장 삭제는 하드 삭제로 할까요, 휴지통(소프트 삭제)으로 할까요? | 하드 삭제 | REQ-007 |
| Q4 | 단어 필드는 표제어·뜻·예문으로 충분한가요? (품사, 발음 기호 추가 여부) | 표제어·뜻·예문 | REQ-008 |
| Q5 | 학습 이력(REQ-016)을 1차 릴리스에 포함할까요? | 권장(S)으로 포함 | REQ-016 |
| Q6 | 동시 접속 사용자 수와 p95 응답 목표 수치 | 50명, 300ms | REQ-102 |
| Q7 | 시각은 DB에 UTC로 저장할까요, Asia/Seoul로 저장할까요? | UTC 저장, 화면에서 KST 변환 | REQ-109 |
| Q8 | 관리자(Admin) 역할이 필요한가요? | 1차 제외 | §2 |

---

## 7. 요구사항 추적 매트릭스 (Traceability Matrix)

이 표는 요구사항 ID가 이후 설계 산출물과 테스트 케이스에 어떻게 연결되는지 정의한다. 설계와 테스트 ID는 착수 시 채운다.

| 요구사항 ID | 요구사항 요약 | 우선순위 | 설계 산출물 (예정) | 구현 위치 (예정) | 테스트 ID (예정) | 상태 |
| :--- | :--- | :---: | :--- | :--- | :--- | :---: |
| REQ-001 | 회원 가입 | M | Integration Spec, Data Design(users) | `src/backend/routers/auth.py` | TC-001 | 초안 |
| REQ-002 | 로그인 / 로그아웃 | M | Integration Spec | `src/backend/routers/auth.py` | TC-002 | 초안 |
| REQ-003 | 사용자별 데이터 격리 | M | Architecture Design | `src/backend/services/` | TC-003 | 초안 |
| REQ-004 | 단어장 생성 | M | Integration Spec, Data Design(wordbooks) | `src/backend/routers/wordbook.py` | TC-004 | 초안 |
| REQ-005 | 단어장 목록 조회 | M | Integration Spec | `src/backend/routers/wordbook.py` | TC-005 | 초안 |
| REQ-006 | 단어장 수정 | M | Integration Spec | `src/backend/routers/wordbook.py` | TC-006 | 초안 |
| REQ-007 | 단어장 삭제 | M | Integration Spec, Data Design(FK cascade) | `src/backend/routers/wordbook.py` | TC-007 | 초안 |
| REQ-008 | 단어 추가 | M | Integration Spec, Data Design(words) | `src/backend/routers/word.py` | TC-008 | 초안 |
| REQ-009 | 단어 목록·검색 | M | Integration Spec | `src/backend/routers/word.py` | TC-009 | 초안 |
| REQ-010 | 단어 수정 | M | Integration Spec | `src/backend/routers/word.py` | TC-010 | 초안 |
| REQ-011 | 단어 삭제 | M | Integration Spec | `src/backend/routers/word.py` | TC-011 | 초안 |
| REQ-012 | 플래시카드 학습 | M | UI/UX 설계서 | `src/frontend/js/study-flashcard.js` | TC-012 | 초안 |
| REQ-013 | 플래시카드 셔플 | S | UI/UX 설계서 | `src/frontend/js/study-flashcard.js` | TC-013 | 초안 |
| REQ-014 | 객관식 퀴즈 | M | Integration Spec (퀴즈 출제 API) | `src/backend/services/quiz.py` | TC-014 | 초안 |
| REQ-015 | 퀴즈 결과 | M | Integration Spec | `src/frontend/js/study-quiz.js` | TC-015 | 초안 |
| REQ-016 | 학습 이력 기록 | S | Data Design(study_logs) | `src/backend/services/study_log.py` | TC-016 | 초안 |
| REQ-017 | 북마크 토글 | M | Data Design(bookmarks), Integration Spec | `src/backend/routers/bookmark.py` | TC-017 | 초안 |
| REQ-018 | 북마크 목록 | M | Integration Spec | `src/backend/routers/bookmark.py` | TC-018 | 초안 |
| REQ-019 | 북마크 기반 학습 | S | Integration Spec | `src/frontend/js/study-*.js` | TC-019 | 초안 |
| REQ-020 | 모바일 반응형 레이아웃 | M | UI/UX 설계서 | `src/frontend/*.html`, Tailwind 클래스 | TC-020 (브라우저 검증) | 초안 |
| REQ-021 | 터치 인터랙션 | M | UI/UX 설계서 | `src/frontend/js/` | TC-021 (브라우저 검증) | 초안 |
| REQ-022 | SweetAlert2 모달 | M | UI/UX 설계서 | `src/frontend/js/` | TC-022 | 초안 |
| REQ-023 | Lucide 아이콘 | S | UI/UX 설계서 | `src/frontend/*.html` | TC-023 | 초안 |
| REQ-101 | 비동기 API | M | Architecture Design | `src/backend/db/session.py` | TC-101 | 초안 |
| REQ-102 | 응답 시간 | M | Architecture Design | 부하 테스트 스크립트 | TC-102 | 초안 |
| REQ-103 | 목록 페이지네이션 | S | Integration Spec | `src/backend/routers/word.py` | TC-103 | 초안 |
| REQ-104 | 참조 무결성(FK) | M | Data Design | `src/backend/models/` | TC-104 | 초안 |
| REQ-105 | 중복 방지(UNIQUE) | M | Data Design | `src/backend/models/`, Alembic | TC-105 | 초안 |
| REQ-106 | 트랜잭션 일관성 | M | Architecture Design | `src/backend/services/` | TC-106 | 초안 |
| REQ-107 | Alembic 마이그레이션 | M | Architecture Design | `src/backend/alembic/` | TC-107 | 초안 |
| REQ-108 | 문자셋 / 시간대 | M | Data Design, `docker/docker-compose.yml` | `docker/docker-compose.yml` | TC-108 | 구현 완료 (인프라) |
| REQ-109 | 시각 저장 기준 | S | Data Design | `src/backend/models/base.py` | TC-109 | 초안 |
| REQ-110 | 비밀번호 해시 | M | Decision Records (ADR: 해시 알고리즘) | `src/backend/services/auth.py` | TC-110 | 초안 |
| REQ-111 | 입력 검증 | M | Integration Spec | `src/backend/schemas/` | TC-111 | 초안 |
| REQ-112 | 설정 값 `.env` 주입 | M | Deployment Spec (README) | `.env.example`, 설정 모듈 | TC-112 | 부분 완료 (`.env.example`, `.gitignore`) |
| REQ-113 | SQL 인젝션 방지 | M | Architecture Design | `src/backend/services/` | TC-113 | 초안 |
| REQ-114 | 터치 타겟 44px | M | UI/UX 설계서 | `src/frontend/` | TC-114 (브라우저 검증) | 초안 |
| REQ-115 | 모바일 본문 16px | S | UI/UX 설계서 | `src/frontend/` | TC-115 (브라우저 검증) | 초안 |
| REQ-116 | 컨테이너 격리 | M | Architecture Design | `docker/docker-compose.yml` | TC-116 | 구현 완료 (인프라) |
| REQ-117 | 단일 명령 기동 | M | Deployment Spec (README) | `docker/docker-compose.yml` | TC-117 | 구현 완료 (인프라) |
| REQ-118 | pytest 자동화 테스트 | M | Test Specification | `src/backend/tests/` | TC-118 | 초안 |
| REQ-119 | 모바일 스크린샷 검증 | S | Test Specification | 검증 스크립트 | TC-119 | 초안 |
| REQ-120 | 코드 추적성 (ID 명시) | M | 개발방법론 §3 | 모듈 헤더, 커밋 메시지 | 코드 리뷰 체크리스트 | 초안 |

**상태 값 정의**: `초안` (명세만 작성) / `설계 완료` / `구현 완료` / `검증 완료`.
**요구사항 ID 체계**: `REQ-0xx` = 기능 요구사항(FR), `REQ-1xx` = 비기능 요구사항(NFR). 번호는 재사용하지 않으며, 폐기 시 상태만 `폐기`로 바꾼다.

---

## 8. 변경 이력

| 버전 | 날짜 | 내용 | 작성 |
| :--- | :--- | :--- | :--- |
| v0.1 | 2026-11-02 | 초안 작성 (요구사항 ID 체계 수립, 기능/비기능 목록, 추적 매트릭스) | Claude |
| v1.0 | 2026-11-02 | 사용자 승인 후 `docs/`로 승격 (파일명 `Requirement_Spec` 규칙 적용) | Claude |
