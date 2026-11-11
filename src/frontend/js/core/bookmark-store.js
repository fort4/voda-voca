/*
 * 2026-11-10 - voda-voca - 세션 북마크 저장소: 문항에서 초기 상태를 채우고, 낙관적으로 토글하며, 실패하면 되돌린다
 * 파일 위치: src/frontend/js/core/bookmark-store.js
 */

/**
 * 세션 화면 하나가 쓰는 저장소. 화면은 상태가 바뀔 때마다 다시 그려지므로 사용자가 바꾼 값은 여기에 남겨 두고,
 * seed 는 모르는 단어만 채운다 (서버가 출제 시점에 준 옛 값으로 되돌리지 않는다).
 * @param {{api: (path: string, options?: object) => Promise<any>}} deps 테스트에서 api 를 바꿔 끼운다
 */
export function createBookmarkStore({ api }) {
  /** @type {Map<number, boolean>} */
  const state = new Map();
  /** @type {Set<number>} 요청이 진행 중인 단어 */
  const pending = new Set();
  const listeners = new Set();

  const set = (wordId, on) => {
    state.set(wordId, on);
    listeners.forEach((listener) => listener(wordId, on));
  };

  return {
    /** @param {Array<{word_id: number, bookmarked?: boolean}>} items */
    seed(items) {
      for (const item of items) if (!state.has(item.word_id)) state.set(item.word_id, item.bookmarked === true);
    },
    isBookmarked: (wordId) => state.get(wordId) === true,
    isPending: (wordId) => pending.has(wordId),
    /**
     * 북마크를 뒤집는다. 응답을 기다리지 않고 새 상태를 먼저 보여 주고, 실패하면 되돌린 뒤 오류를 던진다.
     * 같은 단어의 요청이 진행 중이면 무시한다 (연타로 PUT/DELETE 가 엇갈리지 않게).
     * @returns {Promise<boolean>} 토글 뒤의 상태
     */
    async toggle(wordId) {
      const before = state.get(wordId) === true;
      if (pending.has(wordId)) return before;
      pending.add(wordId);
      set(wordId, !before);
      try {
        await api(`/bookmarks/${wordId}`, { method: before ? "DELETE" : "PUT" });
        return !before;
      } catch (error) {
        set(wordId, before);
        throw error;
      } finally {
        pending.delete(wordId);
      }
    },
    /** @returns {() => void} 구독 해제 */
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}
