# 요구사항 명세서 (Requirement Spec)

| 항목 | 내용 |
| :--- | :--- |
| 프로젝트 | voda-voca (보다보카, 웹 기반 단어장 서비스) |
| 문서 종류 | 요구사항 명세서 (Requirement Spec, `개발방법론.md` §2.2) |
| 버전 / 상태 | v2.1 / **승인 (Approved)** — 중앙 제공형 단어장 전환 반영 |
| 작성일 | 2026-11-05 (v2.0: 2026-11-02) |
| 산출물 경로 | `docs/voda-voca_Requirement_Spec_v2.1_261105.md` (이전 버전: `docs/old/voda-voca_Requirement_Spec_v2.0_261102.md` 외 보관) |

> **작성 원칙**: 본 문서의 요구사항 ID는 이후 모든 비즈니스 로직, API, 테스트 케이스의 추적 키로 사용한다 (`개발방법론.md` §3-1).
> **v2.1 개정 원칙**: 서비스가 *개인 단어장 관리형*에서 *중앙 제공형 단어장 + 단일 학습 세션 러너*로 전환되었다 (`작업계획_261105_통합_설계안.md`). 의미가 사라진 요구사항은 **번호를 재사용하지 않고 `폐기`로 표시**하며 후속 요구사항을 새 번호로 둔다 (A안 확정). 의미가 이어지는 요구사항은 번호를 유지하고 기준만 고친다. 폐기·개정 현황은 §9에 한눈에 정리했다.
> v1.1에서 §6 질의 사항을 모두 확정하여 `[확인 필요]` 표시를 제거했다. 사용자 별도 지시가 없었던 항목은 기본값을 적용했고, §6에 그 사실을 명시했다.

---

## 1. 목적 및 범위

### 1.1 목적
모바일 기기에서도 편하게 사용할 수 있는 웹 단어장 서비스를 제공한다. 서비스가 제공하는 표준 단어장(초급·중급·고급)을 골라, 하나의 학습 세션에서 플래시카드와 퀴즈로 학습하고, 중요한 단어를 북마크하며, 틀린 단어를 복습하고, 학습 통계를 확인할 수 있다.

### 1.2 범위 (In Scope)
- 다중 사용자 접속 및 사용자별 데이터 분리
- 서버가 제공하는 표준 단어장 조회와 학습 단어장 선택 (읽기 전용)
- 학습 세션(플래시카드 / 객관식 퀴즈), 숙련도 판정, 오답·북마크 복습
- 단어 북마크, 학습 이력과 통계
- 모바일 뷰포트 우선 반응형 UI

### 1.3 범위 외 (Out of Scope, 1차 릴리스)
- 단어장 공유 및 협업 편집 (기본값: 1차 제외, Q2)
- 소셜 로그인, 이메일 인증 메일 발송 (기본값: 1차 제외)
- 네이티브 앱(iOS/Android) 배포
- 외부 사전 API 연동을 통한 뜻 자동 완성
- 사용자 개인 단어장·단어 생성, 수정, 삭제, CSV 가져오기·내보내기 (v2.1 에서 폐지)

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
| 일반 학습자 (Learner) | 표준 단어장으로 학습하는 주 사용자 | 모바일에서 빠른 학습, 틀린 단어 복습, 진행 상황 확인 |
| 운영자/개발자 (Operator) | Docker 환경을 구성하고 서비스를 운영 | 컨테이너 기동, 마이그레이션, 로그 확인 |

관리자(Admin) 역할은 1차 릴리스에서 제외한다 (기본값, Q8).

---

## 3. 사용자 시나리오 (핵심)

- **S-01 신규 학습자 시작**: 회원 가입 → 초급 단어장이 자동으로 학습 단어장이 됨 → 홈에서 바로 학습 시작
- **S-02 이동 중 학습**: 모바일에서 로그인 → 홈에서 플래시카드 세션 시작 → 카드를 뒤집고 "알아요 / 헷갈려요"로 응답
- **S-03 실력 점검**: 퀴즈 세션(기본 15문항) → 보기를 고르면 즉시 정오와 해설 → 마지막에 정답 수와 오답 노트 확인
- **S-04 단어장 바꾸기**: 탐색 화면에서 카테고리·레벨로 거르고 다른 표준 단어장을 학습 단어장으로 선택
- **S-05 중점 복습**: 복습함에서 북마크 또는 틀린 단어로 복습 세션 시작

---

## 4. 기능 요구사항 (Functional Requirements)

우선순위: **M** = 필수(Must), **S** = 권장(Should)

### 4.1 계정 (Account)

| ID | 요구사항 | 우선순위 | 상세 기준 (Acceptance Criteria) |
| :--- | :--- | :---: | :--- |
| REQ-001 | 회원 가입 | M | 계정은 **닉네임(2~30자, 중복 불가)과 비밀번호**만으로 만든다. 이메일은 받지 않는다. 닉네임은 로그인 식별자이며 대소문자와 무관하게 유일하다. 비밀번호는 8자 이상, UTF-8 기준 **72바이트 이하**만 허용한다 (bcrypt 입력 한계, ADR-002). 가입이 끝나면 초급 표준 단어장(`beginner-200`)이 학습 단어장으로 자동 지정된다 (REQ-142). 인증은 **HttpOnly, SameSite=Lax 세션 쿠키** 방식을 사용한다 (Q1 확정). |
| REQ-002 | 로그인 / 로그아웃 | M | 올바른 자격 증명 시 세션을 `sessions` 테이블에 생성하고 세션 쿠키를 발급한다. 세션 수명은 로그인 후 **14일**(절대 만료)이다 `[기본값]`. 로그아웃 시 해당 세션 행을 삭제하여 즉시 무효화한다. 실패 시 어떤 항목이 틀렸는지 노출하지 않는다. (ADR-001) |
| REQ-003 | 사용자별 데이터 격리 | M | 로그인한 사용자는 본인의 북마크·학습 이력·학습 진행도·학습 세션만 조회·수정·삭제할 수 있다. 타 사용자 리소스(세션 등) 접근 시 404를 반환한다 (존재 여부를 구분하지 않는다). 표준 단어장·단어는 모든 사용자가 공유하는 읽기 전용 콘텐츠다. |
| REQ-122 | 회원 탈퇴 | M | 로그인한 사용자는 계정을 탈퇴할 수 있다 (`DELETE /api/auth/me`). 탈퇴하면 계정, 세션, 북마크, 학습 이력, 학습 진행도, 학습 세션을 **모두 영구 삭제**하고 세션 쿠키를 만료시킨다 (204). **표준 단어장과 단어는 공용 콘텐츠이므로 삭제되지 않는다.** 탈퇴 전에 경고 확인과 닉네임 직접 입력 확인을 거친다. 탈퇴한 닉네임은 다시 사용할 수 있다. |

### 4.2 표준 단어장 (System Vocabulary, 읽기 전용)

표준 단어장은 서버 시드로만 바뀌는 공용 콘텐츠다. 사용자는 만들거나 고치거나 지울 수 없고, 해당 API 경로는 존재하지 않는다 (별도 410 응답 없음).

| ID | 요구사항 | 우선순위 | 상세 기준 (Acceptance Criteria) |
| :--- | :--- | :---: | :--- |
| REQ-004 | 단어장 생성 | M | **폐기** (v2.1) — 개인 단어장 폐지. 후속: REQ-140, REQ-143 |
| REQ-005 | 단어장 목록 조회 | M | **폐기** (v2.1) — 후속: REQ-140 |
| REQ-006 | 단어장 수정 | M | **폐기** (v2.1) — 수정 경로 없음. 학습 대상 선택은 REQ-142 |
| REQ-007 | 단어장 삭제 | M | **폐기** (v2.1) — 삭제 경로 없음. 사용자 데이터 삭제는 REQ-122 |
| REQ-123 | 기본 단어장 자동 제공 | M | **폐기** (v2.1) — 후속: REQ-142 (가입 시 초급 단어장 자동 활성화). 단어장·단어를 사용자별로 복사하지 않는다 |
| REQ-128 | 단어장 단어 수 노출 | S | **폐기** (v2.1) — 후속: REQ-140 (`total_words`) |
| REQ-130 | 중급 1,000제 추천 프리셋 | S | **폐기** (v2.1) — 후속: REQ-143. 프리셋 추가 API와 `intermediate_1000.csv` 를 삭제했다 |
| REQ-140 | 표준 단어장 카탈로그 조회 | M | 로그인한 사용자는 표준 단어장 목록을 조회한다 (`GET /api/vocabularies`). 항목마다 `slug`, `title`, `category`, `level`, `description`, `total_words` 와 **본인의 진행률**(`studied_words`, `memorized_words`, `progress_rate`, `is_active`)을 포함한다. `category`, `level`(1~5, 범위 밖은 422)로 거를 수 있다. 진행률은 단어장별 집계 쿼리 한 번으로 구한다 (N+1 금지). 비로그인은 401. |
| REQ-141 | 표준 단어 목록 조회 | M | 단어장의 단어를 읽기 전용으로 조회한다 (`GET /api/vocabularies/{id}/words`, `page`/`size`, 본인 북마크 여부 포함). 없는 단어장은 404. 단어는 `term`, `meaning`, `example`, `example_meaning` 을 가지며, 예문이 없으면 `example_meaning` 도 없다. |
| REQ-142 | 학습 단어장 선택(활성화) | M | 사용자는 학습할 단어장 하나를 고른다 (`POST /api/users/me/active-vocabulary`, 본문 `{"vocabulary_id"}`). 성공하면 그 단어장의 카탈로그 항목을 돌려주고, 같은 값을 다시 보내도 성공한다. 없는 단어장은 404. 가입한 사용자는 초급 단어장이 자동 활성화되며, 활성 단어장이 없는 사용자가 세션을 시작하면 첫 단어장이 활성화된다. 활성 단어장 행이 사라지면 활성 값은 비워진다 (`ON DELETE SET NULL`). |
| REQ-143 | 표준 단어장 시드 | M | 콘텐츠는 서버 시드 파일로만 바뀐다. 앱 시작 시 멱등으로 적재한다 (`slug` 가 멱등 키, `content_hash` 가 같으면 쓰기를 생략). 초기 범위는 초급·중급·고급 각 200단어(총 600)다. `category` 는 자유 문자열이며 새 카테고리는 스키마 변경 없이 시드만으로 추가한다. |

### 4.3 단어 (Word)

| ID | 요구사항 | 우선순위 | 상세 기준 (Acceptance Criteria) |
| :--- | :--- | :---: | :--- |
| REQ-008 | 단어 추가 | M | **폐기** (v2.1) — 사용자 단어 쓰기 경로 폐지. 단어는 시드로만 추가된다 (REQ-143) |
| REQ-009 | 단어 목록 조회 및 검색 | M | **폐기** (v2.1) — 목록 조회는 REQ-141. 표제어 접두사 검색은 제공하지 않는다 |
| REQ-010 | 단어 수정 | M | **폐기** (v2.1) |
| REQ-011 | 단어 삭제 | M | **폐기** (v2.1) |
| REQ-125 | 발음 청취 (TTS) | S | 학습 세션의 문항·카드 화면에 스피커 버튼을 두고, 브라우저 음성 합성(Web Speech API, 영어 en-US, 속도 0.9, 음높이 1.0)으로 표제어를 읽어 준다. 연속으로 누르면 이전 발음을 끊고 새로 읽는다. 음성을 지원하지 않는 브라우저에서는 예외를 던지지 않고 실패를 무시한다. 외부 음성 서비스와 API 키는 쓰지 않는다. |

### 4.4 학습 (Study)

플래시카드와 퀴즈는 별도 화면이 아니라 **하나의 학습 세션 러너**(`/study/session`)의 두 모드(`flashcard`, `quiz`)다. 출제는 `POST /api/study/sessions`, 문항별 채점·기록은 `POST /api/study/sessions/{id}/answer` 이며 옛 `/api/study/flashcards`, `/api/study/quiz/*` 는 제거되었다.

| ID | 요구사항 | 우선순위 | 상세 기준 (Acceptance Criteria) |
| :--- | :--- | :---: | :--- |
| REQ-012 | 학습 세션 출제와 플래시카드 모드 | M | 세션을 만든다 (`POST /api/study/sessions`, 부수효과가 있으므로 `GET` 을 쓰지 않는다). 요청: `mode`(`quiz`·`flashcard`, 기본 quiz), `count`(1~30, 기본 15), `include_memorized`(기본 false), `source`(`all`·`bookmarks`·`wrong`, 기본 all). **`all`** 은 활성 단어장에서 **워터폴 규칙**으로 고른다: 오답 풀은 최대 `floor(0.3×N)`, 기학습 복습을 `floor(0.1×N)` 먼저 확보, 나머지는 미학습 단어(`order_index` 순), 미학습이 모자라면 복습으로 충원하며, 숙련한 단어는 `include_memorized=false` 일 때 제외한다. 가용 단어가 N 미만이면 가능한 만큼만 출제하고, 출제 후 순서를 섞는다. 응답에는 `composition`(오답·복습·미학습 개수)이 있다. 출제 가능한 단어가 없으면 409 `NO_WORDS_TO_STUDY`, 활성화할 단어장이 없으면 409 `NO_VOCABULARY`. **플래시카드 모드**는 카드 **앞면에는 단어만** 보여 주고 탭하면 뒷면(뜻, 영문 예문, 예문 해석)을 뒤집어 보이며, "알아요"(true)와 "헷갈려요"(false)로 응답한다. 출제 응답에 뒷면 정보가 함께 실린다 (정답이 없는 모드이므로). |
| REQ-013 | 플래시카드 셔플 | S | **폐기** (v2.1) — 순서는 서버 출제가 결정하고 섞어 준다 (REQ-012). 사용자 셔플 조작은 두지 않는다 |
| REQ-014 | 객관식 퀴즈 모드 | M | 표제어와 예문(문맥)을 보여 주고 뜻 4지선다 중 하나를 고르게 한다. 오답 3개는 **같은 단어장의 다른 단어 뜻을 우선**하고 부족하면 전체 표준 단어에서 보충하며, 뜻이 같은 보기는 중복시키지 않는다. 활성 단어장의 단어가 4개 미만이면 퀴즈를 시작할 수 없고(400) 플래시카드는 허용한다. **출제 응답에는 정답을 싣지 않는다** — `options` 만 있고 `correct_index`, `meaning`, `example_meaning` 은 없다. |
| REQ-015 | 세션 결과 | M | 보기를 고르면 **즉시** 정오를 보여 준다 (정답 초록, 오답 빨강). 모든 문항에 답하면 세션이 끝나며(`is_finished`), 정답 수, 정답률, 오답 노트(틀린 단어, 정답 뜻, 내가 고른 뜻)를 보여 준다. 마지막 응답 후 30분이 지나면 새 답을 받지 않는다 (`QUIZ_EXPIRED`, 푼 문항은 이미 저장되어 있다). |
| REQ-016 | 학습 이력 기록과 숙련도 | S | 세션에서 **문항에 답할 때마다** 그 답 1건의 **정답 여부, 학습 모드(`quiz`·`flashcard`), 기록 시각**을 `study_logs` 에 저장한다. 플래시카드의 "알아요"는 정답, "헷갈려요"는 오답이다. 이력 기록과 사용자×단어 진행도(`user_word_progress`: 정답·오답 횟수, 연속 정답, 숙련 여부, 마지막 결과) 갱신은 **하나의 트랜잭션**이다. 정답이 연속 3회가 되면 숙련(`is_memorized`)이며, 오답 1회면 연속 횟수를 0으로 되돌리고 숙련을 해제한다. 같은 문항에 같은 답을 다시 보내면 이력을 늘리지 않고 같은 응답을 돌려주며(멱등), 다른 답으로 바꾸려 하면 409 `QUIZ_ANSWER_LOCKED` 다. 최근 학습 이력 **100건을 최신순**으로 조회할 수 있다 (`GET /api/study/logs`). 이 이력은 통계(REQ-131~133)와 오답 단어 판정(REQ-129)의 근거다. |
| REQ-124 | 즉각 피드백과 해설 | M | 문항마다 답을 기록하는 즉시 서버가 **채점 응답**(`POST /api/study/sessions/{id}/answer`)으로 정오(`is_correct`), 정답 선지(`correct_index`, 퀴즈), 표제어·뜻·예문·예문 뜻(해설), 갱신된 단어 진행도, 진행 상황(`answered`, `total`, `is_finished`)을 돌려준다. **정답과 해설은 채점 응답에서만 공개**되고 출제 응답에는 없다. 화면은 이를 카드로 보여 주고 [다음 문항] 버튼으로 넘어간다. 한 문항은 한 번 답하면 잠긴다. 예문이 없는 단어는 "해설 예문이 없습니다"를 보여 준다. |
| REQ-129 | 오답 복습 | S | 복습함의 "틀린 단어" 목록(`GET /api/study/wrong-words`, `page`/`size`≤100, 최근 틀린 순)에서 복습 세션(`source=wrong`)을 시작한다. **오답 판정은 단어별 마지막 결과가 오답인 단어**이며(최근 N건 제한 없음), 맞히면 대상에서 빠진다. 통계의 `wrong_word_count` 와 같은 규칙이다. 풀이 비면 409, 퀴즈는 4개 미만이면 400 이다. 복습 세션은 활성 단어장을 바꾸지 않고(`vocabulary_id` null) 숙련 단어를 제외하지 않는다. |

### 4.5 북마크 (Bookmark)

| ID | 요구사항 | 우선순위 | 상세 기준 (Acceptance Criteria) |
| :--- | :--- | :---: | :--- |
| REQ-017 | 북마크 토글 | M | 단어 카드 또는 목록에서 북마크를 켜거나 끈다 (`PUT`/`DELETE /api/bookmarks/{word_id}`, 204, 멱등). 같은 단어에 중복 북마크는 생성되지 않는다. 대상은 표준 단어이며 없는 단어는 404 다. |
| REQ-018 | 북마크 목록 조회 | M | 본인 북마크 단어를 소속 표준 단어장 정보와 함께 페이지 단위로 보여 준다 (`GET /api/bookmarks`). 복습함 화면에서 쓴다. |
| REQ-019 | 북마크 기반 학습 | S | 복습함에서 북마크 단어만으로 복습 세션(`source=bookmarks`)을 시작한다. 플래시카드와 퀴즈 모두 가능하며, 북마크가 4개 미만이면 퀴즈는 400 으로 거부되고 플래시카드만 허용한다. 복습 세션은 활성 단어장을 바꾸지 않는다. |

### 4.6 UI / 모바일 (User Interface)

| ID | 요구사항 | 우선순위 | 상세 기준 (Acceptance Criteria) |
| :--- | :--- | :---: | :--- |
| REQ-020 | 모바일 뷰포트 반응형 레이아웃 | M | 360px ~ 430px 폭의 모바일에서 가로 스크롤 없이 모든 주요 화면을 사용할 수 있다. 태블릿·데스크톱에서도 같은 기능을 제공한다. |
| REQ-021 | 터치 인터랙션 | M | 탭, 스와이프 제스처를 지원한다. 300ms 탭 딜레이는 `viewport` 메타 태그와 `touch-action`으로 제거한다. |
| REQ-022 | 알림·확인 UI | M | 브라우저 기본 `alert` / `confirm` 대신 SweetAlert2 모달을 사용한다. |
| REQ-023 | 아이콘 | S | 주요 액션 아이콘은 Lucide Icons로 표시한다. |
| REQ-126 | 다크 모드 | S | 헤더의 테마 버튼으로 밝은 화면과 어두운 화면을 전환한다. 초기값은 저장된 선택이 있으면 그것을, 없으면 시스템 설정을 따른다. 선택은 브라우저(`voda.theme`)에 저장해 다음 방문에도 유지한다. 어두운 화면은 Zinc 계열 팔레트만 쓴다. 저장소를 쓸 수 없으면 저장 없이 동작한다. |
| REQ-127 | 키보드 단축키 (데스크톱) | S | 학습 세션에서 퀴즈는 숫자 `1`~`4` 로 보기를 고르고, 피드백이 뜬 뒤 `Enter`·`Space` 로 다음 문항으로 넘어간다. 플래시카드는 `Space`·`Enter` 로 뒤집고 `→` 알아요, `←` 헷갈려요로 응답한다. `Esc` 로 세션을 나가는 확인을 띄운다. 입력 칸이나 열린 모달에 포커스가 있으면 단축키를 무시한다. |
| REQ-131 | 학습 지표 서버 집계 | S | 통계 화면과 홈은 서버가 집계한 지표를 보여 준다 (`GET /api/study/stats`): 누적 푼 문항 수·정답 수·정답률(기록이 없으면 null → "—"), 연속 학습일(한국 날짜 기준, 오늘 기록이 없으면 어제부터), 최근 7일 활동, 모든 표준 단어 수 합계, 단어장별 진행률, 오답 단어 수. **최근 100건 제한이 없다** (v2.0 의 클라이언트 100건 집계를 대체). |
| REQ-132 | 최근 7일 학습 차트 | S | 통계 화면에서 최근 7일(오늘 포함)의 날짜별 학습 단어 수를 인라인 SVG 막대 차트로 보여 준다. 같은 날 같은 단어는 한 번으로 센다. 오늘 막대는 강조하고 "오늘" 뱃지를 붙인다. 막대를 누르거나 포커스하면 그 날의 개수를 표시한다. 값은 서버 집계(REQ-131)이며 외부 차트 라이브러리는 쓰지 않는다. |
| REQ-133 | 단어장 카드 진행률과 학습 시작 | S | 탐색 화면의 단어장 카드에 카테고리·레벨·단어 수 배지와 본인 진행률(학습한 단어 수, 진행률 바)을 보인다. 카드에서 그 단어장을 학습 단어장으로 선택하고(REQ-142) 홈에서 바로 학습을 시작할 수 있다. 진행률은 REQ-140 의 `user_progress` 를 쓴다. |
| REQ-134 | 계정 드롭다운 메뉴 | M | 닉네임 칩을 누르면 칩 아래에 팝오버가 뜬다. 프로필 헤더, 로그아웃, 회원 탈퇴(위험 구역)를 담는다. 로그아웃은 **확인 모달 없이 즉시** 세션을 종료하고 `/login` 으로 이동한다. 회원 탈퇴는 기존 두 단계 확인을 거친다. 바깥을 누르거나 ESC를 누르면 닫힌다. |
| REQ-135 | CSV 내보내기 확인 모달 | M | **폐기** (v2.1) — CSV 백업 기능 폐지 (개인 단어가 없다) |
| REQ-136 | 단어장별 CSV 내보내기 | S | **폐기** (v2.1) |
| REQ-137 | 정답 효과음 | S | 퀴즈 세션에서 정답을 고르면 D5(587.33Hz)에서 A5(880.00Hz)로 올라가는 두 사인파를 Web Audio API로 합성한다. 외부 오디오 파일은 내려받지 않는다. 오답 선택에는 어떤 소리도 내지 않는다. 컨텍스트가 정지 상태이면 사용자 제스처에서 재개한다. |
| REQ-138 | 정답 소리 음소거 | S | 헤더의 소리 버튼으로 정답 소리를 끄고 켠다. 설정은 `voda.sound_muted`에 저장하며 기본값은 켬이다. 음소거 중에는 소리를 내지 않는다. |
| REQ-139 | CSV 가져오기 정합성 | M | **폐기** (v2.1) — 일괄 등록 기능 폐지 |

---

## 5. 비기능 요구사항 (Non-Functional Requirements)

### 5.1 성능 / 비동기 처리

| ID | 요구사항 | 우선순위 | 상세 기준 |
| :--- | :--- | :---: | :--- |
| REQ-101 | 비동기 API 처리 | M | FastAPI의 `async` 엔드포인트와 SQLAlchemy 2.0 비동기 엔진(asyncmy)을 사용하여 DB I/O 동안 이벤트 루프가 블로킹되지 않아야 한다. |
| REQ-102 | 응답 시간 | M | 동시 사용자 50명 기준, 학습 세션·카탈로그 조회 API의 p95 응답 시간 **300ms 이하** (Q6 확정). |
| REQ-103 | 목록 조회 성능 | S | 단어가 많은 단어장의 단어 목록(REQ-141)과 북마크·오답 목록은 페이지네이션을 적용한다. |

### 5.2 데이터 무결성 (MySQL)

| ID | 요구사항 | 우선순위 | 상세 기준 |
| :--- | :--- | :---: | :--- |
| REQ-104 | 참조 무결성 | M | 표준 단어장·표준 단어·북마크·학습 이력·학습 진행도·학습 세션 간 외래키(FK)를 정의하고, 부모 삭제 시 `ON DELETE CASCADE`로 자식을 함께 정리한다. |
| REQ-105 | 중복 방지 제약 | M | `slug` 단어장 식별자 유일성, `(vocabulary_id, term)` 표제어 유일성, `(user_id, word_id)` 북마크 유일성, `(user_id, word_id)` 학습 진행도 유일성을 DB 제약(UNIQUE)으로 강제한다. 애플리케이션 검사만으로 대체하지 않는다. |
| REQ-106 | 트랜잭션 일관성 | M | 답 1건의 이력·진행도 기록, 회원 탈퇴 등 여러 행을 변경하는 작업은 단일 트랜잭션으로 수행하여 부분 반영을 막는다. |
| REQ-107 | 스키마 버전 관리 | M | 모든 스키마 변경은 Alembic 마이그레이션으로만 수행한다. 수동 `ALTER`를 금지한다. |
| REQ-108 | 문자셋 및 시간대 | M | DB 문자셋은 `utf8mb4`, 콜레이션은 `utf8mb4_0900_ai_ci`로 설정한다. 세션 시간대는 `+09:00`(Asia/Seoul)로 설정한다. 한글과 이모지 저장이 깨지지 않아야 한다. |
| REQ-109 | 시각 저장 기준 | S | 모든 시각 컬럼은 UTC 기준으로 DB에 저장하고, 화면 표시 시 Asia/Seoul(KST)로 변환한다 (Q7 확정). |

### 5.3 보안

| ID | 요구사항 | 우선순위 | 상세 기준 |
| :--- | :--- | :---: | :--- |
| REQ-110 | 비밀번호 저장 | M | 비밀번호는 **bcrypt**로 해시하여 저장한다 (ADR-002). 평문 저장을 금지한다. |
| REQ-111 | 입력 검증 | M | 모든 API 입력은 Pydantic 스키마로 검증한다. 길이·형식 제약은 §4의 기준을 따른다. |
| REQ-112 | 설정 값 관리 | M | DB 접속 정보, 비밀 키, 포트는 `.env`로 주입하며 소스 코드에 하드코딩하지 않는다. 저장소에는 `.env.example`만 커밋한다. |
| REQ-113 | SQL 인젝션 방지 | M | ORM 파라미터 바인딩을 사용하고, 문자열 결합으로 SQL을 만들지 않는다. LIKE 검색어의 `%`, `_`, `\`는 이스케이프한다. |
| REQ-121 | 로그인 무차별 대입 방어 | M | 로그인 실패가 **동일 IP 또는 동일 계정(닉네임)** 기준 **1분 내 5회**에 도달하면, 이후 로그인 요청은 비밀번호와 무관하게 **429 Too Many Requests**와 `Retry-After` 헤더로 거부한다. 성공한 로그인은 해당 계정의 실패 기록을 지운다. 외부 저장소 없이 프로세스 메모리에서 관리한다 (단일 프로세스 한정). |

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
| REQ-118 | 자동화 테스트 | M | 백엔드 핵심 로직은 pytest 단위 테스트와 DB 연동 통합 테스트로 검증한다. 도메인 핵심 비즈니스 로직 기준 **커버리지 80% 이상**을 목표로 한다 (확정). |
| REQ-119 | 모바일 반응형 검증 | S | 360px, 390px, 430px 폭에서 주요 화면 스크린샷 검증 절차를 테스트 정의서에 포함한다. |
| REQ-120 | 코드 추적성 | M | 구현 코드의 모듈 헤더 또는 커밋 메시지에 관련 요구사항 ID를 명시한다. |

---

## 6. 확정 사항 (Resolved)

v1.0의 질의 사항 Q1~Q8에 대한 결정이다. 사용자가 명시적으로 확정한 항목과, 별도 지시가 없어 기본값을 적용한 항목을 구분한다.

| # | 질문 | 확정 결과 | 구분 | 관련 ID |
| :-: | :--- | :--- | :--- | :--- |
| Q1 | 인증 방식 | HttpOnly, SameSite=Lax **세션 쿠키** (Vanilla JS 토큰 관리 복잡도 저감, XSS 방어) | 사용자 확정 | REQ-001, REQ-002 |
| Q2 | 단어장 공유 필요 여부 | 1차 제외 | 기본값 적용 | §1.3 |
| Q3 | 단어장 삭제 방식 | **하드 삭제** (`ON DELETE CASCADE`). v2.1 에서 사용자 단어장 자체가 폐지되어 해당 없음 (회원 탈퇴 시 개인 데이터 하드 삭제는 유지) | 사용자 확정 (v2.1 대체) | REQ-122 |
| Q4 | 단어 필드 구성 | 표제어·뜻·예문·예문 뜻 (품사, 발음 기호는 DDL 에 NULL 허용 확장 컬럼으로만 두고 미사용) | 기본값 적용 | REQ-141 |
| Q5 | 학습 이력 1차 포함 여부 | **포함** (S). 문항별 기록, 최근 100건 최신순 조회 (통계·오답 판정은 전체 이력 서버 집계, v2.1) | 사용자 확정 | REQ-016 |
| Q6 | 동시 접속 및 p95 목표 | 동시 사용자 50명, p95 **300ms 이하** | 사용자 확정 | REQ-102 |
| Q7 | 시각 저장 기준 | DB **UTC** 저장, 화면에서 KST 변환 | 사용자 확정 | REQ-109 |
| Q8 | 관리자 역할 | 1차 제외 | 기본값 적용 | §2 |

**추가 확정 (데이터 설계 과정)**

| 항목 | 확정 결과 | 관련 ID |
| :--- | :--- | :--- |
| 페이징 | 단어 목록(REQ-141) 등 목록 API 는 `page`/`size` 방식 | REQ-141 |
| 단어장 식별 | 표준 단어장은 `slug` 로 유일하게 식별 (시드 멱등 키) | REQ-143, REQ-105 |
| 콜레이션 | `utf8mb4_0900_ai_ci` (대소문자·악센트 무시) | REQ-108 |
| 북마크 대상 | 표준 단어(공용). 본인 북마크만 조회·변경 | REQ-017 |
| 로그인 세션 저장소 | DB `sessions` 테이블 (토큰 해시 저장, ADR-001) | REQ-002 |
| 비밀번호 해시 | bcrypt, 72바이트 제한 (ADR-002) | REQ-001, REQ-110 |
| 다크 모드 팔레트 | Zinc 계열만 사용 (Slate 미사용). 기본값은 시스템 설정 | REQ-126 |
| 오답 복습 원천 | **단어별 마지막 결과가 오답**인 단어 (기간 제한 없음). 통계 오답 단어 수와 같은 규칙 | REQ-129 |
| 숙련 판정 | 연속 정답 3회 = 숙련, 오답 1회면 연속 0·숙련 해제 | REQ-016 |
| 출제 규칙 | 워터폴: 오답 ≤30%, 복습 10% 선확보, 나머지 미학습, 부족 시 복습 충원 | REQ-012 |
| 정답 노출 | 출제 응답에는 정답 비노출, 채점 응답에서만 정답·해설 공개 | REQ-014, REQ-124 |
| 통계 기준 범위 | 서버가 전체 이력에서 집계한다 (최근 100건 제한 없음) | REQ-131~133 |
| 정답 효과음 음높이 | 두 음 간격 0.08초, 각 음 0.15초, 음량 0.2. 오답에는 재생 함수 자체를 두지 않는다 | REQ-137 |
| 예문 뜻 | 예문이 없으면 예문 뜻은 저장하지 않는다 (시드 규칙) | REQ-141, REQ-143 |

---

## 7. 요구사항 추적 매트릭스 (Traceability Matrix)

이 표는 요구사항 ID가 이후 설계 산출물과 테스트 케이스에 어떻게 연결되는지 정의한다. 설계와 테스트 ID는 착수 시 채운다.

| 요구사항 ID | 요구사항 요약 | 우선순위 | 설계 산출물 (예정) | 구현 위치 (예정) | 테스트 ID (예정) | 상태 |
| :--- | :--- | :---: | :--- | :--- | :--- | :---: |
| REQ-001 | 회원 가입 | M | API Integration Spec §3.1, Data Design §3.1 | `src/backend/routers/auth.py`, `services/auth.py` | TC-001 | 구현 완료 (닉네임 고유키) |
| REQ-002 | 로그인 / 로그아웃 | M | Integration Spec, Data Design(sessions) | `src/backend/routers/auth.py` | TC-002 | 설계 완료 |
| REQ-003 | 사용자별 데이터 격리 | M | Architecture Design | `src/backend/services/` | TC-003 | 구현 완료 |
| REQ-004 | 단어장 생성 | M | — | (삭제됨) | — | 폐기 (→ REQ-140) |
| REQ-005 | 단어장 목록 조회 | M | — | (삭제됨) | — | 폐기 (→ REQ-140) |
| REQ-006 | 단어장 수정 | M | — | (삭제됨) | — | 폐기 (→ REQ-142) |
| REQ-007 | 단어장 삭제 | M | — | (삭제됨) | — | 폐기 (→ REQ-122) |
| REQ-008 | 단어 추가 | M | — | (삭제됨) | — | 폐기 (→ REQ-143) |
| REQ-009 | 단어 목록·검색 | M | — | (삭제됨) | — | 폐기 (→ REQ-141) |
| REQ-010 | 단어 수정 | M | — | (삭제됨) | — | 폐기 (→ —) |
| REQ-011 | 단어 삭제 | M | — | (삭제됨) | — | 폐기 (→ —) |
| REQ-012 | 학습 세션 출제·플래시카드 모드 | M | 통합 설계안 §5.1~5.2, Integration Spec | `src/backend/routers/study_session.py`, `services/learning_session.py`, `services/session_picker.py`, `src/frontend/js/views/study-session-view.js` | `test_learning_session_api.py`, `test_session_picker_units.py` | 구현 완료 (v2.1) |
| REQ-013 | 플래시카드 셔플 | S | — | (삭제됨) | — | 폐기 (→ REQ-012) |
| REQ-014 | 객관식 퀴즈 모드 | M | 통합 설계안 §5.1 | `services/learning_session.py`, `services/study.py`(보기 생성) | `test_learning_session_api.py`, `test_study_units.py` | 구현 완료 (v2.1) |
| REQ-015 | 세션 결과 | M | 통합 설계안 §5.3 | `src/frontend/js/core/session-view-model.js`, `views/study-session-view.js` | `src/frontend/tests/` | 구현 완료 (v2.1) |
| REQ-016 | 학습 이력 기록과 숙련도 | S | Data Design(study_logs, user_word_progress) | `services/study_log.py`, `services/progress.py`, `routers/study.py` | `test_study_log_progress.py`, `test_study_logs_api.py` | 구현 완료 (v2.1) |
| REQ-017 | 북마크 토글 | M | Data Design(bookmarks), Integration Spec | `src/backend/routers/bookmark.py` | `test_bookmark_api.py` | 구현 완료 |
| REQ-018 | 북마크 목록 | M | Integration Spec | `src/backend/routers/bookmark.py` | `test_bookmark_api.py` | 구현 완료 |
| REQ-019 | 북마크 기반 학습 | S | 통합 설계안 §5.1 | `services/learning_session.py`(source=bookmarks), `views/review-view.js` | `test_review_session_api.py` | 구현 완료 (v2.1) |
| REQ-020 | 모바일 반응형 레이아웃 | M | UI/UX 설계서 | `src/frontend/*.html`, Tailwind 클래스 | TC-020 (브라우저 검증) | 초안 |
| REQ-021 | 터치 인터랙션 | M | UI/UX 설계서 | `src/frontend/js/` | TC-021 (브라우저 검증) | 초안 |
| REQ-022 | SweetAlert2 모달 | M | UI/UX 설계서 | `src/frontend/js/` | TC-022 | 초안 |
| REQ-023 | Lucide 아이콘 | S | UI/UX 설계서 | `src/frontend/*.html` | TC-023 | 초안 |
| REQ-101 | 비동기 API | M | Architecture Design | `src/backend/db/session.py` | TC-101 | 초안 |
| REQ-102 | 응답 시간 | M | Architecture Design | 부하 테스트 스크립트 | TC-102 | 초안 |
| REQ-103 | 목록 페이지네이션 | S | Integration Spec | `src/backend/routers/vocabulary.py`, `routers/bookmark.py` | `test_vocabulary_api.py` | 구현 완료 |
| REQ-104 | 참조 무결성(FK) | M | Data Design | `src/backend/models/` | TC-104 | 설계 완료 |
| REQ-105 | 중복 방지(UNIQUE) | M | Data Design | `src/backend/models/`, Alembic | TC-105 | 설계 완료 |
| REQ-106 | 트랜잭션 일관성 | M | Architecture Design | `src/backend/services/` | TC-106 | 초안 |
| REQ-107 | Alembic 마이그레이션 | M | Architecture Design | `src/backend/alembic/` | TC-107 | 초안 |
| REQ-108 | 문자셋 / 시간대 | M | Data Design, `docker/docker-compose.yml` | `docker/docker-compose.yml` | TC-108 | 구현 완료 (인프라), 콜레이션 정합 대기 (F1) |
| REQ-109 | 시각 저장 기준 | S | Data Design | `src/backend/models/base.py` | TC-109 | 설계 완료 |
| REQ-110 | 비밀번호 해시 | M | Decision Records (ADR-002) | `src/backend/services/auth.py` | TC-110 | 설계 완료 |
| REQ-111 | 입력 검증 | M | Integration Spec | `src/backend/schemas/` | TC-111 | 초안 |
| REQ-112 | 설정 값 `.env` 주입 | M | Deployment Spec (README) | `.env.example`, 설정 모듈 | TC-112 | 부분 완료 (`.env.example`, `.gitignore`) |
| REQ-113 | SQL 인젝션 방지 | M | Architecture Design, Data Design(§2.5) | `src/backend/services/` | TC-113 | 초안 |
| REQ-114 | 터치 타겟 44px | M | UI/UX 설계서 | `src/frontend/` | TC-114 (브라우저 검증) | 초안 |
| REQ-115 | 모바일 본문 16px | S | UI/UX 설계서 | `src/frontend/` | TC-115 (브라우저 검증) | 초안 |
| REQ-116 | 컨테이너 격리 | M | Architecture Design | `docker/docker-compose.yml` | TC-116 | 구현 완료 (인프라) |
| REQ-117 | 단일 명령 기동 | M | Deployment Spec (README) | `docker/docker-compose.yml` | TC-117 | 구현 완료 (인프라) |
| REQ-118 | pytest 자동화 테스트 | M | Test Specification | `src/backend/tests/` | TC-118 | 초안 |
| REQ-119 | 모바일 스크린샷 검증 | S | Test Specification | 검증 스크립트 | TC-119 | 초안 |
| REQ-120 | 코드 추적성 (ID 명시) | M | 개발방법론 §3 | 모듈 헤더, 커밋 메시지 | 코드 리뷰 체크리스트 | 초안 |
| REQ-121 | 로그인 무차별 대입 방어 | M | 본 명세 §5.3 | `src/backend/core/rate_limit.py`, `src/backend/routers/auth.py` | TC-121 | 구현 완료 |
| REQ-122 | 회원 탈퇴 | M | API Integration Spec §3.1 | `src/backend/routers/auth.py`, `services/auth.py` | `test_auth_api.py` | 구현 완료 (v2.1: 표준 콘텐츠 보존) |
| REQ-123 | 기본 단어장 자동 제공 | M | — | (삭제됨) | — | 폐기 (→ REQ-142) |
| REQ-124 | 즉각 피드백과 해설 | M | 통합 설계안 §5.1 | `services/learning_session.py`, `schemas/learning_session.py`, `views/study-session-view.js` | `test_learning_session_api.py` | 구현 완료 (v2.1) |
| REQ-125 | 발음 청취 (TTS) | S | UI/UX 설계서 | `src/frontend/js/core/tts.js`, `views/study-session-view.js` | TC-125 | 구현 완료 |
| REQ-126 | 다크 모드 | S | UI/UX 설계서 §12 | `src/frontend/js/core/theme.js`, `css/app.css`, `index.html` | TC-126 | 구현 완료 (v1.1 Phase 1) |
| REQ-127 | 키보드 단축키 | S | UI/UX 설계서 | `core/shortcuts.js`, `core/session-view-model.js` | `src/frontend/tests/` | 구현 완료 (v2.1) |
| REQ-128 | 단어장 단어 수 노출 | S | — | (삭제됨) | — | 폐기 (→ REQ-140) |
| REQ-129 | 오답 복습 | S | 통합 설계안 §5.1 | `services/stats.py`, `routers/study.py`, `views/review-view.js` | `test_review_session_api.py`, `test_stats_api.py` | 구현 완료 (v2.1) |
| REQ-130 | 중급 1,000제 추천 프리셋 | S | — | (삭제됨) | — | 폐기 (→ REQ-143) |
| REQ-131 | 학습 지표 서버 집계 | S | 통합 설계안, Data Design | `services/stats.py`, `routers/study.py`, `views/stats-view.js`, `core/home-model.js` | `test_stats_api.py` | 구현 완료 (v2.1) |
| REQ-132 | 최근 7일 학습 차트 | S | UI/UX 설계서 | `core/weekly-chart.js`, `views/stats-view.js` | `test_stats_api.py` | 구현 완료 (v2.1) |
| REQ-133 | 단어장 카드 진행률과 학습 시작 | S | UI/UX 설계서 | `views/explore-view.js`, `core/explore-model.js` | `src/frontend/tests/` | 구현 완료 (v2.1) |
| REQ-134 | 계정 드롭다운 메뉴 | M | UI/UX 설계서 §3.9 | `src/frontend/js/app.js`, `css/app.css` | TC-134 | 구현 완료 (v2.1: 백업 항목 제거) |
| REQ-135 | CSV 내보내기 확인 모달 | M | — | (삭제됨) | — | 폐기 (→ —) |
| REQ-136 | 단어장별 CSV 내보내기 | S | — | (삭제됨) | — | 폐기 (→ —) |
| REQ-137 | 정답 효과음 | S | UI/UX 설계서 | `core/sound.js`, `views/study-session-view.js` | TC-137 | 구현 완료 |
| REQ-138 | 정답 소리 음소거 | S | UI/UX 설계서 §3.1 | `core/sound.js`, `js/app.js`, `index.html` | TC-138 | 구현 완료 (v2.0) |
| REQ-139 | CSV 가져오기 정합성 | M | — | (삭제됨) | — | 폐기 (→ —) |
| REQ-140 | 표준 단어장 카탈로그 조회 | M | 통합 설계안 §4~5, Data Design(system_vocabularies) | `src/backend/routers/vocabulary.py`, `services/system_vocab.py` | `test_vocabulary_api.py` | 구현 완료 (v2.1) |
| REQ-141 | 표준 단어 목록 조회 | M | 통합 설계안 §5.1, Data Design(system_words) | `routers/vocabulary.py`, `services/system_vocab.py` | `test_vocabulary_api.py` | 구현 완료 (v2.1) |
| REQ-142 | 학습 단어장 선택(활성화) | M | 통합 설계안 §5.1, Data Design(users.active_vocabulary_id) | `routers/vocabulary.py`(me_router), `services/auth.py` | `test_vocabulary_api.py`, `test_auth_api.py` | 구현 완료 (v2.1) |
| REQ-143 | 표준 단어장 시드 | M | 통합 설계안 §7 | `src/backend/services/system_seed.py`, `src/backend/data/seeds/` | `test_system_seed.py` | 구현 완료 (v2.1) |

**상태 값 정의**: `초안` (명세만 작성) / `설계 완료` / `구현 완료` / `검증 완료`.
**요구사항 ID 체계**: `REQ-0xx` = 기능 요구사항(FR), `REQ-1xx` = 비기능 요구사항(NFR). 번호는 재사용하지 않으며, 폐기 시 상태만 `폐기`로 바꾼다.

---

## 8. 변경 이력

| 버전 | 날짜 | 내용 | 작성 |
| :--- | :--- | :--- | :--- |
| v0.1 | 2026-11-02 | 초안 작성 (요구사항 ID 체계 수립, 기능/비기능 목록, 추적 매트릭스) | Claude |
| v1.0 | 2026-11-02 | 사용자 승인 후 `docs/`로 승격 (파일명 `Requirement_Spec` 규칙 적용) | Claude |
| v2.1 | 2026-11-05 | 중앙 제공형 단어장 전환(D단계) 반영. **폐기**: REQ-004~011, 013, 123, 128, 130, 135, 136, 139 (A안: 번호 재사용 금지). **신설**: REQ-140~143 (표준 단어장 카탈로그·단어 목록·학습 단어장 선택·시드). **개정**: REQ-001, 003, 012, 014~019, 122, 124, 125, 127, 129, 131~134, 137 및 §1, §3, §5, §6 (세션 러너 규격, 출제 응답 정답 비노출·채점 응답 공개, 숙련 판정, 서버 집계 통계). 옛 `/api/study/flashcards`, `/api/study/quiz/*` 와 `wordbooks`·`words` 테이블 제거 | Claude |
| v2.0 | 2026-11-02 | v2.0 정식 릴리즈 반영. REQ-131 대시보드 핵심 지표, REQ-132 최근 7일 학습 차트(오늘 뱃지), REQ-133 단어장 카드 진행률과 퀵 액션, REQ-134 계정 드롭다운, REQ-135 CSV 내보내기 확인 모달, REQ-136 단어장별 내보내기, REQ-137 정답 효과음(Web Audio), REQ-138 음소거 설정, REQ-139 CSV 가져오기 정합성 신설. 예문 뜻(`words.example_meaning`) 기능 반영 (v2 Phase 1). 데이터 설계 v2.0, API 연동 규격서 v2.0, UI/UX 설계서 v2.0과 정합 | Claude |
| v1.5 | 2026-11-02 | v1.1 Phase 1·2 구현 반영. REQ-125 발음 청취(TTS), REQ-126 다크 모드, REQ-127 키보드 단축키, REQ-128 단어장 단어 수 노출, REQ-129 오답 복습 퀴즈(최근 100건, 4개 미만 차단), REQ-130 중급 1,000제 추천 프리셋 신설. 구현 상태는 §7 추적 매트릭스에 반영. 데이터 설계 v1.4, API 연동 규격서 v1.2, UI/UX 설계서 v1.2와 정합 | Claude |
| v1.4 | 2026-11-02 | 정식 릴리즈 v1.0 반영. REQ-001 이메일 제거, 닉네임(2~30자) 고유 키 기반 가입. REQ-121 계정 키를 닉네임으로 변경. REQ-122 회원 탈퇴 신설, REQ-123 기본 단어장 3종(초/중/고 200제) 자동 제공 신설, REQ-015 즉시 판정 반영, REQ-124 퀴즈 즉각 피드백과 해설 신설 | Claude |
| v1.3 | 2026-11-02 | REQ-121 추가 (로그인 무차별 대입 방어: IP 또는 계정 기준 1분 내 5회 실패 시 429, Retry-After 헤더). 구현은 프로세스 메모리 기반이므로 단일 프로세스 배포를 전제한다. 요청된 REQ-120은 기존 '코드 추적성' 항목과 ID가 충돌하여 사용하지 않고 REQ-121로 부여했다 | Claude |
| v1.2 | 2026-11-02 | REQ-002 세션을 DB `sessions` 테이블로 확정 (14일 절대 만료, 기본값), REQ-110 bcrypt 확정, REQ-001 비밀번호 72바이트 제한 추가. 데이터 설계서 v1.1 및 ADR-001/002와 정합 | Claude |
| v1.1 | 2026-11-02 | §6 질의 Q1~Q8 확정 반영. REQ-001 세션 쿠키, REQ-004/105 단어장 이름 유일성, REQ-005/009 페이지 크기 20, REQ-007 하드 삭제, REQ-009 접두사 검색(뜻 검색 제외), REQ-016 문항별 이력(최근 100건), REQ-102 p95 300ms, REQ-108 `utf8mb4_0900_ai_ci`, REQ-109 UTC 저장, REQ-118 커버리지 80%. 데이터 설계서 v1.0과 정합 | Claude |

---

## 9. v2.1 폐기·개정 현황

| 구분 | 요구사항 | 비고 |
| :--- | :--- | :--- |
| **폐기** (후속 있음) | REQ-004·005 → 140 / REQ-006 → 142 / REQ-007 → 122 / REQ-008 → 143 / REQ-009 → 141 / REQ-013 → 012 / REQ-123 → 142 / REQ-128 → 140 / REQ-130 → 143 | 개인 단어장·단어 CRUD, 프리셋, 가입 시 복사, 셔플 |
| **폐기** (후속 없음) | REQ-010, 011, 135, 136, 139 | 단어 수정·삭제, CSV 내보내기·가져오기 |
| **신설** | REQ-140~143 | 중앙 제공형 카탈로그 |
| **개정** | REQ-001, 003, 012, 014, 015, 016, 017, 018, 019, 122, 124, 125, 127, 129, 131, 132, 133, 134, 137 | 세션 러너·표준 콘텐츠 기준 |
| **유지** | REQ-002, 020~023, 101, 102, 104~121, 126, 138 | REQ-102~106 은 문구만 §5 에서 조정 |
