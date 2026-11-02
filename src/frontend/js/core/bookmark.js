/*
 * 2026-11-02 - voda-voca - 북마크 토글 큐: 즉시 UI 전환(낙관적), 요청 중 재호출은 최종 상태만 남기고 한 번 더 맞춤, 실패 시 되돌림 (REQ-017)
 * 파일 위치: src/frontend/js/core/bookmark.js
 */

/**
 * @param {{
 *   send: (wordId: number, bookmarked: boolean) => Promise<unknown>,
 *   onChange: (wordId: number, bookmarked: boolean, pending: boolean) => void,
 *   onError: (wordId: number, error: unknown, attempted: boolean) => void
 * }} opts
 */
export function createBookmarkQueue({ send, onChange, onError }) {
  /** @type {Map<number, {server: boolean, desired: boolean, inFlight: boolean}>} */
  const entries = new Map();

  /**
   * 서버에서 읽은 초기 상태를 등록한다. 이미 있는 항목은 진행 중 상태를 덮어쓰지 않는다.
   * @param {number} wordId
   * @param {boolean} bookmarked
   */
  function init(wordId, bookmarked) {
    if (!entries.has(wordId)) entries.set(wordId, { server: bookmarked, desired: bookmarked, inFlight: false });
  }

  /**
   * 별을 누른다. 화면은 바로 바뀌고, 서버 요청은 진행 중이 아니면 바로 보낸다.
   * @param {number} wordId
   * @returns {boolean} 전환 후 상태
   */
  function toggle(wordId) {
    const entry = entries.get(wordId);
    if (!entry) throw new Error(`북마크 상태가 등록되지 않은 단어입니다: ${wordId}`);
    entry.desired = !entry.desired;
    onChange(wordId, entry.desired, true);
    if (!entry.inFlight) drain(wordId);
    return entry.desired;
  }

  /** 요청을 순서대로 보낸다. 보내는 동안 바뀐 최종 상태가 서버와 다르면 한 번 더 보낸다. */
  async function drain(wordId) {
    const entry = entries.get(wordId);
    entry.inFlight = true;
    try {
      while (entry.desired !== entry.server) {
        const target = entry.desired;
        try {
          await send(wordId, target);
          entry.server = target;
        } catch (error) {
          entry.desired = entry.server; // 실패: 서버 상태로 되돌린다
          onChange(wordId, entry.server, false);
          onError(wordId, error, target);
          return;
        }
      }
      onChange(wordId, entry.server, false);
    } finally {
      entry.inFlight = false;
    }
  }

  return {
    init,
    toggle,
    /** @param {number} wordId @returns {{bookmarked: boolean, pending: boolean}|null} */
    getState(wordId) {
      const entry = entries.get(wordId);
      if (!entry) return null;
      return { bookmarked: entry.desired, pending: entry.inFlight };
    },
    /** 테스트와 화면 전환에서 상태를 비운다. */
    clear() {
      entries.clear();
    },
  };
}
