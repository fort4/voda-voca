# API 연동 규격서 (API Integration Spec) v1.1

| 항목 | 내용 |
| :--- | :--- |
| 프로젝트 | voda-voca (보다보카) |
| 문서 종류 | API Integration Spec (프론트엔드·백엔드 계약) |
| 버전 / 상태 | v1.1 / **승인 (Approved)** |
| 산출물 경로 | `docs/voda-voca_API_Integration_Spec_v1.1_261102.md` (이전 버전: `docs/old/voda-voca_API_Integration_Spec_v1.0_261102.md`) |
| 작성일 | 2026-11-02 (v1.1: 닉네임 기반 인증, 회원 탈퇴 API, 퀴즈 출제 응답의 정답·해설 필드, 즉각 피드백 반영) |
| 기준 | 백엔드 구현 (`src/backend/routers/*.py`, `src/backend/schemas/*.py`), 요구사항 명세 v1.3, 데이터 설계서 v1.2 |
| 대상 | 프론트엔드 (`src/frontend/js/`, Vanilla JS, 빌드 없음) |
| 공통 | 모든 경로는 `/api` 하위이며, 요청·응답 본문은 JSON(UTF-8)입니다. 시각은 UTC이고 `Z` 접미사가 붙습니다 (REQ-109). |

---

## 목차

1. 공통 규칙 (인증, 오류 본문, 페이징, 시각, 입력 제한)
2. 엔드포인트 목록 (21 + health)
3. 엔드포인트별 상세 (인증 · 단어장 · 단어 · 북마크 · 학습 · 헬스체크)
4. HTTP 상태 코드 매핑 (프론트엔드 처리 규칙)
5. 프론트엔드 연동 설계
   - 5.1 세션 쿠키 인증 플로우 (`credentials: 'include'`)
   - 5.2 401 수신 시 세션 만료 처리 정책
   - 5.3 공통 fetch 래퍼
   - 5.4 429 수신 시 UI 차단 (Retry-After)
   - 5.5 표제어 검색 디바운스(300ms)와 AbortController
6. 퀴즈 결과 화면과 세션 타이머 규격 (확정 결정 반영)
7. 결정 필요 사항

---

## 1. 공통 규칙

### 1.1 인증
- 로그인 성공 시 서버가 `voda_session` 쿠키를 설정합니다 (`HttpOnly`, `SameSite=Lax`, 기본 수명 14일, `Secure`는 `.env`의 `COOKIE_SECURE`로 제어).
- 프론트엔드는 쿠키 값을 읽을 수 없습니다. 로그인 여부는 `GET /api/auth/me`로 확인합니다.
- 인증이 필요한 엔드포인트는 쿠키가 없거나 만료되었으면 **401**을 반환합니다.

### 1.2 오류 본문
백엔드는 두 가지 형태의 본문을 반환하므로, 래퍼는 둘 다 처리해야 합니다.

| 출처 | 형태 | 예 |
| :--- | :--- | :--- |
| 애플리케이션 오류 (401, 404, 409, 400, 429) | `{"detail": "문자열"}` | `{"detail": "단어장을 찾을 수 없습니다."}` |
| 입력 검증 오류 (422, FastAPI 기본) | `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}` | 필드별 메시지 목록 |

- 일괄 등록의 409 본문은 `{"detail": string, "conflict_term": string|null}`입니다. `conflict_term`은 기존 단어와 겹친 요청 표제어입니다 (§3.3 #10b).
- 성공 응답 `204`는 본문이 없습니다.
- 메시지는 서버가 한국어로 작성한 것을 그대로 사용할 수 있습니다. 422는 `loc` 마지막 요소로 필드를 찾아 해당 입력 아래에 표시합니다.

### 1.3 페이징
| 엔드포인트 | 파라미터 | 기본 | 최대 |
| :--- | :--- | :---: | :---: |
| 단어장 목록 | `page` (≥1), `size` (1~100) | 1, 20 | size 100 |
| 단어 목록 | `page` (≥1), `size` (1~100) | 1, 20 | size 100 |
| 북마크 목록 | `page` (≥1), `size` (1~100) | 1, 20 | size 100 |
| 플래시카드 | `limit` (1~500) | 100 | 500 |
| 학습 이력 | `limit` (1~100) | 100 | 100 |

페이징 응답은 공통으로 `{items, total, page, size}`를 반환합니다 (플래시카드는 `{items, total}`, 학습 이력은 `{items}`).

### 1.4 시각
- 모든 시각 필드(`created_at`, `updated_at`, `bookmarked_at`, `expires_at`)는 `2026-11-02T05:30:00.123Z` 형식입니다.
- 화면 표시는 `Intl.DateTimeFormat('ko-KR', {timeZone: 'Asia/Seoul'})`로 변환합니다.

### 1.5 입력 제한 (서버 검증과 같은 값을 클라이언트에서도 검사)
| 필드 | 제한 | 비고 |
| :--- | :--- | :--- |
| 비밀번호 | 최소 8자, 최대 **72바이트(UTF-8)** | 한글은 3바이트이므로 글자 수와 다를 수 있음 |
| 닉네임 | 2~30자 (공백 제거 후), 중복 불가 | 대소문자 무시 유일 (409) |
| 단어장 이름 | 1~50자, 공백만 불가 | 같은 사용자 내 중복 불가 (409) |
| 단어장 설명 | 0~200자 | |
| 표제어 | 1~100자, 공백만 불가 | 같은 단어장 내 중복 불가 (409) |
| 뜻 | 1~200자, 공백만 불가 | |
| 예문 | 0~500자 | 빈 문자열은 `null`로 저장 |
| 검색어 `q` | 최대 100자 | 앞뒤 공백 제거 |

---

## 2. 엔드포인트 목록

| # | 메서드 | 경로 | 요구사항 | 인증 | 성공 | 주요 실패 |
| :-: | :--- | :--- | :--- | :-: | :-: | :--- |
| 1 | POST | `/api/auth/signup` | REQ-001, REQ-123 | — | 201 | 409, 422 |
| 2 | POST | `/api/auth/login` | REQ-001, REQ-121 | — | 200 | 401, **429**, 422 |
| 3 | POST | `/api/auth/logout` | REQ-002 | 선택 | 204 | — |
| 4 | GET | `/api/auth/me` | REQ-002 | 필수 | 200 | 401 |
| 4b | DELETE | `/api/auth/me` | REQ-122 | 필수 | 204 | 401 |
| 5 | POST | `/api/wordbooks` | REQ-004 | 필수 | 201 | 409, 422, 401 |
| 6 | GET | `/api/wordbooks` | REQ-005 | 필수 | 200 | 422, 401 |
| 7 | GET | `/api/wordbooks/{wordbook_id}` | REQ-006 | 필수 | 200 | 404, 401 |
| 8 | PATCH | `/api/wordbooks/{wordbook_id}` | REQ-006 | 필수 | 200 | 404, 409, 422, 401 |
| 9 | DELETE | `/api/wordbooks/{wordbook_id}` | REQ-007 | 필수 | 204 | 404, 401 |
| 10 | POST | `/api/wordbooks/{wordbook_id}/words` | REQ-008 | 필수 | 201 | 404, 409, 422, 401 |
| 10b | POST | `/api/wordbooks/{wordbook_id}/words/bulk` | REQ-008 (일괄 등록) | 필수 | 201 | 404, 409, 422, 401 |
| 11 | GET | `/api/wordbooks/{wordbook_id}/words` | REQ-009 | 필수 | 200 | 404, 422, 401 |
| 12 | GET | `/api/wordbooks/{wordbook_id}/words/{word_id}` | REQ-010 | 필수 | 200 | 404, 401 |
| 13 | PATCH | `/api/wordbooks/{wordbook_id}/words/{word_id}` | REQ-010 | 필수 | 200 | 404, 409, 422, 401 |
| 14 | DELETE | `/api/wordbooks/{wordbook_id}/words/{word_id}` | REQ-011 | 필수 | 204 | 404, 401 |
| 15 | PUT | `/api/bookmarks/{word_id}` | REQ-017 | 필수 | 204 | 404, 401 |
| 16 | DELETE | `/api/bookmarks/{word_id}` | REQ-017 | 필수 | 204 | 401 |
| 17 | GET | `/api/bookmarks` | REQ-018 | 필수 | 200 | 422, 401 |
| 18 | GET | `/api/study/flashcards` | REQ-012, 013, 019 | 필수 | 200 | 404, 422, 401 |
| 19 | POST | `/api/study/quiz/sessions` | REQ-014, 019 | 필수 | 201 | 400, 404, 422, 401 |
| 20 | POST | `/api/study/quiz/sessions/{session_id}/submit` | REQ-015, 016 | 필수 | 200 | 400, 404, 409, 422, 401 |
| 21 | GET | `/api/study/logs` | REQ-016 | 필수 | 200 | 422, 401 |
| — | GET | `/health` | 운영 | — | 200 | 503 |

> **참고**: 초기 요청의 "백엔드 16종"과 실제 구현 수가 달랐습니다. 일괄 등록(10b)과 회원 탈퇴(4b)를 포함해 실제는 **API 23종과 health 1종**입니다. 이 문서는 실제 구현을 기준으로 작성했습니다.

---

## 3. 엔드포인트별 상세

### 3.1 인증

**#1 POST `/api/auth/signup`**
- 요청 본문: `{"nickname": string(2~30자, 공백 제거 후), "password": string(8자 이상, 72바이트 이하)}`. 이메일은 받지 않습니다 (v1.1).
- 응답 201: `UserOut` = `{"id": number, "nickname": string, "created_at": string}`
- 실패: 409 `{"detail": "이미 사용 중인 닉네임입니다."}`, 422 (형식 위반)
- 부가 효과: 가입이 끝나면 기본 단어장 3종(초/중/고 200제)이 같은 트랜잭션에서 만들어집니다 (REQ-123). 어느 하나라도 실패하면 계정도 생기지 않습니다.
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
- 효과: 계정을 지우면 세션, 단어장, 단어, 북마크, 학습 이력, 퀴즈 세션이 DB의 `ON DELETE CASCADE`로 함께 영구 삭제됩니다. 되돌릴 수 없습니다. 탈퇴한 닉네임은 다시 가입할 수 있습니다.
- 실패: 401 (쿠키가 없거나 만료됨). 아무것도 지우지 않습니다.
- 프론트 처리: 경고 확인 후 닉네임을 직접 입력받아 최종 확인합니다. 성공하면 세션 저장소를 비우고 로그인 화면으로 이동합니다.

### 3.2 단어장

**#5 POST `/api/wordbooks`**
- 요청: `{"name": string(1~50자), "description": string|null(0~200자)}`
- 응답 201: `WordbookOut` = `{"id", "name", "description": string|null, "created_at", "updated_at"}`
- 실패: 409 `{"detail": "..."}` (같은 이름 존재), 422

**#6 GET `/api/wordbooks?page=&size=`**
- 응답 200: `{"items": WordbookOut[], "total": number, "page": number, "size": number}`
- 정렬: 최근 수정순 (`updated_at` 내림차순)

**#7 GET `/api/wordbooks/{wordbook_id}`**
- 응답 200: `WordbookOut`. 실패 404 (타인 단어장과 없는 ID는 같은 404).

**#8 PATCH `/api/wordbooks/{wordbook_id}`**
- 요청: `{"name"?: string, "description"?: string|null}`. 보낸 필드만 바뀝니다.
- 응답 200: `WordbookOut`. 실패: 404, 409, 422 (`name`을 `null`로 보내면 422)

**#9 DELETE `/api/wordbooks/{wordbook_id}`**
- 응답 204. 단어, 북마크, 학습 이력, 퀴즈 세션이 함께 삭제됩니다 (REQ-007). 실패 404.
- 프론트 처리: SweetAlert2 확인 모달을 먼저 띄웁니다 (REQ-007).

### 3.3 단어

**#10 POST `/api/wordbooks/{wordbook_id}/words`**
- 요청: `{"term": string(1~100), "meaning": string(1~200), "example": string|null(0~500)}`
- 응답 201: `WordOut` = `{"id", "wordbook_id", "term", "meaning", "example": string|null, "created_at", "updated_at", "bookmarked": boolean}`
- 실패: 404 (단어장), 409 (같은 단어장에 같은 표제어), 422

**#10b POST `/api/wordbooks/{wordbook_id}/words/bulk`** (REQ-008, 일괄 등록)
- 요청 본문: `{"items": [{"term": string(1~100), "meaning": string(1~200), "example": string|null(0~500)}]}`
  - `items`는 **1~100건**입니다. 항목별 제한은 #10과 같습니다.
  - 요청 안에서 표제어가 겹치면 422입니다. 비교는 대소문자와 악센트를 무시합니다 (`Apple`과 `apple`은 겹침).
- 응답 201: `{"items": WordOut[], "count": number}`. 입력 순서대로 반환하며, 모든 `bookmarked`는 `false`입니다.
- **전부 성공 또는 전부 실패 (All-or-Nothing)**: 한 건이라도 실패하면 아무 단어도 저장되지 않습니다. 실패 후 같은 요청을 다시 보내도 됩니다.
- 실패:
  - **422**: `items`가 0건이거나 101건 이상, 항목 필드 위반, 요청 안 표제어 중복. 본문은 FastAPI 검증 형식입니다.
    ```json
    {"detail": [{"type": "value_error", "loc": ["body"], "msg": "Value error, 요청 안에 같은 표제어가 있습니다: Apple", "input": "..."}]}
    ```
    - 항목 필드 오류는 `loc`가 `["body", "items", <인덱스>, "<필드>"]`입니다. 프론트는 이 인덱스로 해당 행을 강조합니다.
    - 요청 안 중복은 `loc`가 `["body"]`이므로 행을 특정할 수 없습니다. 중복된 표제어 목록을 `msg`에서 읽어 안내합니다.
  - **409**: 기존 단어와 표제어가 겹친 경우입니다. 본문은 다음과 같습니다.
    ```json
    {"detail": "같은 단어장에 이미 있는 표제어가 포함되어 있어 전체 등록을 취소했습니다.", "conflict_term": "Apple"}
    ```
    - `conflict_term`은 **요청 항목 중 기존 단어와 겹친 첫 표제어**입니다 (요청 순서 기준). 요청한 표기 그대로이며, 기존 단어의 표기가 아닙니다. 예: 기존 `apple`, 요청 `Apple` → `"Apple"`.
    - 찾지 못한 경우(동시 요청으로 기존 단어가 바뀐 드문 경우)는 `null`입니다. 프론트는 `null`이면 행을 강조하지 않고 상단 배너만 보입니다.
  - **404**: 단어장이 없거나 타인 소유입니다. 두 경우의 본문은 같습니다.
  - **401**: 로그인 필요.
  - 400은 이 엔드포인트에서 쓰지 않습니다. 형식 오류는 모두 422입니다.
- 입력 형식(CSV·TSV)은 프론트엔드가 파싱합니다. 서버는 `WordBulkCreate` JSON만 받습니다.
- 프론트 처리: 전송 전에 클라이언트에서 같은 규칙(100건, 중복, 글자 수)을 먼저 검사합니다 (UI/UX 설계서 §3.8). 서버 422는 방어용입니다.

**#11 GET `/api/wordbooks/{wordbook_id}/words?q=&page=&size=`**
- 응답 200: `{"items": WordOut[], "total", "page", "size"}`
- 정렬: 표제어 오름차순. `q`는 **표제어 접두사** 검색입니다 (뜻 검색은 1차 제외, F4).
- 빈 `q`는 전체 목록입니다.
- 실패: 404, 422 (`q`가 100자 초과)

**#12 GET `/api/wordbooks/{wordbook_id}/words/{word_id}`**
- 응답 200: `WordOut`. 실패 404 (단어장 소속이 아니거나 없음).

**#13 PATCH `/api/wordbooks/{wordbook_id}/words/{word_id}`**
- 요청: `{"term"?, "meaning"?, "example"?}`. `term`과 `meaning`은 `null`로 보낼 수 없고, `example`은 `null`로 지울 수 있습니다.
- 응답 200: `WordOut`. 실패 404, 409, 422.

**#14 DELETE `/api/wordbooks/{wordbook_id}/words/{word_id}`**
- 응답 204. 북마크와 학습 이력이 함께 삭제됩니다 (REQ-011). 실패 404.
- 주의: 퀴즈 진행 중 이 단어가 삭제되면 해당 퀴즈 제출은 409가 됩니다 (§3.5).

### 3.4 북마크

**#15 PUT `/api/bookmarks/{word_id}`**
- 본문 없음. 응답 204. 이미 북마크되어 있어도 204입니다 (멱등).
- 실패: 404 (타인 단어이거나 없는 단어)

**#16 DELETE `/api/bookmarks/{word_id}`**
- 본문 없음. 응답 204. 북마크가 없어도 204입니다 (멱등).

**#17 GET `/api/bookmarks?page=&size=`**
- 응답 200: `{"items": [{"word_id", "wordbook_id", "wordbook_name", "term", "meaning", "example", "bookmarked_at"}], "total", "page", "size"}`
- 정렬: 최근 북마크순 (`bookmarked_at` 내림차순)

### 3.5 학습

**#18 GET `/api/study/flashcards?wordbook_id=&bookmarked=&shuffle=&limit=`**
- `wordbook_id` 또는 `bookmarked=true` 중 하나 이상이 필요합니다. 둘 다 없으면 422입니다.
- 응답 200: `{"items": [{"word_id", "wordbook_id", "term", "meaning", "example", "bookmarked"}], "total": number}`
- `total`은 `limit`과 무관한 전체 개수입니다.
- `shuffle=true`면 무작위 순서입니다. 셔플 해제 시 프론트가 표제어 순으로 되돌립니다 (REQ-013).
- 실패: 404 (타인 단어장), 422

**#19 POST `/api/study/quiz/sessions`**
- 요청: `{"wordbook_id": number}` **또는** `{"bookmarks": true}` 중 정확히 하나. 여기에 `"count"?: number(1~50, 기본 10)`.
- 응답 201:
  ```json
  {
    "session_id": 123,
    "expires_at": "2026-11-02T06:00:00.000Z",
    "questions": [
      {"question_id": 0, "term": "apple", "choices": ["사과", "배", "포도", "바나나"], "correct_index": 0, "example": "I eat an apple every morning."}
    ]
  }
  ```
- 문항마다 정답 인덱스(`correct_index`, 0~3)와 해설 예문(`example`, 없으면 `null`)을 포함합니다 (v1.1, 즉각 피드백 REQ-124). 문항 수는 `min(count, 가용 단어 수)`입니다.
- 실패:
  - 400: 원천 단어가 4개 미만이거나 오답 보기를 만들 수 없음 (`{"detail": "퀴즈는 단어가 4개 이상 있어야 시작할 수 있습니다."}`)
  - 404: 단어장 없음 / 타인 단어장
  - 422: 두 출처를 함께 보내거나 둘 다 없음, `count` 범위 위반

**#20 POST `/api/study/quiz/sessions/{session_id}/submit`**
- 요청: `{"answers": [{"question_id": number(≥0), "choice_index": number(0~3)}]}`. 모든 문항에 정확히 한 번씩 답해야 합니다.
- 응답 200:
  ```json
  {
    "session_id": 123,
    "total": 10,
    "correct_count": 7,
    "accuracy": 70.0,
    "wrong_items": [
      {"word_id": 5, "term": "banana", "correct_meaning": "바나나", "selected_meaning": "배"}
    ]
  }
  ```
- 실패:
  - 400: 만료(30분 경과), 답안 누락·중복·알 수 없는 문항
  - 404: 세션 없음 / 타인 세션
  - 409: 이미 제출됨, 또는 문항 단어가 삭제되어 제출할 수 없음
  - 422: `choice_index`가 0~3 범위 밖
- 주의: 제출은 한 번만 성공합니다. 실패한 요청(400)은 세션을 소모하지 않으므로 답을 고쳐 다시 제출할 수 있습니다. 409 중 "단어 삭제"는 세션을 다시 만들어야 합니다.
- 결과 화면 한계: 응답의 `wrong_items`에는 **틀린 문항만** 있습니다. 전체 문항 비교와 새로고침 복원은 프론트엔드 `sessionStorage` 캐싱으로 처리합니다 (§6, 확정 결정 2). API 변경은 없습니다.

**#21 GET `/api/study/logs?limit=`**
- 응답 200: `{"items": [{"word_id", "term", "is_correct": boolean, "created_at"}]}`
- 정렬: 최신순. 본인 기록만 반환합니다.

### 3.6 헬스체크

**GET `/health`** (인증 없음)
- 200: `{"status": "ok", "db": "connected"}`
- 503: `{"status": "error", "db": "disconnected"}`
- 프론트는 이 엔드포인트를 쓰지 않습니다. 운영 점검용입니다.

---

## 4. HTTP 상태 코드 매핑 (프론트 처리 규칙)

| 코드 | 의미 | 프론트 처리 |
| :-: | :--- | :--- |
| 200, 201 | 성공 (본문 있음) | 결과를 상태에 반영 |
| 204 | 성공 (본문 없음) | 낙관적 갱신 확정 또는 목록 제거 |
| 400 | 요청 내용 오류 (퀴즈 조건, 제출 답안, 만료) | 메시지를 그대로 표시. 만료는 퀴즈 종료 화면으로 이동. 일괄 등록에서는 쓰지 않음 (422) |
| 401 | 인증 필요 또는 세션 만료 | §5.2 정책 적용 (로그인 화면 이동). 로그인 요청 자체의 401은 제외 |
| 404 | 대상 없음 또는 접근 불가 | "찾을 수 없습니다" 빈 화면. 타인 자원과 구분하지 않음 |
| 409 | 충돌 (중복 이름·표제어, 이미 제출, 단어 삭제) | 입력 칸 아래 또는 모달로 안내. 일괄 등록 409는 모달을 유지하고 전체 취소를 안내. 제출 충돌은 결과 화면으로 이동 |
| 422 | 입력 검증 실패 | `loc` 마지막 요소로 필드를 찾아 해당 입력 아래에 표시. 일괄 등록은 `loc`의 인덱스로 행을 강조 (§3.3 #10b) |
| **429** | 로그인 시도 과다 | §5.4 정책 적용 (Retry-After 카운트다운, 버튼 비활성) |
| 503 | 서버 또는 DB 이상 | 재시도 안내. 서버 오류 화면 |
| 0 (네트워크) | 연결 실패, 시간 초과 | 오프라인 안내 + 재시도 버튼 |

---

## 5. 프론트엔드 연동 설계

### 5.1 세션 쿠키 인증 플로우
1. 앱 시작 → `GET /api/auth/me` 호출 (`credentials: 'include'`).
   - 200이면 사용자 상태를 저장하고 `#/wordbooks`로 갑니다.
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
- 퀴즈 진행 중 401이면 답안을 `sessionStorage`에 임시 보관하지 않습니다. 세션이 복구되어도 퀴즈 세션은 서버에서 이미 만료 또는 소유권 문제가 될 수 있기 때문입니다. 퀴즈는 처음부터 다시 시작합니다.

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

### 5.5 표제어 검색: 디바운스 300ms와 요청 취소
- 입력 이벤트마다 요청하지 않습니다. 마지막 입력 후 **300ms**가 지나면 검색합니다 (trailing debounce).
- 새 검색을 보내기 전에 이전 요청의 `AbortController`를 `abort()`합니다. 늦게 도착한 옛 응답이 화면을 덮어쓰지 않게 합니다.
- 검색어가 바뀌면 페이지를 1로 되돌리고 `total`을 다시 받습니다.
- 빈 검색어는 전체 목록입니다. 앞뒤 공백은 보내기 전에 제거합니다.
- 검색 중에는 목록을 지우지 않고 이전 결과를 흐리게 표시합니다 (깜빡임 방지).
- 화면을 떠나면 진행 중인 검색 요청을 취소합니다.

---

## 6. 퀴즈 결과 화면과 세션 타이머 규격 (확정 결정 반영)

| 결정 | 확정 내용 |
| :-: | :--- |
| 채점 방식 | **즉각 피드백 (v1.1 재결정, REQ-124).** 보기를 고르는 즉시 정오와 정답 뜻, 해설 예문을 보여 줍니다. 최종 기록은 제출 API가 일괄 저장합니다 (REQ-015). 정답 인덱스는 출제 응답에 포함됩니다. |
| 타이머 기준 | **세션 만료 시점(`expires_at`, 출제 후 30분) 기준 전체 잔여 시간**을 글로벌 카운트다운으로 표시합니다. 문항별 제한 시간은 없습니다. |

**세션 타이머 규격**
- 출발점: 출제 응답 `expires_at`(UTC). 잔여 시간은 `expires_at - 현재 서버 시각`입니다.
- 클라이언트 시계 오차 보정: 출제 응답의 `Date` 헤더로 `offset = 서버 시각 - 클라이언트 시각`을 계산하고, 잔여 시간은 `expires_at - (Date.now() + offset)`으로 구합니다. 기기 시계가 틀려도 잔여 시간이 맞습니다.
- 갱신: 1초마다 다시 계산합니다. 탭이 백그라운드로 가서 타이머가 늦어져도, 값은 항상 시각 차이로 계산하므로 틀리지 않습니다.
- 0이 되면 답안 선택과 제출을 막고 "시간이 지났습니다" 상태로 바꿉니다. 제출 요청은 보내지 않습니다 (보내면 400이 됩니다).
- 제출 요청의 400(만료)은 서버 판정이 우선합니다. 클라이언트 타이머가 조금 늦게 끝나도 서버 응답을 따릅니다.

**결과 화면 데이터 규격 (확정: 결정 2, sessionStorage 캐싱)**
- 제출 응답의 `wrong_items`로 **오답 노트**를 그립니다 (표제어, 정답 뜻, 선택한 뜻).
- **문항별 비교**(선지 4개의 정답·오답·선택 표시)와 **새로고침 복원**은 프론트엔드가 `sessionStorage`에 캐싱해 처리합니다. 백엔드 변경은 없습니다.
  - 캐시 키: `voda.quizResult.<session_id>` (세션 ID별로 하나)
  - 저장 시점: 제출이 200으로 성공한 직후. 그 시점의 메모리 상태(출제 응답의 문항·선지, 내가 고른 선지, 제출 응답)로 만듭니다.
  - 저장 값: 세션 ID, 제출 응답 전체, 문항별 `{question_id, term, choices, selected_index, correct_index}`, 저장 시각.
  - `correct_index`는 맞힌 문항은 `selected_index`, 틀린 문항은 `wrong_items.correct_meaning`과 같은 선지의 인덱스입니다. 제출이 끝난 뒤이므로 정답 인덱스를 클라이언트에 두어도 채점 규칙을 해치지 않습니다.
- 범위: `sessionStorage`는 **같은 탭 안에서만** 유지됩니다. 탭을 닫거나 다른 기기에서 열면 결과를 볼 수 없습니다. 이 경우 안내 문구를 씁니다 (UI/UX 설계서 §3.5).

---

## 7. 결정 기록 (확정 및 미결)

| # | 항목 | 내용 | 추천 |
| :-: | :--- | :--- | :--- |
| 1 | 퀴즈 즉각 채점 | **재결정 (2026-11-02): 즉각 피드백 도입** (REQ-124). 출제 응답에 `correct_index`와 `example` 포함. 기록 신뢰도 위험은 Data Design D11에서 수용 | 확정 (v1.1) |
| 2 | 퀴즈 타이머 | **확정 (2026-11-02): 세션 만료 시점 기준 전체 잔여 시간 글로벌 카운트다운** (§6). | 확정 |
| 3 | 409 행 식별 | **확정 (2026-11-02): 409 본문에 `conflict_term` 추가** (§3.3 #10b). 요청 항목 중 기존 단어와 겹친 첫 표제어를 요청 표기 그대로 돌려줍니다. 구현 완료 (`963d9d2`). | 확정 |
| 4 | 퀴즈 결과 복원 | **확정 (2026-11-02): 프론트엔드 `sessionStorage` 캐싱, API 변경 없음** (§6). 같은 탭 안에서만 복원되며, 다른 탭·기기에서는 결과를 볼 수 없습니다. | 확정 |
| 5 | 퀴즈 중 단어 삭제 | 제출 시 409가 됩니다. 프론트는 결과 화면이 아니라 "퀴즈를 다시 시작하세요" 안내로 처리합니다. | 안내 후 퀴즈 목록으로 이동 |
| 6 | 일괄 등록 입력 포맷 | **확정 (2026-11-02): CSV 및 TSV 지원. 파싱과 유효성 검증은 프론트엔드가 전담.** 백엔드에는 `WordBulkCreate` JSON만 전달합니다 (UI/UX 설계서 §3.8). | 확정 |

---

## 변경 이력

| 버전 | 날짜 | 내용 | 작성 |
| :--- | :--- | :--- | :--- |
| v1.1 | 2026-11-02 | 닉네임 기반 가입·로그인 (이메일 제거, §1.5, §3.1), 회원 탈퇴 `DELETE /api/auth/me` 추가 (§3.1 #4b), 퀴즈 출제 응답에 `correct_index`, `example` 추가 (§3.5 #19), 채점 방식 재결정 (§6, §7-1). 정식 릴리즈 v1.0 반영 | Claude |
| v1.0 | 2026-11-02 | 일괄 등록 API, 409 `conflict_term`, 결과 캐싱, CSV/TSV 클라이언트 파싱 (정식 승격) | Claude |
