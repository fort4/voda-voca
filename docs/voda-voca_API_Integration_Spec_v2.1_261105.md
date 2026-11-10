# API 연동 규격서 (API Integration Spec) v2.1

| 항목 | 내용 |
| :--- | :--- |
| 프로젝트 | voda-voca (보다보카) |
| 문서 종류 | API Integration Spec (프론트엔드·백엔드 계약) |
| 버전 / 상태 | v2.1 / **승인 (Approved)** — 중앙 제공형 단어장 + 세션 러너 반영 |
| 산출물 경로 | `docs/voda-voca_API_Integration_Spec_v2.1_261105.md` (이전 버전: `docs/old/voda-voca_API_Integration_Spec_v2.0_261102.md` 외 보관) |
| 작성일 | 2026-11-05 (v2.0: 2026-11-02) |
| 기준 | 백엔드 구현 (`src/backend/routers/*.py`, `src/backend/schemas/*.py`), 요구사항 명세 v2.1, 데이터 설계서 v2.1 |
| 대상 | 프론트엔드 (`src/frontend/js/`, Vanilla JS, 빌드 없음) |
| 공통 | 모든 경로는 `/api` 하위이며, 요청·응답 본문은 JSON(UTF-8)입니다. 시각은 UTC이고 `Z` 접미사가 붙습니다 (REQ-109). |

> **v2.1 요약**: 개인 단어장·단어·CSV·옛 플래시카드/퀴즈 API 는 **제거**되었습니다 (별도 410 응답 없이 경로 자체가 없음). 대신 읽기 전용 표준 단어장 카탈로그와 단일 학습 세션 러너 API 가 추가되었습니다. 이 문서의 필드와 상태 코드는 구현(`app.openapi()`)과 대조했습니다.

---

## 목차

1. 공통 규칙 (인증, 오류 본문, 페이징, 시각, 입력 제한)
2. 엔드포인트 목록 (16 + health)
3. 엔드포인트별 상세 (인증 · 표준 단어장 · 북마크 · 학습 세션 · 학습 지표 · 헬스체크)
4. HTTP 상태 코드 매핑
5. 프론트엔드 연동 설계 (인증 플로우, 401, fetch 래퍼, 429)
6. 학습 세션 규격 (정답 노출, 멱등, 만료, 오류 코드)
7. 제거된 엔드포인트
8. 결정 기록

---

## 1. 공통 규칙

### 1.1 인증
- 로그인 성공 시 서버가 `voda_session` 쿠키를 설정합니다 (`HttpOnly`, `SameSite=Lax`, 기본 수명 14일, `Secure`는 `.env`의 `COOKIE_SECURE`로 제어).
- 프론트엔드는 쿠키 값을 읽을 수 없습니다. 로그인 여부는 `GET /api/auth/me`로 확인합니다.
- 인증이 필요한 엔드포인트는 쿠키가 없거나 만료되었으면 **401**을 반환합니다.

### 1.2 오류 본문
| 출처 | 형태 | 예 |
| :--- | :--- | :--- |
| 애플리케이션 오류 (401, 404, 409, 400, 429) | `{"detail": "문자열"}` | `{"detail": "단어장을 찾을 수 없습니다."}` |
| 입력 검증 오류 (422, FastAPI 기본) | `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}` | 필드별 메시지 목록 |

- 학습 세션 API 의 일부 오류는 응답 헤더 **`X-Error-Code`** 에 문구와 무관한 코드를 싣습니다 (§6.3). 화면은 `detail` 문구가 아니라 이 값으로 분기합니다.
- 성공 응답 `204`는 본문이 없습니다.

### 1.3 페이징
| 엔드포인트 | 파라미터 | 기본 | 최대 |
| :--- | :--- | :---: | :---: |
| 표준 단어 목록 | `page` (≥1), `size` (1~200) | 1, **50** | size 200 |
| 북마크 목록 | `page` (≥1), `size` (1~100) | 1, 20 | size 100 |
| 오답 단어 목록 | `page` (≥1), `size` (1~100) | 1, 20 | size 100 |
| 학습 이력 | `limit` (1~100) | 100 | 100 |
| 표준 단어장 목록 | 페이징 없음 (전체 배열) | — | — |

페이징 응답은 공통으로 `{items, total, page, size}`를 반환합니다 (표준 단어 목록은 `vocabulary_id` 가 추가됨, 학습 이력은 `{items}`).

### 1.4 시각
- 모든 시각 필드(`created_at`, `bookmarked_at`, `wrong_at`, `expires_at`)는 `2026-11-02T05:30:00.123Z` 형식입니다.
- 화면 표시는 `Intl.DateTimeFormat('ko-KR', {timeZone: 'Asia/Seoul'})`로 변환합니다.

### 1.5 입력 제한
| 필드 | 제한 | 비고 |
| :--- | :--- | :--- |
| 비밀번호 | 최소 8자, 최대 **72바이트(UTF-8)** | 한글은 3바이트이므로 글자 수와 다를 수 있음 |
| 닉네임 | 2~30자 (공백 제거 후), 중복 불가 | 대소문자 무시 유일 (409) |
| 카탈로그 `category` | 최대 50자 | 필터 값 |
| 카탈로그 `level` | 1~5 | 범위 밖은 422 |
| 세션 `count` | 1~30 (기본 15) | 범위 밖은 422 |
| 세션 답 | `choice_index` 0~3, `known` boolean — **둘 중 정확히 하나** | 아니면 422 |

---

## 2. 엔드포인트 목록

| # | 메서드 | 경로 | 요구사항 | 인증 | 성공 | 주요 실패 |
| :-: | :--- | :--- | :--- | :-: | :-: | :--- |
| 1 | POST | `/api/auth/signup` | REQ-001, REQ-142 | — | 201 | 409, 422 |
| 2 | POST | `/api/auth/login` | REQ-001, REQ-121 | — | 200 | 401, **429**, 422 |
| 3 | POST | `/api/auth/logout` | REQ-002 | 선택 | 204 | — |
| 4 | GET | `/api/auth/me` | REQ-002 | 필수 | 200 | 401 |
| 4b | DELETE | `/api/auth/me` | REQ-122 | 필수 | 204 | 401 |
| 5 | GET | `/api/vocabularies` | REQ-140 | 필수 | 200 | 422, 401 |
| 6 | GET | `/api/vocabularies/{vocabulary_id}/words` | REQ-141 | 필수 | 200 | 404, 422, 401 |
| 7 | POST | `/api/users/me/active-vocabulary` | REQ-142 | 필수 | 200 | 404, 422, 401 |
| 8 | PUT | `/api/bookmarks/{word_id}` | REQ-017 | 필수 | 204 | 404, 401 |
| 9 | DELETE | `/api/bookmarks/{word_id}` | REQ-017 | 필수 | 204 | 401 |
| 10 | GET | `/api/bookmarks` | REQ-018 | 필수 | 200 | 422, 401 |
| 11 | POST | `/api/study/sessions` | REQ-012, 014, 019, 129 | 필수 | 201 | 400, 409, 422, 401 |
| 12 | POST | `/api/study/sessions/{session_id}/answer` | REQ-015, 016, 124 | 필수 | 200 | 400, 404, 409, 422, 401 |
| 13 | GET | `/api/study/stats` | REQ-131~133 | 필수 | 200 | 401 |
| 14 | GET | `/api/study/wrong-words` | REQ-129 | 필수 | 200 | 422, 401 |
| 15 | GET | `/api/study/logs` | REQ-016 | 필수 | 200 | 422, 401 |
| — | GET | `/health` | 운영 | — | 200 | 503 |

> 이 표는 `app.openapi()` 의 경로·메서드 집합과 일치합니다 (인증 5건, 표준 단어장 3건, 북마크 3건, 학습 5건 = 16건 + health).

---

## 3. 엔드포인트별 상세

### 3.1 인증

**#1 POST `/api/auth/signup`**
- 요청 본문: `{"nickname": string(2~30자, 공백 제거 후), "password": string(8자 이상, 72바이트 이하)}`. 이메일은 받지 않습니다 (v1.1).
- 응답 201: `UserOut` = `{"id": number, "nickname": string, "created_at": string}`
- 실패: 409 `{"detail": "이미 사용 중인 닉네임입니다."}`, 422 (형식 위반)
- 부가 효과: 가입 시 초급 표준 단어장(`beginner-200`)이 `active_vocabulary_id` 로 자동 지정됩니다 (REQ-142). 단어장·단어를 복사하지 않습니다.
- 프론트 처리: 성공 시 자동 로그인하지 않습니다. 로그인 화면으로 이동하고 성공 토스트를 띄웁니다 (2번 호출 필요).

**#2 POST `/api/auth/login`**
- 요청 본문: `{"nickname": string, "password": string}`
- 응답 200: `UserOut`과 함께 `Set-Cookie: voda_session=...`
- 실패:
  - 401 `{"detail": "닉네임 또는 비밀번호가 올바르지 않습니다."}`. 없는 닉네임도 401입니다 (422가 아님). 닉네임 대소문자는 구분하지 않습니다.
  - **429** `{"detail": "로그인 시도가 너무 많습니다. 잠시 후 다시 시도해 주세요."}` + `Retry-After: <초>`. 상세는 §5.4.
  - 422: 닉네임 또는 비밀번호가 비어 있을 때
- 주의: 429는 비밀번호가 맞아도 반환됩니다. 계정 차단 키는 닉네임(REQ-121)입니다. 프론트는 429 중에는 로그인 버튼을 막습니다.

**#3 POST `/api/auth/logout`**
- 본문 없음. 응답 204. 세션이 없어도 204입니다 (멱등).
- 프론트 처리: 응답과 무관하게 로컬 사용자 상태를 지우고 로그인 화면으로 이동합니다.

**#4 GET `/api/auth/me`**
- 응답 200: `UserOut`. 실패 401.
- 프론트 처리: 앱 시작 시 한 번 호출해 로그인 여부를 판단합니다.

**#4b DELETE `/api/auth/me`** (REQ-122, v1.1 신설)
- 본문 없음. 로그인한 사용자만 호출할 수 있습니다.
- 응답 204. 응답 헤더 `Set-Cookie: voda_session=""; Max-Age=0`으로 세션 쿠키를 만료시킵니다.
- 효과: 계정을 지우면 세션, 북마크, 학습 이력, 학습 진행도, 학습 세션이 DB의 `ON DELETE CASCADE`로 함께 영구 삭제됩니다. **표준 단어장·단어는 공용이라 삭제되지 않습니다.** 되돌릴 수 없습니다. 탈퇴한 닉네임은 다시 가입할 수 있습니다.
- 실패: 401 (쿠키가 없거나 만료됨). 아무것도 지우지 않습니다.
- 프론트 처리: 경고 확인 후 닉네임을 직접 입력받아 최종 확인합니다. 성공하면 세션 저장소를 비우고 로그인 화면으로 이동합니다.

### 3.2 표준 단어장 (읽기 전용, REQ-140~142)

표준 단어장은 서버 시드로만 바뀌며 생성·수정·삭제 API 가 없습니다.

**#5 GET `/api/vocabularies?category=&level=`**
- 쿼리: `category`(최대 50자, 선택), `level`(1~5, 선택). 정렬: `sort_order`, `id`.
- 응답 200: `VocabularyOut[]`
  ```json
  [{
    "id": 1, "slug": "beginner-200", "title": "초급 필수 영단어 200",
    "category": "ELEMENTARY", "level": 1, "description": "일상에서 가장 자주 쓰는 기초 어휘",
    "total_words": 200,
    "user_progress": {"studied_words": 52, "memorized_words": 14, "progress_rate": 26.0, "is_active": true}
  }]
  ```
- `studied_words` = `user_word_progress` 행이 있는 단어 수(한 번이라도 풀어 본 단어), `memorized_words` = 숙련 단어 수, `progress_rate` = `studied_words / total_words × 100`(소수 첫째 자리), `is_active` = 지금 학습 중인 단어장. 진행률은 단어장별 집계 한 번으로 구합니다 (N+1 없음).
- 프론트 처리: 탐색 화면의 카테고리·레벨 칩은 이 목록에서 만듭니다.
- **카테고리 값 (v2.2)**: `ELEMENTARY`, `SECONDARY`, `CSAT`, `EXAM`(시험 대비 핵심 200, `exam-core-200`), `BUSINESS`(실무 비즈니스 영단어 200, `business-practical-200`). 정렬은 `sort_order` 순(1~5)이고 `?category=EXAM` 처럼 거를 수 있습니다. 새 카테고리는 시드만으로 늘고 API 형태는 그대로입니다 (하위 호환).

**#6 GET `/api/vocabularies/{vocabulary_id}/words?page=&size=`**
- 응답 200: `{"vocabulary_id", "items": [{"word_id", "term", "meaning", "example": string|null, "example_meaning": string|null, "phonetic": string|null, "pos": string|null, "bookmarked": boolean}], "total", "page", "size"}`
- `phonetic` (`VocabularyWordOut`, v2.2): 슬래시 없는 미국식 IPA (예: `"ˈæpəl"`), 없으면 null. 화면이 `/…/` 를 입힙니다. 추가 필드이므로 하위 호환입니다.
- **`pos`(품사, `VocabularyWordOut`, v2.2, REQ-146)**: 영문 소문자 문자열(`noun`, `verb`, `adjective`, `adverb`, `preposition`, `conjunction`, `pronoun`, `interjection`) 또는 null. 시드 1,000단어는 모두 값이 있습니다. 화면이 한글 라벨을 입힙니다. 추가 필드이므로 하위 호환입니다.
- 정렬: `order_index`, `id`. `bookmarked` 는 요청한 사용자의 북마크 여부입니다.
- 실패: 404 (없는 단어장), 422 (`page`/`size` 범위)

**#7 POST `/api/users/me/active-vocabulary`**
- 요청: `{"vocabulary_id": number(>0)}`
- 응답 200: 그 단어장의 `VocabularyOut` (`user_progress.is_active = true`)
- **멱등**: 이미 활성인 단어장을 다시 보내도 200 입니다.
- 실패: 404 (없는 단어장), 422

### 3.3 북마크

**#8 PUT `/api/bookmarks/{word_id}`**
- 본문 없음. 응답 204. 이미 북마크되어 있어도 204입니다 (멱등).
- 실패: 404 (없는 표준 단어)

**#9 DELETE `/api/bookmarks/{word_id}`**
- 본문 없음. 응답 204. 북마크가 없어도 204입니다 (멱등).

**#10 GET `/api/bookmarks?page=&size=`**
- 응답 200: `{"items": [{"word_id", "vocabulary_id", "vocabulary_title", "term", "meaning", "example", "example_meaning", "bookmarked_at"}], "total", "page", "size"}`
- 정렬: 최근 북마크순 (`created_at`, `id` 내림차순)

### 3.4 학습 세션 (세션 러너, REQ-012, 014~016, 124, 129)

**#11 POST `/api/study/sessions`** — 세션 출제 (부수효과가 있으므로 `GET` 이 아닙니다)
- 요청 (`SessionCreate`, 모두 선택):
  | 필드 | 값 | 기본 | 설명 |
  | :--- | :--- | :--- | :--- |
  | `mode` | `"quiz"` \| `"flashcard"` | `quiz` | 4지선다 / 알아요·헷갈려요 |
  | `count` | 1~30 | 15 | 요청 문항 수. 가용 단어가 적으면 줄어듭니다 |
  | `include_memorized` | boolean | false | true 면 숙련 단어도 출제 (`source=all` 에만 적용) |
  | `source` | `"all"` \| `"bookmarks"` \| `"wrong"` | `all` | 아래 표 |
- `source` 별 동작:
  | source | 출제 풀 | 활성 단어장 | 비고 |
  | :--- | :--- | :--- | :--- |
  | `all` | 활성 단어장. **워터폴**: 오답 풀 최대 `floor(0.3×N)`, 기학습 복습 `floor(0.1×N)` 선확보, 나머지 미학습(`order_index` 순), 모자라면 복습 충원. 출제 후 섞음 | 사용. 활성 단어장이 없으면 첫 단어장을 활성으로 저장 | 응답 `vocabulary_id` 에 값 |
  | `bookmarks` | 내 북마크 단어에서 무작위 | 바꾸지 않음 | `vocabulary_id` = null, 제목 "북마크 복습" |
  | `wrong` | 단어별 마지막 결과가 오답인 단어에서 무작위 | 바꾸지 않음 | `vocabulary_id` = null, 제목 "오답 복습". 숙련 제외 없음 |
- 응답 201 (`SessionOut`):
  ```json
  {
    "session_id": 123, "mode": "quiz", "vocabulary_id": 1, "vocabulary_title": "초급 필수 영단어 200",
    "total_questions": 15, "expires_at": "2026-11-05T09:30:00.123Z",
    "composition": {"wrong": 4, "review": 1, "unseen": 10},
    "items": [{
      "question_id": 0, "word_id": 105, "term": "postpone",
      "context": "The meeting was postponed until next Monday.",
      "options": ["연기하다", "가속하다", "조사하다", "설립하다"],
      "meaning": null, "example_meaning": null, "phonetic": null, "pos": "noun"
    }]
  }
  ```
- **정답 비노출 규격 (퀴즈)**: 출제 응답 문항에는 `question_id`, `word_id`, `term`, `context`(예문, 없으면 null), `options` 만 있습니다. **`correct_index` 필드는 출제 응답 스키마에 없고, `meaning`, `example_meaning` 은 퀴즈에서 항상 null 입니다.** 정답과 해설은 `#12` 채점 응답에서만 공개됩니다.
- **플래시카드**: 정답 개념이 없으므로 `options` = null 이고, 뒷면 정보 `meaning`, `example_meaning` 과 앞면에 보일 `phonetic` 을 문항에 함께 싣습니다 (`context` = 예문).
- **`phonetic` (`SessionItemOut`, v2.2, REQ-144)**: 문자열 또는 null. **퀴즈 세션의 출제 응답에서는 단어에 발음기호가 있어도 항상 null** 입니다 (채점 전 정보 최소화. 서버가 값을 내려보내지 않아 클라이언트 실수로 새지 않게 합니다). 플래시카드는 뒷면용으로 값을 싣습니다. 진행 중인 옛 세션(스냅샷에 키 없음)은 null 입니다. 추가 필드이므로 하위 호환입니다.
- **`pos` (`SessionItemOut`, v2.2, REQ-146)**: 문자열 또는 null. 발음기호와 달리 **퀴즈 출제 응답에도 값을 싣습니다** (문제 화면에 표제어와 함께 보이는 정보이며 정답을 알려 주지 않습니다). 채점 응답(`SessionAnswerOut.pos`)에도 같은 값이 있고 멱등 재전송에서도 동일합니다. 진행 중인 옛 세션(스냅샷에 키 없음)은 null 입니다.
- `expires_at`: 이 시각 이후에는 새 답을 기록할 수 없습니다. **답을 기록할 때마다 30분씩 뒤로 밀립니다.** 밀리초 정밀도로 맞춰 재전송 응답과 항상 같습니다.
- 실패:
  - 400: 퀴즈인데 단어가 4개 미만 (`"퀴즈는 단어가 4개 이상 있어야 시작할 수 있습니다."` 등), 오답 보기를 만들 수 없음
  - 409 `X-Error-Code: NO_WORDS_TO_STUDY`: 출제할 단어가 없음 (`all` 이면 `"학습할 단어가 없습니다. 숙련한 단어를 포함해 볼까요?"`, 복습이면 `"복습할 단어가 없습니다."`)
  - 409 `X-Error-Code: NO_VOCABULARY`: 학습할 단어장이 없음
  - 422: 필드 범위·값 위반
  - 401

**#12 POST `/api/study/sessions/{session_id}/answer`** — 문항별 즉시 채점
- 요청 (`SessionAnswerIn`): `{"question_id": number(≥0), "choice_index"?: 0~3 | "known"?: boolean}`. 퀴즈 세션은 `choice_index`, 플래시카드 세션은 `known`(true=알아요, false=헷갈려요)으로 답합니다. **둘 중 정확히 하나만** 보내야 합니다 (아니면 422, 세션 모드와 맞지 않으면 400).
- 응답 200 (`SessionAnswerOut`):
  ```json
  {
    "question_id": 0, "is_correct": true, "correct_index": 0, "selected_index": 0, "known": null,
    "term": "postpone", "meaning": "연기하다",
    "example": "The meeting was postponed until next Monday.", "example_meaning": "회의는 다음 주 월요일로 연기되었다.",
    "phonetic": "pəstˈpoʊn", "pos": "verb",
    "progress": {"correct_count": 2, "wrong_count": 0, "consecutive_correct_count": 2, "is_memorized": false},
    "answered": 1, "total": 15, "is_finished": false,
    "expires_at": "2026-11-05T09:30:00.123Z"
  }
  ```
- 퀴즈는 `correct_index`·`selected_index` 를 채우고 `known` 은 null, 플래시카드는 반대입니다 (`correct_index` null). `meaning`, `example`, `example_meaning`, `phonetic` 은 **해설**이며 이 응답에서 처음 공개됩니다. `phonetic` (`SessionAnswerOut`, v2.2)은 퀴즈·플래시카드 모두 값을 싣고, 없으면 null 입니다. 같은 답을 다시 보내는 멱등 응답에서도 동일합니다.
- **효과 (한 트랜잭션)**: `study_logs` 1행 INSERT + `user_word_progress` 갱신 + 세션의 `answers` 갱신 + 마감 30분 연장. **숙련도 전이**: 정답이면 `consecutive_correct_count += 1` (3 이상이면 `is_memorized = true`), 오답이면 연속 0, 숙련 해제. 응답의 `progress` 는 갱신된 값입니다.
- **멱등**: 같은 문항에 **같은 답**을 다시 보내면 이력을 늘리지 않고 이전과 **동일한 본문**을 돌려줍니다 (200). 다른 답으로 바꾸려 하면 409 `QUIZ_ANSWER_LOCKED`.
- `is_finished`: 모든 문항에 답하면 true 이며 세션이 끝납니다.
- 실패: 404 (없는 세션, 타인 세션), 400 `QUIZ_ANSWER_INVALID` (알 수 없는 문항, 모드와 맞지 않는 답 형식), 400 `QUIZ_EXPIRED`, 409 `QUIZ_ALREADY_SUBMITTED` / `QUIZ_ANSWER_LOCKED` / `QUIZ_WORD_MISSING`, 422, 401. 오류 코드는 §6.3.

### 3.5 학습 지표

**#13 GET `/api/study/stats`** (`StudyStatsOut`)
- 응답 200:
  ```json
  {
    "answered": 120, "correct": 96, "accuracy": 80.0, "streak_days": 5,
    "weekly": [{"date": "2026-11-05", "label": "목", "count": 15, "is_today": true}],
    "total_words": 1000,
    "vocabulary_progress": [{"vocabulary_id": 1, "word_count": 200, "learned_words": 52, "percent": 26}],
    "wrong_word_count": 9
  }
  ```
- **전체 이력 기준**이며 최근 N건 제한이 없습니다 (REQ-131). `accuracy` 는 푼 문항이 없으면 null. `streak_days` 는 한국 날짜 기준이며 오늘 기록이 없으면 어제부터 셉니다. `weekly` 는 오늘을 포함한 최근 7일(오래된 날부터)이고 `count` 는 그날 푼 **고유 단어 수**입니다. `vocabulary_progress[].learned_words` 는 **한 번이라도 맞힌** 단어 수이며(#5 의 `studied_words` 와 기준이 다릅니다), `wrong_word_count` 는 #14 의 `total` 과 같은 규칙입니다.

**#14 GET `/api/study/wrong-words?page=&size=`**
- 응답 200: `{"items": [{"word_id", "vocabulary_id", "vocabulary_title", "term", "meaning", "example", "example_meaning", "bookmarked", "wrong_at"}], "total", "page", "size"}`
- 오답 판정: 단어별 **가장 최근 결과가 오답**인 단어 (기간 제한 없음). 맞히면 대상에서 빠집니다. 정렬: 최근에 틀린 순.

**#15 GET `/api/study/logs?limit=`**
- 응답 200: `{"items": [{"word_id", "vocabulary_id", "term", "is_correct": boolean, "created_at"}]}`
- 최신순, 본인 기록만. 한 번에 최대 100건이며 통계의 근거는 아닙니다 (#13 이 서버 집계).

### 3.6 헬스체크

**GET `/health`** (인증 없음)
- 200: `{"status": "ok", "db": "connected"}` / 503: `{"status": "error", "db": "disconnected"}`
- 프론트는 쓰지 않습니다. 운영 점검용입니다.

---

## 4. HTTP 상태 코드 매핑 (프론트 처리 규칙)

| 코드 | 의미 | 프론트 처리 |
| :-: | :--- | :--- |
| 200, 201 | 성공 (본문 있음) | 결과를 상태에 반영 |
| 204 | 성공 (본문 없음) | 낙관적 갱신 확정 또는 목록 제거 |
| 400 | 요청 내용 오류 (퀴즈 4개 미만, 알 수 없는 문항, 만료) | 메시지를 그대로 표시. 만료는 `X-Error-Code: QUIZ_EXPIRED` 로 구분해 세션 종료 안내 |
| 401 | 인증 필요 또는 세션 만료 | §5.2 정책 적용 (로그인 화면 이동). 로그인 요청 자체의 401은 제외 |
| 404 | 대상 없음 또는 접근 불가 (없는 단어장·단어·세션, 타인 세션) | "찾을 수 없습니다" 안내. 타인 자원과 구분하지 않음 |
| 409 | 충돌 (닉네임 중복, 답 변경 시도, 이미 끝난 세션, 단어 삭제, 출제할 단어 없음) | `X-Error-Code` 로 분기 (§6.3). 닉네임 중복은 입력 칸 아래에 안내 |
| 422 | 입력 검증 실패 | `loc` 마지막 요소로 필드를 찾아 해당 입력 아래에 표시 |
| **429** | 로그인 시도 과다 | §5.4 정책 적용 (Retry-After 카운트다운, 버튼 비활성) |
| 503 | 서버 또는 DB 이상 | 재시도 안내. 서버 오류 화면 |
| 0 (네트워크) | 연결 실패, 시간 초과 | 오프라인 안내 + 재시도 버튼 |

---

## 5. 프론트엔드 연동 설계

### 5.1 세션 쿠키 인증 플로우
1. 앱 시작 → `GET /api/auth/me` 호출 (`credentials: 'include'`).
   - 200이면 사용자 상태를 저장하고 홈(`#/`)으로 갑니다.
   - 401이면 `#/login`으로 갑니다.
2. 로그인 → `POST /api/auth/login`
   - 200이면 브라우저가 `voda_session`을 저장합니다. 프론트는 응답 본문의 `UserOut`만 메모리에 둡니다.
   - 쿠키는 JS로 읽지 않습니다. `localStorage`나 `sessionStorage`에 토큰을 저장하지 않습니다.
3. 이후 모든 요청은 같은 출처이므로 쿠키가 자동으로 붙습니다. 래퍼는 `credentials: 'include'`를 명시합니다.
4. 로그아웃 → `POST /api/auth/logout`
   - 응답과 무관하게 메모리의 사용자 상태를 지우고 `#/login`으로 갑니다.

**배포 전제**: 프론트와 API를 같은 출처(같은 호스트·포트)에서 제공합니다. 다른 출처라면 CORS와 `SameSite`가 달라지므로 이 문서를 다시 검토해야 합니다.

### 5.2 401 수신 시 세션 만료 처리 정책
- 로그인 요청(`POST /api/auth/login`)의 401은 "자격 증명 오류"이므로 세션 만료로 취급하지 않습니다. 오류 메시지를 폼에 표시합니다.
- 그 밖의 요청에서 401을 받으면 세션이 만료된 것으로 봅니다.
  1. 진행 중인 요청을 모두 취소합니다 (AbortController).
  2. 메모리의 사용자 상태를 지웁니다.
  3. 현재 경로를 `next` 파라미터로 저장하고 `#/login?next=...`로 이동합니다.
  4. 토스트로 "세션이 만료되었습니다. 다시 로그인해 주세요."를 띄웁니다.
- 로그인 성공 후에는 `next` 경로로 돌아갑니다. `next`는 같은 앱 내부 해시 경로만 허용하고, 외부 URL이면 무시합니다 (열린 리다이렉트 방지).
- 학습 세션 중 401이면 진행 중이던 세션을 이어 가지 않습니다. 이미 기록된 답은 서버에 저장되어 있으며, 로그인 후 새 세션을 시작합니다.

### 5.3 공통 fetch 래퍼

```javascript
/**
 * @typedef {Object} ApiOptions
 * @property {'GET'|'POST'|'PUT'|'PATCH'|'DELETE'} [method]
 * @property {Record<string, string|number|boolean|null|undefined>} [query]
 * @property {unknown} [body]
 * @property {AbortSignal} [signal]
 */

/**
 * 백엔드 API 호출 래퍼.
 * - credentials: 'include' 로 쿠키를 보낸다.
 * - 본문은 JSON, 204 는 null 을 반환한다.
 * - 실패는 ApiError 로 던진다 (status, detail, retryAfter).
 */
export async function api(path, opts = {}) { /* 설계 */ }
```

| 항목 | 규칙 |
| :--- | :--- |
| 기본 호출 | `fetch(url, {credentials: 'include', headers, body, signal})` |
| 쿼리 | `undefined` 와 `null` 값은 제외. `boolean` 은 `true`/`false` 문자열 |
| 응답 파싱 | `204` 는 `null`. 그 밖에는 `response.json()` |
| 오류 본문 | `detail` 이 문자열이면 그대로, 배열이면 `[{field, message}]` 로 변환 (`loc` 마지막 요소를 `field`로) |
| 네트워크 오류 | `TypeError` 는 `ApiError(status=0)` 으로 감싼다 |
| 시간 초과 | 기본 15초. `AbortSignal.timeout` 과 호출자의 `signal` 을 `AbortSignal.any` 로 합친다 |
| 401 공통 처리 | 래퍼가 `onUnauthorized` 콜백을 호출하고 §5.2 정책을 실행한다 (로그인 경로 제외) |
| 429 공통 처리 | 래퍼는 `ApiError.retryAfter`(초, 정수)만 채운다. UI 차단은 로그인 화면이 담당한다 (§5.4) |
| 취소 | `AbortError` 는 사용자에게 오류로 보여주지 않고 조용히 무시한다 |

**ApiError 모양**
```javascript
/** @typedef {{status: number, detail: string, fields?: Array<{field: string, message: string}>, retryAfter?: number}} ApiErrorShape */
```

### 5.4 429 수신 시 UI 블로킹 (로그인 전용)
- 429를 받으면 로그인 제출 버튼을 비활성화하고, `Retry-After` 초를 카운트다운으로 보여 줍니다.
- 카운트다운: "약 N초 후 다시 시도할 수 있습니다." 0초가 되면 버튼을 다시 활성화합니다.
- 카운트다운 중에는 입력 칸을 수정할 수 있습니다. 서버는 비밀번호와 무관하게 차단하므로, 입력을 바꿔도 제출은 막힙니다.
- 페이지를 새로고침해도 카운트다운은 서버 기준이므로, 새로고침 후 다시 제출하면 429를 한 번 더 받아 같은 상태로 돌아옵니다. 로컬 저장으로 우회하지 않습니다.
- 다른 엔드포인트는 429를 반환하지 않으므로 이 블로킹은 로그인 폼에만 둡니다.

### 5.5 (삭제됨)
v2.0 의 표제어 검색 디바운스 규칙은 검색 API 가 없어져 삭제되었습니다.

---

## 6. 학습 세션 규격

### 6.1 라이프사이클

```
POST /api/study/sessions  ─►  items[0..N-1]
   │  (프론트: 1문항 집중 뷰)
   ├─ 퀴즈:       POST .../answer {question_id, choice_index} ─► 정오 + 해설 + progress
   └─ 플래시카드: POST .../answer {question_id, known}        ─► 해설 + progress
모든 문항 응답 ─► is_finished = true ─► 결과 화면 (프론트가 응답을 모아 구성)
```

- 별도의 "제출" API 는 없습니다. 답은 문항마다 서버에 저장되므로 중간에 앱을 닫아도 푼 답은 이력에 남습니다.
- 결과 화면(정답 수, 정답률, 오답 노트)은 프론트가 `#12` 응답들로 구성합니다.

### 6.2 정답 노출 원칙 (REQ-014, REQ-124, D16)
| 단계 | 퀴즈 | 플래시카드 |
| :--- | :--- | :--- |
| 출제 (`#11`) | `term`, `context`, `options`, **`pos`**. 정답·뜻·예문 뜻·**발음기호(`phonetic` 항상 null)** 비노출 | `term`, `context`, **`meaning`, `example_meaning`, `phonetic`, `pos` 포함** (정답 없음) |
| 채점 (`#12`) | `is_correct`, `correct_index`, 해설(`meaning`, `example`, `example_meaning`, `phonetic`, `pos`), `progress` | 해설(`phonetic`·`pos` 포함), `progress` |

### 6.3 오류 코드 (`X-Error-Code` 헤더)
| 코드 | 상태 | 의미 | 프론트 처리 |
| :--- | :-: | :--- | :--- |
| `NO_WORDS_TO_STUDY` | 409 | 출제할 단어 없음 | 숙련 포함 제안 또는 안내 |
| `NO_VOCABULARY` | 409 | 학습할 단어장 없음 | 탐색 화면으로 안내 |
| `QUIZ_EXPIRED` | 400 | 마지막 응답 후 30분 경과 | 세션 종료 안내 (푼 답은 저장됨) |
| `QUIZ_ANSWER_INVALID` | 400 | 알 수 없는 문항, 답 형식이 모드와 다름 | 오류 안내 |
| `QUIZ_ANSWER_LOCKED` | 409 | 이미 답한 문항을 다른 답으로 바꾸려 함 | 이전 답 유지 |
| `QUIZ_ALREADY_SUBMITTED` | 409 | 이미 끝난 세션 | 결과 화면으로 이동 |
| `QUIZ_WORD_MISSING` | 409 | 문항 단어가 삭제됨 | "다시 시작해 주세요" 안내 |

### 6.4 세션 타이머
- 전역 카운트다운은 두지 않습니다. 마감(`expires_at`)은 답을 기록할 때마다 30분씩 밀리는 **유휴 제한**이며, 만료되면 `QUIZ_EXPIRED` 로 알려 줍니다.

---

## 7. 제거된 엔드포인트 (v2.1)

경로 자체가 없으며 호출하면 404(또는 405)입니다. 별도 안내 응답은 두지 않습니다. 회귀 방지 테스트: `test_legacy_study_removed.py`, `test_drop_legacy_tables.py`.

| 제거된 경로 | 대체 |
| :--- | :--- |
| `/api/wordbooks/*` (생성·목록·수정·삭제, 프리셋) | `GET /api/vocabularies`, `POST /api/users/me/active-vocabulary` |
| `/api/wordbooks/{id}/words/*`, `/api/words/*` (CRUD, 일괄 등록, 검색) | `GET /api/vocabularies/{id}/words` |
| `GET /api/study/flashcards` | `POST /api/study/sessions` (`mode=flashcard`) |
| `POST /api/study/quiz/sessions` | `POST /api/study/sessions` (`mode=quiz`, `source=all|bookmarks|wrong`) |
| `POST /api/study/quiz/sessions/{id}/answers`, `.../submit`, `GET .../{id}` | `POST /api/study/sessions/{id}/answer` |

---

## 8. 결정 기록

| # | 항목 | 내용 | 상태 |
| :-: | :--- | :--- | :--- |
| 1 | 출제 응답 정답 노출 | **v2.1 재결정: 출제 응답에서 정답·해설 비노출**, 채점 응답에서만 공개 (REQ-124, 데이터 설계 D16). v1.1 의 "출제 응답에 `correct_index` 포함"은 폐기 | 확정 |
| 2 | 퀴즈 타이머 | **v2.1 대체**: 세션 전체 카운트다운 폐지. 마감은 답마다 30분 연장되는 유휴 제한 | 확정 |
| 3 | 일괄 등록 409 `conflict_term` | **폐기** (일괄 등록 API 삭제) | 폐기 |
| 4 | 퀴즈 결과 복원 | **v2.1 대체**: 결과는 프론트가 채점 응답으로 구성. 서버에 답이 문항마다 저장됨 | 확정 |
| 5 | 퀴즈 중 단어 삭제 | 답 기록 시 409 `QUIZ_WORD_MISSING` — 안내 후 새 세션 시작 | 확정 |
| 6 | 오답 복습 원천 | **v2.1 대체**: 단어별 마지막 결과가 오답 (`source=wrong`, `GET /api/study/wrong-words`) | 확정 |
| 7 | 추천 1,000제 프리셋 | **폐기** | 폐기 |
| 8 | 학습 통계 | **v2.1 대체**: `GET /api/study/stats` 서버 집계 (최근 100건 제한 없음, 데이터 설계 D15 대체) | 확정 |
| 9 | 세션 생성 메서드 | `POST` 사용 (출제는 세션 행을 만드는 부수효과) | 확정 |
| 10 | 활성 단어장 변경 | `POST /api/users/me/active-vocabulary`, 멱등 | 확정 |

---

## 변경 이력

| 버전 | 날짜 | 내용 | 작성 |
| :--- | :--- | :--- | :--- |
| v2.1 개정 | 2026-11-06 | 발음기호 `phonetic` 필드 추가 (REQ-144, v2.2). `VocabularyWordOut`(#6 단어 목록), `SessionItemOut`(#11 출제), `SessionAnswerOut`(#12 채점)에 `string\|null` 추가. **퀴즈 출제 응답은 항상 null**, 플래시카드 출제·채점 응답은 값 (§6.2 표 갱신). 옛 세션은 null. 추가 필드라 하위 호환 | Claude |
| v2.1 개정 | 2026-11-10 | 품사 `pos` 필드 추가 (REQ-146, v2.2): `VocabularyWordOut`, `SessionItemOut`(**퀴즈 출제 포함**), `SessionAnswerOut` 에 `string\|null`. 이전 "pos 비노출" 문구 폐기. 플래시카드 `phonetic` 은 앞면용으로 용도 표기 정정. 추가 필드라 하위 호환 | Claude |
| v2.1 개정 | 2026-11-10 | `pos` 값 정정: 기존 600단어도 값이 채워져 전체 1,000단어가 값을 가짐. 값 집합에 `pronoun`·`interjection` 추가. 필드·타입 변경 없음 | Claude |
| v2.1 개정 | 2026-11-10 | 카탈로그 확충 반영 (REQ-145, v2.2). 카테고리 값 `EXAM`·`BUSINESS` 와 단어장 2개(총 5개·1,000단어), 통계 예시 `total_words` 1000. **API 스키마 변경 없음** — `pos` 는 응답에 노출하지 않음을 명시. 하위 호환 | Claude |
| v2.1 | 2026-11-05 | 중앙 제공형 단어장 전환 반영. `/api/wordbooks/*`, `/api/words/*`, `/api/study/flashcards`, `/api/study/quiz/*` 제거. `GET /api/vocabularies`, `GET /api/vocabularies/{id}/words`, `POST /api/users/me/active-vocabulary`, `POST /api/study/sessions`(source: all/bookmarks/wrong), `POST /api/study/sessions/{id}/answer`, `GET /api/study/wrong-words`, `GET /api/study/stats` 추가. 출제 응답 정답 비노출·채점 응답 공개 규격, 멱등 재전송, 숙련도 전이, `X-Error-Code` 표 명시. 요구사항 명세 v2.1, 데이터 설계 v2.1 과 정합 | Claude |
| v2.0 | 2026-11-02 | `example_meaning`, 학습 로그 `wordbook_id` 등 (`docs/old/voda-voca_API_Integration_Spec_v2.0_261102.md`) | Claude |
| v1.2 이하 | 2026-11-02 | `docs/old/` 보관본 참조 | Claude |
