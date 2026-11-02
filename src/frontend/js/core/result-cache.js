/*
 * 2026-11-02 - voda-voca - 퀴즈 결과 sessionStorage 캐시: 세션 ID 키, 저장 실패·깨진 값 허용, 로그아웃 시 정리 (확정 결정 2)
 * 파일 위치: src/frontend/js/core/result-cache.js
 */

export const RESULT_KEY_PREFIX = "voda.quizResult.";

/** @param {number} sessionId @returns {string} */
export function resultKey(sessionId) {
  return `${RESULT_KEY_PREFIX}${sessionId}`;
}

/**
 * 결과를 저장한다. 저장소를 쓸 수 없으면 false 를 돌려주고 예외를 던지지 않는다.
 * @param {Storage|null|undefined} storage
 * @param {number} sessionId
 * @param {object} record
 * @returns {boolean}
 */
export function saveQuizResult(storage, sessionId, record) {
  if (!storage) return false;
  try {
    storage.setItem(resultKey(sessionId), JSON.stringify({ ...record, savedAt: record.savedAt ?? new Date().toISOString() }));
    return true;
  } catch {
    return false;
  }
}

/**
 * 결과를 읽는다. 없거나 깨진 값이면 null.
 * @param {Storage|null|undefined} storage
 * @param {number} sessionId
 * @returns {object|null}
 */
export function loadQuizResult(storage, sessionId) {
  if (!storage) return null;
  try {
    const raw = storage.getItem(resultKey(sessionId));
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" && Array.isArray(parsed.items) ? parsed : null;
  } catch {
    return null;
  }
}

/**
 * 이 탭의 퀴즈 결과 캐시를 모두 지운다 (로그아웃 시).
 * @param {Storage|null|undefined} storage
 * @returns {number} 지운 개수
 */
export function clearQuizResults(storage) {
  if (!storage) return 0;
  try {
    const keys = [];
    for (let i = 0; i < storage.length; i += 1) {
      const key = storage.key(i);
      if (key && key.startsWith(RESULT_KEY_PREFIX)) keys.push(key);
    }
    keys.forEach((key) => storage.removeItem(key));
    return keys.length;
  } catch {
    return 0;
  }
}
