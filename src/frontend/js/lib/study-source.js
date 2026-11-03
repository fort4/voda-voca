/*
 * 2026-11-02 - voda-voca - 학습 출처 해석: 단어장 또는 북마크 중 하나. URL 쿼리와 API 파라미터를 한곳에서 만든다 (REQ-019)
 * 파일 위치: src/frontend/js/lib/study-source.js
 */

const TRUE_VALUES = new Set(["1", "true"]);

/**
 * 라우트 쿼리에서 출처를 읽는다. wordbook_id 가 있으면 단어장, bookmarks 또는 bookmarked 가 참이면 북마크.
 * 둘 다 없거나 잘못되면 null.
 * @param {Record<string, string>} query
 * @returns {{kind: "wordbook", wordbookId: number} | {kind: "bookmarks"} | null}
 */
export function parseStudySource(query) {
  if (query.wordbook_id !== undefined) {
    const id = Number(query.wordbook_id);
    return Number.isInteger(id) && id > 0 ? { kind: "wordbook", wordbookId: id } : null;
  }
  if (TRUE_VALUES.has(query.bookmarks) || TRUE_VALUES.has(query.bookmarked)) return { kind: "bookmarks" };
  if (TRUE_VALUES.has(query.wrong)) return { kind: "wrong" };
  return null;
}

/** @param {{kind: string, wordbookId?: number}} source @returns {Record<string, string>} 라우트 쿼리 */
export function sourceRouteQuery(source) {
  if (source.kind === "wordbook") return { wordbook_id: String(source.wordbookId) };
  if (source.kind === "wrong") return { wrong: "1" };
  return { bookmarks: "1" };
}

/**
 * 서버 세션의 출처(source, wordbook_id)로 '다시 풀기' 라우트 쿼리를 만든다 (결과 화면을 서버 데이터로 그릴 때 쓴다).
 * @param {{source: string, wordbook_id: number|null}} session
 * @returns {Record<string, string>}
 */
export function routeQueryFromSession(session) {
  if (session.source === "wordbook") return { wordbook_id: String(session.wordbook_id) };
  if (session.source === "wrong") return { wrong: "1" };
  return { bookmarks: "1" };
}

/** 플래시카드 API 쿼리 (GET /api/study/flashcards) */
export function sourceFlashcardQuery(source) {
  return source.kind === "wordbook" ? { wordbook_id: source.wordbookId } : { bookmarked: true };
}

/** 퀴즈 출제 본문 일부 (POST /api/study/quiz/sessions) */
export function sourceQuizBody(source) {
  if (source.kind === "wordbook") return { wordbook_id: source.wordbookId };
  if (source.kind === "wrong") return { wrong_only: true };
  return { bookmarks: true };
}

/**
 * 원천 단어 수를 세는 요청 경로. size=1 로 받아 total 만 쓴다.
 * @param {{kind: string, wordbookId?: number}} source
 * @returns {{path: string, query: Record<string, number>}}
 */
export function sourceCountRequest(source) {
  return source.kind === "wordbook"
    ? { path: `/wordbooks/${source.wordbookId}/words`, query: { page: 1, size: 1 } }
    : { path: "/bookmarks", query: { page: 1, size: 1 } };
}

/** 원천 단어가 퀴즈 최소 개수(4개) 이상인지. */
export const QUIZ_MIN_WORDS = 4;

/** @param {number} total @returns {boolean} */
export function canStartQuiz(total) {
  return total >= QUIZ_MIN_WORDS;
}
