# 테스트 정의서 (Test Specification)

| 항목 | 내용 |
| :--- | :--- |
| 프로젝트 | voda-voca (보다보카) |
| 문서 종류 | Test Specification (`개발방법론.md` §2.4, 필수 산출물: pytest 및 UI 검증) |
| 기준 문서 | `docs/voda-voca_Requirement_Spec_v2.2_261119.md` §5.6 (REQ-118~120), §7 추적 매트릭스 |
| 버전 / 상태 | v1.1 / **승인 (Approved, 2026-11-19)** |
| 작성일 | 2026-11-19 |
| 산출물 경로 | `docs/voda-voca_Test_Specification_v1.1_261119.md` (이전 버전: `docs/old/voda-voca_Test_Specification_v1.0_261119.md`) |

> **이 문서가 하는 일**: 요구사항 명세 §7 은 테스트 ID(`TC-001` 등)를 "예정"으로만 적어 두었고 정의서가 없었다. 이 문서가 TC ID 를 정의하고, 각 TC 를 실제 테스트 파일에 연결하며, **연결되지 않는 요구사항(갭)을 드러낸다.** 파일 연결은 테스트 파일의 헤더 주석과 파일 안의 `REQ-` 언급을 읽어 정리했다. 개별 테스트 케이스 단위의 전수 매핑은 아니다.

---

## 1. 테스트 전략

| 계층 | 도구 | 대상 | 위치 |
| :--- | :--- | :--- | :--- |
| 백엔드 단위 | pytest | 순수 함수: 출제(`session_picker`), SRS(`srs`), 진행도(`progress`), 비밀번호·토큰, 레이트 리미터, 스키마 검증. **`no_db` 표시**가 붙어 MySQL 없이 돈다 (175건, 약 0.5초) | `src/backend/tests/*_units.py`, `test_auth_schemas.py`, `test_config.py`, `test_db_session.py`, `test_static_mount.py`, `test_legacy_study_removed.py` |
| 백엔드 통합 | pytest + httpx, **실제 MySQL** | API 계약, 트랜잭션, 제약(FK·UNIQUE), 마이그레이션 스키마, 시드 | `src/backend/tests/test_*_api.py`, `test_system_*.py`, `test_transition_schema.py` |
| 프론트엔드 단위 | `node --test` (외부 패키지 없음) | `js/core/` 의 DOM 없는 순수 로직: API 클라이언트, 라우터, 세션 러너, 뷰모델, 저장소, 사운드, TTS | `src/frontend/tests/*.test.js` |
| 프론트엔드 소스 검사 | `node --test` | 화면 배선, 디자인 토큰, 다크 모드 색 누락, 터치 영역 등을 **소스 텍스트 수준**으로 검사 (브라우저 없음) | `dark-theme`, `design-tokens`, `*-ui.test.js`, `ui-polish.test.js` |
| 수동 (실기기) | 사람 | 시각·터치·폰트 렌더링·반응형 (자동화 불가 영역) | §6 점검 절차 |

**설계 원칙**
- 순수 로직은 DB·DOM 없이 검증되도록 분리한다 (Architecture Design §5).
- **회귀 방지 검사 우선** (CLAUDE.md §4 테스트 운용 원칙 5): 같은 종류의 누락이 반복될 수 있는 곳(다크 모드 색, 폐기된 API 제거, 옛 테이블 제거)은 개별 수정과 함께 자동 검사를 둔다. 예: `dark-theme.test.js`, `test_legacy_study_removed.py`, `test_drop_legacy_tables.py`.
- 기능 추가와 버그 수정은 실패하는 테스트를 먼저 쓴다 (Red → Green → Refactor).

## 2. 실행 방법과 범위

| 시점 | 실행 범위 | 명령 |
| :--- | :--- | :--- |
| Red/Green 반복 | 지금 쓰는 테스트 하나. 순수 단위 테스트는 DB 없이 `-m no_db` 로 | `.venv/bin/python -m pytest -q src/backend/tests/test_x.py::test_y` / `.venv/bin/python -m pytest -q -m no_db` (Docker 불필요) / `cd src/frontend && node --test tests/x.test.js` |
| 기능 단위 완료 | 영향받는 테스트 파일 | `.venv/bin/python -m pytest -q src/backend/tests/test_x.py` |
| 커밋 전 | 위 범위 + 직전 실패 우선 | `.venv/bin/python -m pytest -q --lf` |
| 푸시 전 / PR | 백엔드와 프론트엔드 전체 + **마이그레이션 일치 검사** | `.venv/bin/python -m pytest -q` / `cd src/frontend && node --test tests/` / `.venv/bin/alembic -c src/backend/alembic.ini check` |

**실행 전제 (백엔드)**
1. MySQL 컨테이너가 기동되어 healthy 여야 한다 (`docker compose --project-directory . -f docker/docker-compose.yml up -d`).
2. `alembic upgrade head` 로 스키마가 최신이어야 한다.
3. 루트 `.env` 가 있어야 한다.

**마이그레이션 일치 검사 (푸시 전)**: `alembic check` 는 코드의 모델과 실제 DB 구조가 같은지 확인하는 읽기 전용 명령이다. "No new upgrade operations detected." 가 나와야 통과다. 새 upgrade 작업이 감지되면 모델은 바꿨는데 마이그레이션을 빼먹은 것이다. 이 명령은 DB 가 최신 리비전이어야 하므로 "Target database is not up to date" 가 나오면 먼저 `alembic upgrade head` 가 필요하다 (DB 를 바꾸는 명령이라 승인 후 실행).

**`no_db` 마커**: 순수 단위 테스트는 `pytestmark = pytest.mark.no_db` 로 표시한다. DB 정리 fixture 를 건너뛰므로 MySQL 이 꺼져 있어도 돈다. 표시된 테스트가 DB 를 쓰게 되면 `test_no_db_guard.py` 가 실패한다.

**데이터 격리**: 통합 테스트는 닉네임 `tvoda-` 접두사 계정과 테스트용 표준 단어장 접두사 데이터만 만들고, 테스트 전후로 같은 패턴만 지운다 (`conftest.py`). 운영·개발 데이터를 지우지 않도록 패턴 밖은 건드리지 않는다.

**보고 규칙**: 테스트 결과는 범위와 함께 적는다 (예: "`test_study_api.py` 37건 통과"). 전체를 돌리지 않았으면 그렇게 적는다. 변경과 무관한 간헐 실패는 숨기지 않고 별도 이슈로 등록한다 (CLAUDE.md §4).

## 3. 현황 기준선 (2026-11-19 측정)

| 대상 | 파일 수 | 케이스 수 | 측정 결과 |
| :--- | :-: | :-: | :--- |
| 백엔드 `pytest -q` (전체) | 33 | **557** | **557 통과, 실패 0** (약 30~45초). 이 중 `no_db` 175건은 DB 없이 0.5초 |
| 프론트엔드 `node --test tests/` (전체) | 38 | **463** | **463 통과, 실패 0** |
| 합계 | 71 | 1,020 | 전체 통과 |

**측정 조건**
- MySQL 컨테이너 기동, `.env` 의 `MYSQL_PORT=3307`, DB 마이그레이션 head `a7d3f1c9e5b2` 적용 상태에서 실행했다.
- 측정 시점의 작업 트리는 SRS 4단계(`source=due`, 마이그레이션 `a7d3f1c9e5b2`)를 포함했고, 같은 내용이 이어서 커밋되었다.
- README 의 "510 / 456" 기록은 이전 측정값이며 위 값이 현재 기준선이다.

**백엔드 커버리지 (REQ-118 목표 80% 이상)**

| 측정 방식 | 결과 | 해석 |
| :--- | :-: | :--- |
| 기본 설정 (`--cov=backend`) | 서비스 일부가 44~68% (예: `learning_session.py` 44%) | **측정 오류.** SQLAlchemy 비동기 코드가 greenlet 에서 실행되어 coverage 가 추적하지 못한다 |
| `concurrency = greenlet,thread` + 테스트 코드 제외 | **전체 98%** (1,549문 중 미실행 27문) | 신뢰할 수 있는 값. 목표 80% 를 넘는다 |

98% 미만인 파일: `learning_session.py` 95%, `system_seed.py` 93%, `study_session.py`(라우터) 94%, `study.py`(라우터) 96%, `services/study.py` 99%. 나머지는 100% 다.

**측정 명령**: 루트의 `.coveragerc`(`concurrency = greenlet,thread`, 테스트 코드 제외)를 2026-11-19 에 추가했다. 기본 명령만으로 위 98% 가 재현된다.
```bash
.venv/bin/python -m pytest -q --cov=backend --cov-report=term
```

## 4. 테스트 케이스 정의 및 요구사항 추적

**TC ID 규칙**: `TC-{요구사항 번호}` 를 기본으로 한다 (예: REQ-121 → TC-121). 요구사항 명세 §7 이 이미 쓰는 ID 와 같다. 
**검증 구분**: `자동`(CI 가능), `소스검사`(브라우저 없는 텍스트 수준 검사), `수동`(사람), `없음`(갭).

### 4.1 계정·보안

| TC | 요구사항 | 구분 | 검증 위치 | 비고 |
| :--- | :--- | :---: | :--- | :--- |
| TC-001 | REQ-001 회원 가입 | 자동 | `test_auth_api.py`, `test_auth_schemas.py`(닉네임 2~30자, 비밀번호 8자·72바이트 경계), `validate.test.js`(같은 경계) | |
| TC-002 | REQ-002 로그인·로그아웃 | 자동 | `test_auth_api.py`, `test_auth_units.py`(세션 토큰 다이제스트) | |
| TC-003 | REQ-003 사용자별 격리 | 자동 | `test_auth_api.py`, `test_bookmark_api.py`, `test_study_logs_api.py`(사용자 분리) | |
| TC-110 | REQ-110 bcrypt | 자동 | `test_auth_units.py`, `test_auth_schemas.py` | 73바이트 거부를 스키마 단위로 검증 (`test_password_over_72_bytes_is_rejected`). API 수준 422 는 별도로 확인하지 않았다 |
| TC-111 | REQ-111 입력 검증 | 자동 | `test_auth_schemas.py`, 각 API 테스트의 422 케이스 | |
| TC-112 | REQ-112 `.env` 주입 | 자동 | `test_config.py` | 하드코딩 금지 자체는 코드 리뷰로 확인 |
| TC-113 | REQ-113 SQL 인젝션 방지 | **없음** | — | 표제어 검색 API 가 폐기되어 LIKE 이스케이프 대상이 사실상 없다. 파라미터 바인딩은 ORM 사용으로 구조적으로 보장되며 전용 테스트는 없다 |
| TC-121 | REQ-121 로그인 무차별 대입 방어 | 자동 | `test_rate_limit_units.py`(윈도우 경계, 키 독립성), `test_login_rate_limit_api.py`(429, `Retry-After`) | 단일 프로세스 한정 |
| TC-122 | REQ-122 회원 탈퇴 | 자동 | `test_auth_api.py` | 표준 콘텐츠 보존, 개인 데이터 CASCADE 삭제 |

### 4.2 학습 핵심 (표준 단어장·세션·복습)

| TC | 요구사항 | 구분 | 검증 위치 | 비고 |
| :--- | :--- | :---: | :--- | :--- |
| TC-012 | REQ-012 학습 세션 출제, 플래시카드 | 자동 | `test_learning_session_api.py`, `test_session_picker_units.py`(오답 30% 상한, 복습 10% 선확보, 미학습), `test_session_count_setting.py`, `session-runner.test.js`(상태 머신), `session-driver.test.js` | |
| TC-014 | REQ-014 객관식 퀴즈 | 자동 | `test_learning_session_api.py`, `test_study_units.py`(오답 선지 구성) | 4개 미만 거부 포함 |
| TC-015 | REQ-015 세션 결과 | 자동 | `session-view-model.test.js` | |
| TC-016 | REQ-016 학습 이력·숙련 | 자동 | `test_progress_units.py`(연속 3회 숙련, 오답 해제), `test_study_log_progress.py`(답 기록 단일 진입점), `test_study_logs_api.py`, `format-kst.test.js` | |
| TC-150 | REQ-150 SRS 단계·다음 복습 시각·오늘 복습 (ADR-006) | 자동 | `test_srs_units.py`(단계 증감, 부분 감쇠, 한국 날짜 0시 경계, 기한 전 정답 유지), `test_srs_picker_units.py`(기한 지난 단어 우선), `test_progress_units.py`, `test_study_log_progress.py`(저장되는 단계·복습 시각), `test_review_session_api.py`(`source=due`), `test_stats_api.py`(`due_review_count`), `review-model.test.js`(오늘 복습 카드) | |
| TC-017 | REQ-017 북마크 토글 | 자동 | `test_bookmark_api.py`(멱등 등록·해제), `test_bookmark_units.py`(중복·FK 충돌 분기) | |
| TC-018 | REQ-018 북마크 목록 | 자동 | `test_bookmark_api.py`, `review-model.test.js` | |
| TC-019 | REQ-019 북마크 기반 학습 | 자동 | `test_review_session_api.py` | |
| TC-124 | REQ-124 즉각 피드백·해설 | 자동 | `test_learning_session_api.py`, `session-view-model.test.js` | 출제 응답 정답 비노출(D16)은 이 파일에서 확인한다 |
| TC-129 | REQ-129 오답 복습 | 자동 | `test_review_session_api.py`, `test_stats_api.py`, `review-model.test.js`, `review-view-null.test.js`(조건부 자식 null 회귀) | |
| TC-131 | REQ-131 학습 지표 서버 집계 | 자동 | `test_stats_api.py`, `stats-page-model.test.js`, `home-model.test.js` | KST 날짜 경계 포함 |
| TC-132 | REQ-132 최근 7일 차트 | 자동 | `test_stats_api.py`, `weekly-chart.test.js` | |
| TC-133 | REQ-133 단어장 진행률·학습 시작 | 자동 | `explore-model.test.js`, `test_vocabulary_api.py` | |
| TC-140~143 | REQ-140~143 표준 단어장 카탈로그·단어·활성화·시드 | 자동 | `test_vocabulary_api.py`, `test_system_seed.py`(파일 검증, 해시, 멱등 적재), `test_system_models.py` | 시드 59건이 가장 두껍다 |
| TC-144 | REQ-144 발음기호 | 자동 | `test_phonetic_api.py`, `test_system_seed.py`, `phonetic.test.js` | 퀴즈 문제 화면에서 숨기는 규칙 포함 |
| TC-145 | REQ-145 카탈로그 확충(1,000단어) | 자동 | `test_system_seed.py` | |
| TC-146 | REQ-146 품사 | 자동 | `test_pos_api.py`, `pos.test.js` | |
| TC-147 | REQ-147 학습 개수 설정 | 자동 | `test_user_settings_api.py`, `test_user_settings_model.py`, `test_session_count_setting.py`, `settings-model/store/ui.test.js`, `home-model.test.js` | |
| TC-148 | REQ-148 세션 중 북마크 | 자동 + 소스검사 | `bookmark-store.test.js`(낙관적 갱신·롤백), `bookmark-ui.test.js`(버튼 배치) | 360px 겹침은 수동 (§6) |

### 4.3 데이터·인프라

| TC | 요구사항 | 구분 | 검증 위치 | 비고 |
| :--- | :--- | :---: | :--- | :--- |
| TC-101 | REQ-101 비동기 API | 자동 | `test_db_session.py`(예외 시 rollback → close 순서) | 이벤트 루프 비차단 자체를 재는 테스트는 없다 |
| TC-102 | REQ-102 p95 300ms (50명) | **없음** | — | 부하 테스트 스크립트가 없다. 관측 수단도 없다 (Architecture Design A7) |
| TC-103 | REQ-103 페이지네이션 | 자동 | `test_vocabulary_api.py`, `test_bookmark_api.py` | |
| TC-104/105 | REQ-104, 105 FK·UNIQUE | 자동 | `test_system_models.py`, `test_transition_schema.py`(`SHOW CREATE TABLE` 수준) | |
| TC-106 | REQ-106 트랜잭션 일관성 | 자동 | `test_study_log_progress.py`, `test_auth_api.py`(탈퇴) | |
| TC-107 | REQ-107 Alembic | 자동 + 수동 | `test_system_models.py`, `test_drop_legacy_tables.py`, 수동 `alembic check` | 모든 마이그레이션 적용 자동 검증은 없다 |
| TC-108 | REQ-108 문자셋·시간대 | 수동 | 컨테이너 설정 확인 | 실행 중 컨테이너에 반영되었는지는 F1(Data Design) 승인 대기 |
| TC-109 | REQ-109 UTC 저장, KST 표시 | 자동 | `test_stats_api.py`(KST 날짜), `format-kst.test.js` | |
| TC-116 | REQ-116 컨테이너 격리 | 자동 + 수동 | `test_health.py`(DB 연결 성공·503), `test_static_mount.py` | 컨테이너 구성은 수동 |
| TC-117 | REQ-117 단일 명령 기동 | 수동 | README §3.3 절차 | |

### 4.4 UI·모바일 (자동화 한계가 큰 영역)

| TC | 요구사항 | 구분 | 검증 위치 | 비고 |
| :--- | :--- | :---: | :--- | :--- |
| TC-020 | REQ-020 반응형 레이아웃 | 소스검사 + 수동 | `design-tokens.test.js`, §6 | 실제 렌더링은 사람이 본다 |
| TC-021 | REQ-021 터치 인터랙션 | 수동 | §6 | |
| TC-022 | REQ-022 SweetAlert2 모달 | 자동 | `toast.test.js`(토스트 래퍼) | 모달 시각은 수동 |
| TC-023 | REQ-023 Lucide 아이콘 | 자동 | `dom.test.js`(Lucide 부재에도 안전) | |
| TC-114 | REQ-114 터치 44px | 소스검사 + 수동 | `speak-ui.test.js`, `bookmark-ui.test.js` | 전 화면 전수 검사는 아니다 |
| TC-115 | REQ-115 본문 16px | 수동 | §6 | `design-tokens.test.js` 는 `--fs-body` 토큰의 존재만 검사하고 값(16px 이상)은 검사하지 않는다. 값 검사 추가는 후속 제안 |
| TC-125 | REQ-125 발음 청취(TTS) | 자동 | `tts.test.js`, `tts-state.test.js`, `speak-ui.test.js` | 실제 음성 출력은 수동 |
| TC-126 | REQ-126 다크 모드 | 자동 | `theme.test.js`, `dark-theme.test.js`(색 클래스마다 다크 규칙 존재), `ui-polish.test.js` | 색 구분은 수동 |
| TC-127 | REQ-127 키보드 단축키 | 자동 | `shortcuts.test.js`, `session-view-model.test.js` | |
| TC-134 | REQ-134 계정 메뉴 | 소스검사 | `preferences-ui.test.js`, `settings-ui.test.js` | |
| TC-137 | REQ-137 세션 효과음 | 자동 | `sound.test.js`(큐 4종 파라미터), `combo-model.test.js`, `combo-ui.test.js` | 실제 소리는 수동 |
| TC-138 | REQ-138 효과음 음소거 | 자동 | `sound.test.js`, `preferences-model.test.js` | |
| TC-149 | REQ-149 환경 설정 | 자동 + 소스검사 | `preferences-model.test.js`, `preferences-ui.test.js` | |

### 4.5 프로세스 요구사항

| TC | 요구사항 | 구분 | 검증 방법 | 현황 |
| :--- | :--- | :---: | :--- | :--- |
| TC-118 | REQ-118 자동화 테스트, **커버리지 80% 이상** | 자동 | `pytest-cov` + 루트 `.coveragerc`. 2026-11-19 측정 결과 **98%** (§3) | **목표 달성**. 임계값 도입은 §7 G1 |
| TC-119 | REQ-119 360/390/430px 스크린샷 검증 | 수동 | §6 | 체크리스트는 360·390px 만 있고 430px 과 스크린샷 보관은 없다 (§7 G3) |
| TC-120 | REQ-120 코드 추적성 | 수동 | 코드 리뷰: 모듈 헤더·커밋 메시지의 요구사항 ID | 헤더 규칙(CLAUDE.md §5.2)에는 요구사항 ID 항목이 없다 |

## 5. 핵심 시나리오 (BDD)

방법론 §2.4 가 요구하는 BDD 형식으로, 자동 테스트가 이미 보장하는 핵심 동작을 시나리오로 기록한다. 새 테스트를 만드는 문서가 아니라 **기대 동작의 합의**다.

**S1. 가입하고 바로 학습한다** (TC-001, TC-142)
- Given 닉네임 `kim` 으로 가입하지 않은 상태
- When 닉네임 `kim`, 8자 이상 비밀번호로 가입하고 로그인한다
- Then 세션 쿠키(`HttpOnly`)가 발급되고 기본 활성 단어장이 지정되어 학습을 시작할 수 있다

**S2. 퀴즈에서는 채점 전에 정답을 알 수 없다** (TC-124, ADR-005)
- Given 활성 단어장에 단어가 4개 이상이다
- When 퀴즈 세션을 만든다
- Then 출제 응답의 문항에는 정답 인덱스와 해설이 없다
- And 답을 제출하면 채점 응답에서 정답과 해설을 받는다

**S3. 틀린 단어는 복습 대상이 되고 다시 맞히면 빠진다** (TC-129, TC-016)
- Given 단어 W 를 한 번 틀렸다 (마지막 결과가 오답)
- Then W 가 오답 목록에 보인다
- When W 를 다시 맞힌다
- Then 오답 목록에서 빠진다

**S4. 연속 3번 맞히면 숙련, 한 번 틀리면 풀린다** (TC-016)
- Given 단어 W 를 2번 연속 맞혔다
- When 한 번 더 맞힌다 → Then 숙련이 된다
- When 이후 한 번 틀린다 → Then 연속 정답이 0 이 되고 숙련이 해제된다

**S5. 오답은 SRS 단계를 두 단계 낮춘다** (TC-150, ADR-006)
- Given W 의 단계가 4 (14일)다
- When W 를 틀린다
- Then 단계가 2 가 되고 다음 복습은 3일 뒤 한국 날짜 0시다 (정답이면 단계 5, 30일 뒤)

**S8. 기한 전에 다시 맞혀도 단계는 오르지 않는다** (TC-150, ADR-006 결정 8)
- Given 단어 W 를 방금 맞혀 단계 1(다음 복습 내일 0시)이 되었다
- When 같은 날 W 를 한 번 더 맞힌다
- Then 단계와 다음 복습 시각은 그대로이고 정답 수·연속 정답만 늘어난다

**S9. 밤에 맞힌 단어는 다음 날 오전에 오늘 복습에 뜬다** (TC-150, ADR-006 결정 7)
- Given 한국 시각 23:00 에 W 를 맞혀 단계 1 이 되었다
- When 다음 날 오전 9시에 복습함을 연다
- Then W 가 "오늘 복습"에 보인다 (복습 시각이 다음 날 0시이므로)

**S6. 로그인을 5번 틀리면 잠시 막힌다** (TC-121)
- Given 같은 IP 에서 1분 안에 로그인에 5번 실패했다
- When 올바른 비밀번호로 시도한다
- Then 429 와 `Retry-After` 로 거부된다 (비밀번호와 무관)

**S7. 시드를 다시 적재해도 학습 기록은 남는다** (TC-143, ADR-004)
- Given 표준 단어장을 한 번 적재했고 사용자가 W 를 학습했다
- When 같은 시드로 서버를 다시 시작한다
- Then 변경 없음으로 처리되고 W 의 `word_id` 와 학습 기록이 유지된다
- And 시드의 단어 내용이 바뀌면 같은 `word_id` 로 UPDATE 된다

## 6. 모바일 반응형 검증 절차 (REQ-119)

브라우저가 없는 환경에서는 시각·터치 항목을 자동으로 검증할 수 없어서 사람이 점검한다. 현재 절차는 `ai-agent/claude/검토_261111_모바일_실기기_점검_체크리스트.md`(v2.2) 한 건이다.

| 항목 | 현재 | 요구 (REQ-119) |
| :--- | :--- | :--- |
| 뷰포트 | 360px, 390px, 라이트·다크 각각 | 360px, 390px, **430px** |
| 증적 | 체크박스 기록 | **스크린샷** |
| 범위 | v2.2 변경분 (북마크, 플래시카드 뒷면, 표시 요소, 설정 모달) | 주요 화면 전체 |

**주요 화면 목록(점검 대상)**: 로그인·가입, 홈, 탐색(단어장 미리보기), 학습 세션(퀴즈·플래시카드·결과), 복습함, 통계, 학습 설정 모달, 환경 설정 모달.

**점검 규칙**: 각 화면을 3개 폭 × 2개 테마로 확인하고, 문제는 "증상 / 화면 / 기기"로 기록한다. 릴리스 직전에 수행하며 결과는 `ai-agent/claude/` 에 날짜를 붙여 보관한다. 이 절차를 승인하면 체크리스트를 위 범위로 확장해 별도 문서로 정리한다.

## 7. 갭과 개선 과제

| # | 갭 | 영향 | 제안 | 우선순위 |
| :-: | :--- | :--- | :--- | :-: |
| G1 | ~~커버리지 측정 설정이 저장소에 없다~~ **해결 (2026-11-19)**: `.coveragerc` 를 추가해 기본 명령으로 98% 가 재현된다. 남은 결정은 임계값(`--cov-fail-under`) 도입 여부다 | 임계값이 없어 커버리지가 떨어져도 막지 못한다 | 임계값 도입 여부를 결정한다 (예: 90) | 낮음 |
| G2 | ~~순수 단위 테스트도 DB 필요~~ **해결 (2026-11-19)**: `no_db` 마커로 `conftest.py` 의 DB 정리 fixture 를 건너뛴다. `test_no_db_guard.py` 가 접속 불가 포트에서 `no_db` 테스트를 돌려 표시가 거짓이 아님을 검증한다 (DB 가 필요한 테스트에 표시하면 실패함을 변이로 확인) | 해소. 새 순수 단위 테스트에는 `pytestmark = pytest.mark.no_db` 를 붙인다 | 표시 대상 확대는 필요할 때 | 낮음 |
| G3 | **모바일 검증 범위 부족**: 430px 과 스크린샷 증적이 없고, 범위가 v2.2 변경분뿐이다 | REQ-119 미충족 | §6 의 절차로 확장 | 중간 |
| G4 | **응답 시간(REQ-102) 검증 수단 없음**: 부하 테스트도, 관측도 없다 | p95 300ms 달성 여부 불명 | 간단한 부하 스크립트(예: 학습 세션·카탈로그 조회) 또는 요청 시간 로그 도입 검토 | 중간 |
| G5 | **REQ-113 전용 테스트 없음** | 현재는 바인딩 사용이 구조적으로 보장되어 위험이 낮다 | 검색 기능이 다시 생기면 LIKE 이스케이프 테스트를 같이 추가 | 낮음 |
| G6 | ~~마이그레이션 일관성 자동 검증 없음~~ **해결 (절차, 2026-11-19)**: 푸시 전 절차(§2, CLAUDE.md §4)에 `alembic check` 를 추가했다. 모델만 고치고 마이그레이션을 빼먹으면 이 명령이 "새 upgrade 작업 감지"로 알려 준다 | 사람이 실행해야 한다 (자동 테스트는 아님) | 자동화가 필요해지면 pytest 로 감싼다 | 낮음 |
| G7 | **자동 실행 환경(CI) 없음**: 저장소에 CI 설정이 없고 전체 테스트는 사람이 돌린다 | 푸시 전 전체 실행이 누락될 수 있다 | 이번 범위 밖. 필요하면 별도 제안 | 낮음 |
| G8 | **REQ-120 헤더 규칙**: 모듈 헤더 표준에 요구사항 ID 항목이 없다 | 추적성이 커밋 메시지에만 의존한다 | CLAUDE.md §5.2 헤더에 선택 항목으로 추가 검토 (지침 변경이므로 사용자 결정) | 낮음 |

## 8. 변경 이력

| 버전 | 날짜 | 내용 | 작성 |
| :--- | :--- | :--- | :--- |
| v1.1 개정 | 2026-11-19 | SRS 규칙 개정(REQ-150) 반영: TC-150 검증 위치, 시나리오 S8·S9, 기준선 557건(전체 pytest)·no_db 175건 | Claude |
| v1.1 | 2026-11-19 | **G2 해결**: `no_db` 마커와 가드 테스트(`test_no_db_guard.py`)로 순수 단위 테스트를 DB 없이 실행, `conftest.py` 정리 fixture 조건부화. **G6 해결(절차)**: 푸시 전 절차에 `alembic check` 추가(§2). 기준선 546건 | Claude |
| v1.0 | 2026-11-19 | 최초 작성(`.coveragerc` 추가 반영, REQ-150 은 TC-150). TC ID 정의와 테스트 파일 매핑, 현황 기준선(백엔드 545건·프론트엔드 463건 전체 통과, 백엔드 커버리지 98%), 갭 G1~G8 | Claude |
