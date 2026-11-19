# 요구사항 명세서 (Requirement Spec)

| 항목 | 내용 |
| :--- | :--- |
| 프로젝트 | voda-voca (보다보카, 웹 기반 단어장 서비스) |
| 문서 종류 | 요구사항 명세서 (Requirement Spec, `개발방법론.md` §2.2) |
| 버전 / 상태 | v2.1 / **승인 (Approved)** — 중앙 제공형 단어장 전환 반영. REQ-125, REQ-137, REQ-138 은 2026-11-05 에, REQ-141 은 2026-11-06 에 v2.2 사양으로 개정, REQ-144 신설, REQ-145·REQ-146·REQ-147 은 2026-11-10 에, REQ-148 은 2026-11-11 에 신설 |
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
- **S-03 실력 점검**: 퀴즈 세션(기본 10문항, 설정에서 10·20·30 선택) → 보기를 고르면 즉시 정오와 해설 → 마지막에 정답 수와 오답 노트 확인
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
| REQ-141 | 표준 단어 목록 조회 | M | 단어장의 단어를 읽기 전용으로 조회한다 (`GET /api/vocabularies/{id}/words`, `page`/`size`, 본인 북마크 여부 포함). 없는 단어장은 404. 단어는 `term`, `meaning`, `example`, `example_meaning`, `phonetic`(v2.2, 없으면 null) 을 가지며, 예문이 없으면 `example_meaning` 도 없다. |
| REQ-142 | 학습 단어장 선택(활성화) | M | 사용자는 학습할 단어장 하나를 고른다 (`POST /api/users/me/active-vocabulary`, 본문 `{"vocabulary_id"}`). 성공하면 그 단어장의 카탈로그 항목을 돌려주고, 같은 값을 다시 보내도 성공한다. 없는 단어장은 404. 가입한 사용자는 초급 단어장이 자동 활성화되며, 활성 단어장이 없는 사용자가 세션을 시작하면 첫 단어장이 활성화된다. 활성 단어장 행이 사라지면 활성 값은 비워진다 (`ON DELETE SET NULL`). |
| REQ-143 | 표준 단어장 시드 | M | 콘텐츠는 서버 시드 파일로만 바뀐다. 앱 시작 시 멱등으로 적재한다 (`slug` 가 멱등 키, `content_hash` 가 같으면 쓰기를 생략). 초기 범위는 초급·중급·고급 각 200단어(총 600)이며, v2.2 에서 시험 대비·실무 비즈니스 각 200단어가 더해져 총 1,000단어다 (REQ-145). `category` 는 자유 문자열이며 새 카테고리는 스키마 변경 없이 시드만으로 추가한다. |
| REQ-144 | 단어 발음기호(IPA) 연동 및 표시 | S | (v2.2) 표준 단어에 **미국식 IPA** 발음기호를 싣고 화면에 보인다 (기존 600개, 이어서 REQ-145 의 신규 400개까지 총 1,000개). ① **저장**: `system_words.phonetic`(VARCHAR(100), NULL 허용)에 **슬래시 없는** IPA 문자열로 저장하고(예: `ˈæpəl`), 시드 로더가 IPA 문자(라틴 소문자·IPA 확장·수정 문자·결합 기호·공백)만 허용해 검증한다. 한글·슬래시·대괄호·제어 문자와 100자 초과는 거부한다. 값이 바뀌면 `content_hash` 가 달라져 DB 에 반영된다. ② **API**: 단어 목록(`VocabularyWordOut`)·플래시카드 출제(`SessionItemOut`)·채점(`SessionAnswerOut`)이 `phonetic`(문자열 또는 null)을 싣는다. **퀴즈 출제 응답의 `phonetic` 은 단어에 값이 있어도 항상 null** 이다(채점 전 정보 최소화, REQ-014·REQ-124). ③ **표시**: 화면이 `/…/` 서식을 입힌다. 해설 시트(퀴즈 채점 후)와 단어 시트에서는 표제어 오른쪽에, 플래시카드는 **앞면의 표제어 아래**에 보이고 뒷면과 퀴즈 문제 화면에는 보이지 않는다 (2026-11-10 개정: 소리를 짐작하며 뜻을 떠올리게 하려고 앞면으로 옮겼다). 복습함의 북마크·틀린 단어 행에서는 표제어 옆(품사 오른쪽)에 보인다 (2026-11-11). 복습함은 조회 API 라 위 비노출 규칙의 대상이 아니다. 값이 없으면(null·빈 값) 요소를 그리지 않는다. ④ **접근성**: 발음기호는 `aria-hidden="true"` 시각 전용이며 낭독은 🔊 버튼(REQ-125)이 맡는다. ⑤ **데이터 출처·라이선스**: CMU Pronouncing Dictionary(CMUdict, Copyright (C) 1993-2015 Carnegie Mellon University, BSD 계열 라이선스)의 미국식 발음을 IPA 로 변환하고, 미수록·동형이음 단어는 수기로 확정했다. 저작권 고지와 라이선스 조건은 §10 에 유지한다. |
| REQ-145 | 시험 대비·실무 비즈니스 카탈로그 확충 | S | (v2.2) 표준 카탈로그를 시험 대비와 직장 영어로 넓힌다. ① **단어장**: `exam-core-200`(제목 "시험 대비 핵심 200", category `EXAM`, level 3, sort_order 4)과 `business-practical-200`(제목 "실무 비즈니스 영단어 200", category `BUSINESS`, level 3, sort_order 5) 각 200단어를 추가해 총 **1,000단어**(5개 단어장)로 한다. 시험 이름은 상표이므로 제목에 쓰지 않고 설명란에 "영어 공인시험"처럼 서술형으로만 표기한다. ② **단어 규격**: 신규 400단어는 **단일 단어**(숙어·구동사 제외)이며 `term`, `phonetic`(REQ-144 규격), `pos`, `meaning`, `example`, `example_meaning` 6개를 모두 갖는다. 예문에는 표제어 또는 그 활용형이 들어 있어야 하고, 전체 1,000단어의 표제어는 서로 겹치지 않으며, 한 단어장 안에서 뜻이 겹치지 않는다(퀴즈 보기 모호성 방지). ③ **품사(`pos`)**: 영문 소문자 `noun`·`verb`·`adjective`·`adverb`·`preposition`·`conjunction` 중 하나(v2.2 후속으로 `pronoun`·`interjection` 추가, REQ-146). `system_words.pos` 에 저장한다 (API·화면 노출은 REQ-146). 기존 600단어도 v2.2 후속에서 품사를 채워 **1,000단어 전부에 값이 있다**. ④ **기존 데이터 불변**: `pos` 는 값이 있을 때만 `content_hash` 에 넣는다. 기존 3개 단어장은 품사를 채우며 해시가 한 번 바뀌어 앱 시작 때 `system_words` 가 갱신(UPDATE)되지만, `word_id`·사용자 진행 기록은 그대로 유지된다. 신규 단어장은 앱 시작 시 한 번 적재된다. ⑤ **화면**: 탐색 화면 카테고리 칩에 `EXAM`=시험, `BUSINESS`=비즈니스 한글 라벨을 쓴다. ⑥ **데이터 출처**: 단어·뜻·예문은 직접 작성했고 발음기호는 CMUdict 변환이다 (요구사항 명세 §10). |
| REQ-146 | 품사 표시 | S | (v2.2) 시드의 품사(`pos`)를 API 로 내려 화면에 보인다. ① **API**: 단어 목록(`VocabularyWordOut`)·출제(`SessionItemOut`, **퀴즈와 플래시카드 모두**)·채점(`SessionAnswerOut`)이 `pos`(영문 소문자 문자열 또는 null)를 싣는다. 발음기호와 달리 **퀴즈 출제 응답에서도 숨기지 않는다** (품사는 뜻을 직접 알려 주지 않는다). 진행 중인 옛 세션(스냅샷에 키 없음)은 null. 추가 필드라 하위 호환이다. ② **표시**: 화면이 한글 라벨(`noun`=명사, `verb`=동사, `adjective`=형용사, `adverb`=부사, `preposition`=전치사, `conjunction`=접속사, `pronoun`=대명사, `interjection`=감탄사; 그 밖의 값은 그대로)을 작은 알약 `.pos-tag` 로 입힌다. 위치는 단어 미리보기 시트(표제어 오른쪽), 퀴즈 문제 화면(표제어 아래), 플래시카드 **앞면**(표제어 아래, 발음기호 왼쪽), 퀴즈 해설 시트(표제어 오른쪽)다. 복습함 행(표제어 오른쪽, 발음기호 왼쪽)에도 보인다 (2026-11-11). 플래시카드 뒷면에는 보이지 않는다. 값이 없으면 요소를 그리지 않는다 (현재 시드 1,000단어는 모두 값이 있다). ③ **플래시카드 구성 변경**: 앞면 = 표제어·품사·발음기호, 뒷면 = 뜻·예문·예문 뜻 (뒷면에서 표제어와 발음기호를 뺀다, REQ-144 개정). |
| REQ-147 | 학습 개수 사용자 설정 | S | (v2.2) 사용자가 퀴즈·플래시카드 1회 문항 수와 오늘의 목표를 고른다. ① **설정 3종**: `quiz_count`(퀴즈 1회 문항 수), `flashcard_count`(플래시카드 1회 문항 수), `daily_goal`(오늘의 목표). 값은 **10·20·30** 중 하나이고 **기본은 10** 이다. 선택 가능한 값은 서버 상수 한 곳에서 정하며 API 응답(`options`)으로 내려 프론트가 하드코딩하지 않는다. ② **저장**: 사용자별로 서버 DB(`users` 컬럼 3개)에 저장한다. DB 는 양수만 검사하고 허용 값은 앱이 검증한다(옵션 확장 시 마이그레이션 불필요). ③ **API**: `GET`·`PATCH /api/users/me/settings`. 부분 수정을 허용하고, 허용 값 밖·null·알 수 없는 필드는 422. ④ **세션 반영**: 세션 생성(`POST /api/study/sessions`)에서 `count` 를 **생략하면** `mode` 에 맞는 설정(`quiz_count`/`flashcard_count`)을 쓴다. 값을 보내면 기존처럼 1~30 으로 그 값을 쓴다. 북마크·오답 복습도 같다. ⑤ **화면**: 상단바 계정 메뉴의 "학습 설정"(`book-open` 아이콘, 환경 설정 항목 바로 위)을 누르면 모달이 열리고, 행 3개(퀴즈·플래시카드·오늘의 목표) × 칩 3개로 고른다. 선택 즉시 반영·저장하며 실패하면 이전 값으로 되돌리고 모달 안에 오류를 보인다(홈에는 설정 카드를 두지 않는다). 오늘의 목표 카드와 시작 버튼 문구("N문항 학습 시작", 현재 모드 기준)가 설정을 따른다. ⑥ **기본값 변경**: 이전의 고정값 15(세션·목표)는 폐기되고 기존 사용자도 10 으로 시작한다. |
| REQ-148 | 세션 중 북마크 | S | (v2.2) 퀴즈·플래시카드를 진행하는 중에 현재 단어를 북마크에 넣고 뺀다. ① **버튼**: 카드 **오른쪽 위** 44px 토글(`aria-pressed`), 플래시카드에서는 눌러도 카드가 뒤집히지 않고, 앞·뒷면 각각의 오른쪽 위에 버튼이 있어 카드와 함께 뒤집히며 두 버튼의 상태는 같다 (2026-11-11). ② **초기 상태**: 출제 응답 `SessionItemOut.bookmarked`(요청 사용자의 북마크 여부, 출제 시점 기준, 기본 false). 세션 스냅샷에는 저장하지 않는다. ③ **동작**: 기존 `PUT`/`DELETE /api/bookmarks/{word_id}`(REQ-017)를 쓴다. 응답을 기다리지 않고 바로 상태를 바꾸고, 실패하면 되돌린 뒤 오류 토스트를 띄운다. 같은 단어의 요청이 진행 중이면 추가 입력을 무시한다. 화면이 다시 그려져도 사용자가 바꾼 값은 유지한다. |
| REQ-149 | 환경 설정 | S | (v2.2) 사용자가 효과음과 다크 모드를 계정 메뉴의 **환경 설정** 모달에서 바꾼다. ① **진입**: 상단바 계정 메뉴의 "환경 설정"(학습 설정 바로 아래). 헤더에는 효과음·다크 모드 버튼을 두지 않는다. ② **구성**: 효과음·다크 모드 두 행의 스위치(`role="switch"`, `aria-checked`). 누르면 즉시 적용·저장하고 확인 버튼 없이 "닫기"만 둔다. 효과음은 `voda.sound_muted`(기본 켬), 다크 모드는 `voda.theme`(없으면 시스템 설정)에 저장한다 — REQ-138·REQ-126 과 같은 저장소다. ③ **동기화**: 효과음은 엔진 구독으로 어디서 바뀌어도 스위치가 따라온다. 모달을 닫을 때 구독을 해제한다. ④ **터치·접근성**: 행 높이 44px 이상, 행 전체가 스위치라 라벨과 설명을 함께 낭독한다. ⑤ **제약**: 로그인 상태에서만 열 수 있어 로그인·회원가입 화면에서는 다크 모드를 전환할 수 없다(저장값·시스템 설정은 적용). ⑥ **모션**: 모달 등장·퇴장은 오버슈트 없는 220ms/140ms 페이드+이동이고 `prefers-reduced-motion` 에서는 끈다(UI/UX 설계서 §9). |

### 4.3 단어 (Word)

| ID | 요구사항 | 우선순위 | 상세 기준 (Acceptance Criteria) |
| :--- | :--- | :---: | :--- |
| REQ-008 | 단어 추가 | M | **폐기** (v2.1) — 사용자 단어 쓰기 경로 폐지. 단어는 시드로만 추가된다 (REQ-143) |
| REQ-009 | 단어 목록 조회 및 검색 | M | **폐기** (v2.1) — 목록 조회는 REQ-141. 표제어 접두사 검색은 제공하지 않는다 |
| REQ-010 | 단어 수정 | M | **폐기** (v2.1) |
| REQ-011 | 단어 삭제 | M | **폐기** (v2.1) |
| REQ-125 | 발음 청취 (TTS) | S | 브라우저 음성 합성(Web Speech API)으로 **표제어와 예문**을 읽어 준다. 외부 음성 서비스와 API 키는 쓰지 않는다. ① **버튼 위치**: 학습 세션 헤더(표제어), 해설 시트(**예문만** — 표제어는 헤더에 이미 있어 2026-11-11 에 뺐다), 플래시카드 뒷면(예문), 단어 미리보기 시트(행마다 **표제어만** — 미리보기는 훑어보는 용도라 예문 듣기를 두지 않는다, 2026-11-10 개정). 버튼은 44×44px 이상이다. ② **보이스**: 사용자 선택 UI 없이 자동 판별한다. en-US, en-GB, 그 밖의 en-* 순이며 같은 언어 안에서는 기기 내장(localService) 보이스를 먼저 쓴다. 보이스 목록이 늦게 채워지는 브라우저(`voiceschanged`)에서도 재생을 막지 않는다. ③ **속도**: 표제어 0.9, 예문 0.85, 음높이 1.0. ④ **재생 동작**: 소리는 사용자가 버튼을 누른 때에만 낸다(자동 재생 없음). 연속으로 누르면 이전 발음을 끊고 새로 읽는다. 문항 전환·해설 시트 닫힘·세션 중단/종료·단어 시트 닫힘·화면 이동·탭 숨김 시 재생을 멈춘다. ⑤ **재생 상태 표시**: 재생 중인 버튼만 강조하고(`aria-pressed`), 동작 줄이기 설정에서는 움직임 없이 색만 바꾼다. ⑥ **실패 처리**: 취소·중단(`canceled`/`interrupted`)은 정상 종료로 보고 조용히 넘긴다. 브라우저가 재생을 막았거나(`not-allowed`), 영어 보이스가 없거나, 음성 합성을 지원하지 않으면 예외 없이 실패하고 학습 세션당 최초 1회 토스트로 알린다. |

### 4.4 학습 (Study)

플래시카드와 퀴즈는 별도 화면이 아니라 **하나의 학습 세션 러너**(`/study/session`)의 두 모드(`flashcard`, `quiz`)다. 출제는 `POST /api/study/sessions`, 문항별 채점·기록은 `POST /api/study/sessions/{id}/answer` 이며 옛 `/api/study/flashcards`, `/api/study/quiz/*` 는 제거되었다.

| ID | 요구사항 | 우선순위 | 상세 기준 (Acceptance Criteria) |
| :--- | :--- | :---: | :--- |
| REQ-012 | 학습 세션 출제와 플래시카드 모드 | M | 세션을 만든다 (`POST /api/study/sessions`, 부수효과가 있으므로 `GET` 을 쓰지 않는다). 요청: `mode`(`quiz`·`flashcard`, 기본 quiz), `count`(1~30, 생략하면 내 설정 `quiz_count`/`flashcard_count`, 기본 10 — REQ-147), `include_memorized`(기본 false), `source`(`all`·`bookmarks`·`wrong`, 기본 all). **`all`** 은 활성 단어장에서 **워터폴 규칙**으로 고른다: 오답 풀은 최대 `floor(0.3×N)`, 기학습 복습을 `floor(0.1×N)` 먼저 확보, 나머지는 미학습 단어(`order_index` 순), 미학습이 모자라면 복습으로 충원하며, 숙련한 단어는 `include_memorized=false` 일 때 제외한다. 가용 단어가 N 미만이면 가능한 만큼만 출제하고, 출제 후 순서를 섞는다. 응답에는 `composition`(오답·복습·미학습 개수)이 있다. 출제 가능한 단어가 없으면 409 `NO_WORDS_TO_STUDY`, 활성화할 단어장이 없으면 409 `NO_VOCABULARY`. **플래시카드 모드**는 카드 **앞면에는 단어만** 보여 주고 탭하면 뒷면(뜻, 영문 예문, 예문 해석)을 뒤집어 보이며, "알아요"(true)와 "헷갈려요"(false)로 응답한다. 출제 응답에 뒷면 정보가 함께 실린다 (정답이 없는 모드이므로). |
| REQ-013 | 플래시카드 셔플 | S | **폐기** (v2.1) — 순서는 서버 출제가 결정하고 섞어 준다 (REQ-012). 사용자 셔플 조작은 두지 않는다 |
| REQ-014 | 객관식 퀴즈 모드 | M | 표제어와 예문(문맥)을 보여 주고 뜻 4지선다 중 하나를 고르게 한다. 오답 3개는 **같은 단어장의 다른 단어 뜻을 우선**하고 부족하면 전체 표준 단어에서 보충하며, 뜻이 같은 보기는 중복시키지 않는다. 활성 단어장의 단어가 4개 미만이면 퀴즈를 시작할 수 없고(400) 플래시카드는 허용한다. **출제 응답에는 정답을 싣지 않는다** — `options` 만 있고 `correct_index`, `meaning`, `example_meaning` 은 없다. |
| REQ-015 | 세션 결과 | M | 보기를 고르면 **즉시** 정오를 보여 준다 (정답 초록, 오답 빨강). 모든 문항에 답하면 세션이 끝나며(`is_finished`), 정답 수, 정답률, 오답 노트(틀린 단어, 정답 뜻, 내가 고른 뜻)를 보여 준다. 마지막 응답 후 30분이 지나면 새 답을 받지 않는다 (`QUIZ_EXPIRED`, 푼 문항은 이미 저장되어 있다). |
| REQ-016 | 학습 이력 기록과 숙련도 | S | 세션에서 **문항에 답할 때마다** 그 답 1건의 **정답 여부, 학습 모드(`quiz`·`flashcard`), 기록 시각**을 `study_logs` 에 저장한다. 플래시카드의 "알아요"는 정답, "헷갈려요"는 오답이다. 이력 기록과 사용자×단어 진행도(`user_word_progress`: 정답·오답 횟수, 연속 정답, 숙련 여부, 마지막 결과) 갱신은 **하나의 트랜잭션**이다. 정답이 연속 3회가 되면 숙련(`is_memorized`)이며, 오답 1회면 연속 횟수를 0으로 되돌리고 숙련을 해제한다. 같은 문항에 같은 답을 다시 보내면 이력을 늘리지 않고 같은 응답을 돌려주며(멱등), 다른 답으로 바꾸려 하면 409 `QUIZ_ANSWER_LOCKED` 다. 최근 학습 이력 **100건을 최신순**으로 조회할 수 있다 (`GET /api/study/logs`). 이 이력은 통계(REQ-131~133)와 오답 단어 판정(REQ-129)의 근거다. |
| REQ-124 | 즉각 피드백과 해설 | M | 문항마다 답을 기록하는 즉시 서버가 **채점 응답**(`POST /api/study/sessions/{id}/answer`)으로 정오(`is_correct`), 정답 선지(`correct_index`, 퀴즈), 표제어·뜻·예문·예문 뜻(해설), 갱신된 단어 진행도, 진행 상황(`answered`, `total`, `is_finished`)을 돌려준다. **정답과 해설은 채점 응답에서만 공개**되고 출제 응답에는 없다. 화면은 이를 카드로 보여 주고 [다음 문항] 버튼으로 넘어간다. 한 문항은 한 번 답하면 잠긴다. 예문이 없는 단어는 "해설 예문이 없습니다"를 보여 준다. |
| REQ-129 | 오답 복습 | S | 복습함의 "틀린 단어" 목록(`GET /api/study/wrong-words`, `page`/`size`≤100, 최근 틀린 순)에서 복습 세션(`source=wrong`)을 시작한다. **오답 판정은 단어별 마지막 결과가 오답인 단어**이며(최근 N건 제한 없음), 맞히면 대상에서 빠진다. 통계의 `wrong_word_count` 와 같은 규칙이다. 풀이 비면 409, 퀴즈는 4개 미만이면 400 이다. 복습 세션은 활성 단어장을 바꾸지 않고(`vocabulary_id` null) 숙련 단어를 제외하지 않는다. 목록 응답은 `pos`·`phonetic` 을 싣고(2026-11-11), 복습함 행은 북마크 목록과 같은 모양(표제어·품사·발음기호·단어장·뜻)이다. |

### 4.5 북마크 (Bookmark)

| ID | 요구사항 | 우선순위 | 상세 기준 (Acceptance Criteria) |
| :--- | :--- | :---: | :--- |
| REQ-017 | 북마크 토글 | M | 단어 카드 또는 목록에서 북마크를 켜거나 끈다 (`PUT`/`DELETE /api/bookmarks/{word_id}`, 204, 멱등). 같은 단어에 중복 북마크는 생성되지 않는다. 대상은 표준 단어이며 없는 단어는 404 다. |
| REQ-018 | 북마크 목록 조회 | M | 본인 북마크 단어를 소속 표준 단어장 정보와 함께 페이지 단위로 보여 준다 (`GET /api/bookmarks`). 복습함 화면에서 쓴다. 응답은 `pos`·`phonetic`(문자열 또는 null)을 싣고, 복습함 화면은 예문 대신 품사·발음기호를 보인다 (2026-11-11). |
| REQ-019 | 북마크 기반 학습 | S | 복습함에서 북마크 단어만으로 복습 세션(`source=bookmarks`)을 시작한다. 플래시카드와 퀴즈 모두 가능하며, 북마크가 4개 미만이면 퀴즈는 400 으로 거부되고 플래시카드만 허용한다. 복습 세션은 활성 단어장을 바꾸지 않는다. |

### 4.6 UI / 모바일 (User Interface)

| ID | 요구사항 | 우선순위 | 상세 기준 (Acceptance Criteria) |
| :--- | :--- | :---: | :--- |
| REQ-020 | 모바일 뷰포트 반응형 레이아웃 | M | 360px ~ 430px 폭의 모바일에서 가로 스크롤 없이 모든 주요 화면을 사용할 수 있다. 태블릿·데스크톱에서도 같은 기능을 제공한다. |
| REQ-021 | 터치 인터랙션 | M | 탭, 스와이프 제스처를 지원한다. 300ms 탭 딜레이는 `viewport` 메타 태그와 `touch-action`으로 제거한다. |
| REQ-022 | 알림·확인 UI | M | 브라우저 기본 `alert` / `confirm` 대신 SweetAlert2 모달을 사용한다. |
| REQ-023 | 아이콘 | S | 주요 액션 아이콘은 Lucide Icons로 표시한다. |
| REQ-126 | 다크 모드 | S | 계정 메뉴의 **환경 설정** 모달의 스위치(REQ-149)로 밝은 화면과 어두운 화면을 전환한다 (2026-11-11 개정: 헤더 버튼을 이동). 로그인·회원가입 화면에서는 전환할 수 없고 저장값 또는 시스템 설정을 따른다. 초기값은 저장된 선택이 있으면 그것을, 없으면 시스템 설정을 따른다. 선택은 브라우저(`voda.theme`)에 저장해 다음 방문에도 유지한다. 어두운 화면은 Zinc 계열 팔레트만 쓴다. 저장소를 쓸 수 없으면 저장 없이 동작한다. |
| REQ-127 | 키보드 단축키 (데스크톱) | S | 학습 세션에서 퀴즈는 숫자 `1`~`4` 로 보기를 고르고, 피드백이 뜬 뒤 `Enter`·`Space` 로 다음 문항으로 넘어간다. 플래시카드는 `Space`·`Enter` 로 뒤집고 `→` 알아요, `←` 헷갈려요로 응답한다. `Esc` 로 세션을 나가는 확인을 띄운다. 입력 칸이나 열린 모달에 포커스가 있으면 단축키를 무시한다. |
| REQ-131 | 학습 지표 서버 집계 | S | 통계 화면과 홈은 서버가 집계한 지표를 보여 준다 (`GET /api/study/stats`): 누적 푼 문항 수·정답 수·정답률(기록이 없으면 null → "—"), 연속 학습일(한국 날짜 기준, 오늘 기록이 없으면 어제부터), 최근 7일 활동, 모든 표준 단어 수 합계, 단어장별 진행률, 오답 단어 수. **최근 100건 제한이 없다** (v2.0 의 클라이언트 100건 집계를 대체). |
| REQ-132 | 최근 7일 학습 차트 | S | 통계 화면에서 최근 7일(오늘 포함)의 날짜별 학습 단어 수를 인라인 SVG 막대 차트로 보여 준다. 같은 날 같은 단어는 한 번으로 센다. 오늘 막대는 강조하고 "오늘" 뱃지를 붙인다. 막대를 누르거나 포커스하면 그 날의 개수를 표시한다. 값은 서버 집계(REQ-131)이며 외부 차트 라이브러리는 쓰지 않는다. |
| REQ-133 | 단어장 카드 진행률과 학습 시작 | S | 탐색 화면의 단어장 카드에 카테고리·레벨·단어 수 배지와 본인 진행률(학습한 단어 수, 진행률 바)을 보인다. 카드에서 그 단어장을 학습 단어장으로 선택하고(REQ-142) 홈에서 바로 학습을 시작할 수 있다. 진행률은 REQ-140 의 `user_progress` 를 쓴다. |
| REQ-134 | 계정 드롭다운 메뉴 | M | 닉네임 칩을 누르면 칩 아래에 팝오버가 뜬다. 프로필 헤더, 로그아웃, 회원 탈퇴(위험 구역)를 담는다. 로그아웃은 **확인 모달 없이 즉시** 세션을 종료하고 `/login` 으로 이동한다. 회원 탈퇴는 기존 두 단계 확인을 거친다. 바깥을 누르거나 ESC를 누르면 닫힌다. |
| REQ-135 | CSV 내보내기 확인 모달 | M | **폐기** (v2.1) — CSV 백업 기능 폐지 (개인 단어가 없다) |
| REQ-136 | 단어장별 CSV 내보내기 | S | **폐기** (v2.1) |
| REQ-137 | 세션 효과음 | S | 학습 세션에서 Web Audio API 로 효과음을 합성한다. 외부 오디오 파일은 내려받지 않는다. ① **큐 4종**: `correct`(정답, C5-E5-G5 상승 아르페지오), `milestone`(콤보 5·10·15 도달, C5-E5-G5-C6 4음 상승이며 정답음을 대체), `wrong`(오답, 196Hz 에서 130.8Hz 로 가라앉는 낮고 부드러운 한 음, 최대 음량 0.12·어택 30ms), `complete`(세션 완료, G4-C5-E5-G5 상승 뒤 C5·E5·G5 화음 팡파레). ② **재생 규칙**: 4지선다 퀴즈의 오답에는 `wrong` 을 낸다. 플래시카드 자가 평가("알아요"·"헷갈려요")는 모두 무음이다 ("알아요"의 소리는 퀴즈 정답음과 같아 중복이라 2026-11-11 에 뺐다. 콤보 마일스톤음도 퀴즈에서만 난다). `complete` 는 정상 완주이고 정답이 1개 이상일 때만 세션당 한 번 낸다(중단·푼 문항 없음·전부 오답은 무음). ③ **음질**: 모든 음은 마스터 게인(0.6)을 거치며, 같은 순간 울리는 음량의 합이 클리핑되지 않도록 제한하고, 음이 끝나면 오디오 노드를 해제한다. ④ **콤보**: 세션 안의 연속 정답 수를 "콤보"라 부르며, 2콤보부터 세션 상단 뱃지로 보여 준다(화면 규격은 UI/UX 설계서 §12.7). 콤보 계산은 `core/combo-model.js` 한 곳에서 하고 러너가 위임한다. 완료 요약에는 "최대 콤보"를 보인다. ⑤ 컨텍스트가 정지 상태이면 사용자 제스처에서 재개하고, 미지원·생성 실패는 예외 없이 무음으로 넘어간다. |
| REQ-138 | 효과음 음소거 | S | 계정 메뉴의 **환경 설정** 모달의 효과음 스위치(REQ-149, 켬 `bell-ring` / 끔 `bell-off`)로 (2026-11-11 개정: 헤더 버튼을 이동) REQ-137 의 효과음 전체를 끄고 켠다. 설정은 `voda.sound_muted`에 저장하며 기본값은 켬이다. 음소거 중에는 소리를 내지 않고, 상태가 바뀌면 구독 중인 모든 토글이 즉시 따라온다. 발음(TTS, REQ-125)은 사용자가 직접 누르는 소리라 이 설정과 별개이며 `volume-2` 아이콘을 쓴다. |
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
| Q4 | 단어 필드 구성 | 표제어·뜻·예문·예문 뜻 (품사는 v2.2 에서 전체 1,000단어 시드에 싣고 REQ-146 으로 API·화면에 노출). **발음기호는 v2.2 부터 사용** (미국식 IPA, REQ-144) | 기본값 적용, v2.2 개정 | REQ-141, REQ-144 |
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
| 효과음 큐 | `correct` 간격 0.07초·각 0.18초·음량 0.2 / `milestone` 간격 0.08초·마지막 C6 0.4초 / `wrong` 196→130.8Hz·0.25초·음량 0.12 / `complete` 상승 4음 뒤 화음 0.6초 / 마스터 게인 0.6 | REQ-137 |
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
| REQ-018 | 북마크 목록 | M | Integration Spec | `src/backend/routers/bookmark.py`, `schemas/bookmark.py`, `views/review-view.js` | `test_bookmark_api.py`(`test_list_carries_pos_and_phonetic…`), `tests/review-model.test.js` | 구현 완료 |
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
| REQ-125 | 발음 청취 (TTS) | S | UI/UX 설계서 §3.6, §12.6 | `src/frontend/js/core/tts.js`, `core/speak-model.js`, `views/components/speak-button.js`, `views/components/{progress-header,feedback-sheet,word-sheet}.js`, `views/study-session-view.js`, `app.js` | TC-125 (`tests/tts.test.js`, `tts-state.test.js`, `speak-ui.test.js`) | 구현 완료 (v1.1 Phase 1, 예문·상태 표시·알림은 v2.2 에서 확장) |
| REQ-126 | 다크 모드 | S | UI/UX 설계서 §12, §12.12 | `src/frontend/js/core/theme.js`, `views/preferences-modal.js`, `css/app.css` | TC-126 | 구현 완료 (v1.1 Phase 1) |
| REQ-127 | 키보드 단축키 | S | UI/UX 설계서 | `core/shortcuts.js`, `core/session-view-model.js` | `src/frontend/tests/` | 구현 완료 (v2.1) |
| REQ-128 | 단어장 단어 수 노출 | S | — | (삭제됨) | — | 폐기 (→ REQ-140) |
| REQ-129 | 오답 복습 | S | 통합 설계안 §5.1 | `services/stats.py`, `routers/study.py`, `schemas/study.py`, `views/review-view.js` | `test_review_session_api.py`(`test_wrong_words_carries_pos_and_phonetic`), `test_stats_api.py` | 구현 완료 (v2.1) |
| REQ-130 | 중급 1,000제 추천 프리셋 | S | — | (삭제됨) | — | 폐기 (→ REQ-143) |
| REQ-131 | 학습 지표 서버 집계 | S | 통합 설계안, Data Design | `services/stats.py`, `routers/study.py`, `views/stats-view.js`, `core/home-model.js` | `test_stats_api.py` | 구현 완료 (v2.1) |
| REQ-132 | 최근 7일 학습 차트 | S | UI/UX 설계서 | `core/weekly-chart.js`, `views/stats-view.js` | `test_stats_api.py` | 구현 완료 (v2.1) |
| REQ-133 | 단어장 카드 진행률과 학습 시작 | S | UI/UX 설계서 | `views/explore-view.js`, `core/explore-model.js` | `src/frontend/tests/` | 구현 완료 (v2.1) |
| REQ-134 | 계정 드롭다운 메뉴 | M | UI/UX 설계서 §3.9 | `src/frontend/js/app.js`, `css/app.css` | TC-134 | 구현 완료 (v2.1: 백업 항목 제거) |
| REQ-135 | CSV 내보내기 확인 모달 | M | — | (삭제됨) | — | 폐기 (→ —) |
| REQ-136 | 단어장별 CSV 내보내기 | S | — | (삭제됨) | — | 폐기 (→ —) |
| REQ-137 | 세션 효과음 | S | UI/UX 설계서 §3.6, §12.7 | `core/sound.js`, `core/combo-model.js`, `core/session-runner.js`, `views/components/combo-badge.js`, `views/study-session-view.js` | TC-137 (`tests/sound.test.js`, `combo-model.test.js`, `combo-ui.test.js`) | 구현 완료 (정답음은 v1.1, 오답·마일스톤·완료·콤보는 v2.2 에서 확장) |
| REQ-138 | 효과음 음소거 | S | UI/UX 설계서 §3.1, §12.7, §12.12 | `core/sound.js`, `views/preferences-modal.js` | TC-138 | 구현 완료 (v2.0) |
| REQ-139 | CSV 가져오기 정합성 | M | — | (삭제됨) | — | 폐기 (→ —) |
| REQ-140 | 표준 단어장 카탈로그 조회 | M | 통합 설계안 §4~5, Data Design(system_vocabularies) | `src/backend/routers/vocabulary.py`, `services/system_vocab.py` | `test_vocabulary_api.py` | 구현 완료 (v2.1) |
| REQ-141 | 표준 단어 목록 조회 | M | 통합 설계안 §5.1, Data Design(system_words) | `routers/vocabulary.py`, `services/system_vocab.py` | `test_vocabulary_api.py` | 구현 완료 (v2.1) |
| REQ-142 | 학습 단어장 선택(활성화) | M | 통합 설계안 §5.1, Data Design(users.active_vocabulary_id) | `routers/vocabulary.py`(me_router), `services/auth.py` | `test_vocabulary_api.py`, `test_auth_api.py` | 구현 완료 (v2.1) |
| REQ-143 | 표준 단어장 시드 | M | 통합 설계안 §7 | `src/backend/services/system_seed.py`, `src/backend/data/seeds/` | `test_system_seed.py` | 구현 완료 (v2.1) |
| REQ-144 | 단어 발음기호(IPA) 연동 및 표시 | S | UI/UX 설계서 §3.6, §3.3, §12.8, Data Design §3.3·§3.9, API 규격서 §3.2·§3.4·§6.2 | `services/system_seed.py`, `data/seeds/words/*.json`, `schemas/vocabulary.py`, `schemas/learning_session.py`, `core/phonetic.js`, `views/components/phonetic-line.js`, `feedback-sheet.js`, `word-sheet.js`, `study-session-view.js`, `css/app.css` | `test_system_seed.py`, `test_vocabulary_api.py`, `test_learning_session_api.py`, `src/frontend/tests/phonetic.test.js` | 구현 완료 (v2.2) |
| REQ-145 | 시험 대비·실무 비즈니스 카탈로그 확충 | S | Data Design §3.3·§3.9, API 규격서 §3.2, UI/UX 설계서 §3.3 | `services/system_seed.py`, `models/system_word.py`, `data/seeds/vocabularies.json`, `data/seeds/words/exam-core-200.json`, `business-practical-200.json`, `core/explore-model.js` | `test_system_seed.py`(관문 8종·골든 해시·pos), `test_vocabulary_api.py`, `test_phonetic_api.py`, `src/frontend/tests/explore-model.test.js` | 구현 완료 (v2.2) |
| REQ-146 | 품사 표시 | S | UI/UX 설계서 §3.3, §3.6, §12.9, API 규격서 §3.2·§3.4·§6.2, Data Design §3.3·§3.7 | `schemas/vocabulary.py`, `schemas/learning_session.py`, `services/learning_session.py`, `services/study.py`, `routers/vocabulary.py`, `core/pos.js`, `views/components/pos-tag.js`, `feedback-sheet.js`, `word-sheet.js`, `study-session-view.js`, `css/app.css` | `test_pos_api.py`, `test_vocabulary_api.py`, `src/frontend/tests/pos.test.js`, `session-view-model.test.js` | 구현 완료 (v2.2) |
| REQ-147 | 학습 개수 사용자 설정 | S | UI/UX 설계서 §3.2, §3.7.1, §12.10, API 규격서 §3.4·§3.7, Data Design §3.1 | `models/user.py`, `schemas/user_settings.py`, `routers/user_settings.py`, `routers/study_session.py`, `schemas/learning_session.py`, `core/settings-model.js`, `core/settings-store.js`, `core/home-model.js`, `views/home-view.js`, `views/settings-modal.js`, `views/components/settings-form.js`, `app.js` | `test_user_settings_model.py`, `test_user_settings_api.py`, `test_session_count_setting.py`, `settings-model.test.js`, `settings-store.test.js`, `settings-ui.test.js`, `home-model.test.js` | 구현 완료 (v2.2) |
| REQ-148 | 세션 중 북마크 | S | UI/UX 설계서 §3.6, §12.11, API 규격서 §3.4(`SessionItemOut.bookmarked`), REQ-017 | `schemas/learning_session.py`, `services/learning_session.py`, `core/bookmark-store.js`, `views/components/bookmark-button.js`, `views/study-session-view.js` | `test_learning_session_api.py`(`bookmarked` 3건), `bookmark-store.test.js`, `bookmark-ui.test.js` | 구현 완료 (v2.2) |
| REQ-149 | 환경 설정 | S | UI/UX 설계서 §3.7.1, §12.12, §9, REQ-126, REQ-138 | `core/preferences-model.js`, `views/preferences-modal.js`, `js/app.js`, `css/app.css`, `index.html` | TC-149 (`tests/preferences-model.test.js`, `tests/preferences-ui.test.js`) | 구현 완료 (v2.2) |

**상태 값 정의**: `초안` (명세만 작성) / `설계 완료` / `구현 완료` / `검증 완료`.
**요구사항 ID 체계**: `REQ-0xx` = 기능 요구사항(FR), `REQ-1xx` = 비기능 요구사항(NFR). 번호는 재사용하지 않으며, 폐기 시 상태만 `폐기`로 바꾼다.

---

## 8. 변경 이력

| 버전 | 날짜 | 내용 | 작성 |
| :--- | :--- | :--- | :--- |
| v0.1 | 2026-11-02 | 초안 작성 (요구사항 ID 체계 수립, 기능/비기능 목록, 추적 매트릭스) | Claude |
| v1.0 | 2026-11-02 | 사용자 승인 후 `docs/`로 승격 (파일명 `Requirement_Spec` 규칙 적용) | Claude |
| v2.1 개정 | 2026-11-11 | **REQ-149 신설, REQ-126·REQ-138 개정, REQ-018·129·144·146·147·148 보완**: 헤더의 효과음·다크 모드 버튼을 계정 메뉴의 환경 설정 모달로 이동(REQ-149). 학습 설정 아이콘을 `book-open` 으로. 북마크·오답 목록 API 가 `pos`·`phonetic` 을 싣고 복습함 행이 예문 대신 이를 보임. 플래시카드 북마크 버튼을 앞·뒷면에 둠. 퀴즈 출제 응답의 발음기호 비노출 정책은 유지 | Claude |
| v2.1 개정 | 2026-11-11 | **REQ-148 신설, REQ-125·REQ-137 개정**: 세션 카드 오른쪽 위 북마크 토글과 출제 응답의 `bookmarked` 필드를 추가. 해설 시트에서 표제어 듣기 버튼을 빼고(세션 헤더와 중복), 플래시카드 "알아요" 효과음을 뺌(퀴즈 정답음과 중복) | Claude |
| v2.1 개정 | 2026-11-10 | **REQ-146 신설, REQ-144 개정, REQ-145·Q4 정정**: 품사를 API(`VocabularyWordOut`·`SessionItemOut`·`SessionAnswerOut`, 퀴즈 출제 포함)와 화면(미리보기·퀴즈 문제·플래시카드 앞면·해설 시트)에 노출. 플래시카드는 앞면에 표제어·품사·발음기호, 뒷면은 뜻·예문만 (뒷면에서 표제어·발음기호 제거). 이전 "품사 비노출" 결정(REQ-145 ③) 폐기 | Claude |
| v2.1 개정 | 2026-11-10 | **기존 600단어 품사 채움(REQ-145·146 정정)**: 기존 3개 단어장(초급·중급·고급)의 600단어에 `pos` 를 채워 전체 1,000단어가 품사를 갖는다. 허용 품사에 `pronoun`(대명사)·`interjection`(감탄사) 추가(`hello`·`goodbye`·`what`·`who` 용). 이전 "기존 600단어는 품사 없음" 문구 폐기. 기존 3개 단어장의 `content_hash` 가 바뀌어 시작 시 UPDATE 되며 `word_id`·진행 기록은 불변 | Claude |
| v2.1 개정 | 2026-11-10 | **REQ-147 신설**: 퀴즈·플래시카드 문항 수와 오늘의 목표를 사용자별 설정(10·20·30, 기본 10)으로 바꿈. `users` 컬럼 3개 추가, `GET`·`PATCH /api/users/me/settings`, 세션 `count` 생략 시 설정 적용. 이전 "세션·목표 15 고정" 폐기 | Claude |
| v2.1 개정 | 2026-11-10 | **REQ-147 화면 정정**: 학습 설정 UI 를 홈 카드에서 계정 메뉴의 "학습 설정" 모달로 이동 (UI/UX 설계서 §3.7.1, §12.10). API·DB 변경 없음 | Claude |
| v2.1 개정 | 2026-11-10 | **REQ-125 개정**: 단어 미리보기 시트에서 예문 듣기 버튼 제거(표제어 듣기만 유지). 학습 세션·해설 시트·플래시카드의 예문 듣기는 그대로 | Claude |
| v2.1 개정 | 2026-11-10 | **REQ-145 신설, REQ-143 개정** (v2.2 카탈로그 확충, 이슈 #24): 시험 대비 핵심 200(`EXAM`)·실무 비즈니스 영단어 200(`BUSINESS`) 추가로 총 1,000단어. 신규 단어는 단일 단어에 6개 필드(품사 포함) 필수, 품사는 DB 저장 전용(API·화면 미노출), 기존 3개 단어장의 해시·`word_id` 불변. 탐색 칩 라벨 시험·비즈니스. 시험명 상표는 제목에 쓰지 않음 | Claude |
| v2.1 개정 | 2026-11-06 | **REQ-144 신설, REQ-141 개정, Q4 정정** (v2.2 발음기호): 표준 단어 600개에 미국식 IPA 를 싣고(저장은 슬래시 없는 문자열, 화면이 `/…/` 서식), 단어 목록·플래시카드 출제·채점 응답에 `phonetic` 추가, **퀴즈 출제 응답은 항상 null**. 해설 시트·플래시카드 뒷면·단어 시트에 표시하고 `aria-hidden` 처리. 데이터 출처 CMUdict(BSD 계열) 고지를 §10 에 추가. Q4 의 "발음기호 미사용" 문구를 정정 | Claude |
| v2.1 개정 | 2026-11-05 | **REQ-137·REQ-138 개정** (v2.2 사운드·콤보): 정답 효과음을 **세션 효과음**으로 확대. 큐 4종(정답 아르페지오·콤보 마일스톤 4음·퀴즈 오답 저음 드롭·세션 완료 팡파레), 오답음 허용(**기존 "오답에는 무음" 폐기**)·플래시카드 자가 평가는 무음, 마스터 게인 0.6, 완주+정답 1개 이상일 때만 팡파레, 콤보 뱃지와 "최대 콤보", 효과음 토글 아이콘 `bell-ring`/`bell-off`(REQ-138 명칭을 "효과음 음소거"로 변경). 나머지 요구사항 변경 없음 | Claude |
| v2.1 개정 | 2026-11-05 | **REQ-125 개정** (v2.2 TTS): 표제어에 더해 **예문** 발음 지원, 버튼 위치(세션 헤더·해설 시트·플래시카드 뒷면·단어 미리보기 시트), 보이스 자동 판별(en-US > en-GB > en-*, localService 우선), 속도 단어 0.9/문장 0.85, 재생 상태 표시, 정지 시점, 재생 불가 시 세션당 1회 토스트. 나머지 요구사항 변경 없음 | Claude |
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
| **신설** | REQ-140~143 (v2.2: REQ-144, 145, 146, 147) | 중앙 제공형 카탈로그 (REQ-144 발음기호, REQ-145 카탈로그 확충, REQ-146 품사 표시, REQ-147 학습 개수 설정) |
| **개정** | REQ-141 (v2.2), REQ-001, 003, 012, 014, 015, 016, 017, 018, 019, 122, 124, 125, 127, 129, 131, 132, 133, 134, 137 | 세션 러너·표준 콘텐츠 기준 |
| **유지** | REQ-002, 020~023, 101, 102, 104~121, 126, 138 | REQ-102~106 은 문구만 §5 에서 조정 |

---

## 10. 데이터 출처 및 라이선스 고지

| 자료 | 용도 | 고지 |
| :--- | :--- | :--- |
| CMU Pronouncing Dictionary (CMUdict) | 표준 단어 1,000개(기존 600 + 신규 400)의 미국식 발음기호(IPA) 시드 (REQ-144, REQ-145) | Copyright (C) 1993-2015 Carnegie Mellon University. All rights reserved. BSD 계열 라이선스에 따라 소스·바이너리 재배포 시 위 저작권 고지와 라이선스 조건·면책 문구를 유지한다. 원 발음(ARPAbet)을 IPA 로 변환했고, 미수록 단어와 동형이음 단어는 수기로 확정했다 (변환 도구와 600개 검수표: `ai-agent/claude/작업계획_261106_IPA_변환.py`, `ai-agent/claude/검토_261106_IPA_검수표.md`). |

> 라이선스 전문(조건·면책 문구)은 CMUdict 배포본의 LICENSE 를 따른다. 외부 재배포 시 해당 전문을 함께 싣는다.
