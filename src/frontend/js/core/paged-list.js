/*
 * 2026-11-27 - voda-voca - 쪽 단위 목록: 한 쪽씩 받아 목록을 바꿔 넣는 상태 관리와 이전·다음 버튼 모델 (DOM 없는 순수 로직, REQ-018, REQ-129)
 * 파일 위치: src/frontend/js/core/paged-list.js
 */

/** 복습함 목록 한 쪽의 단어 수 */
export const REVIEW_PAGE_SIZE = 10;

/** 전체 개수의 쪽 수. 비어 있어도 1쪽이다. */
function pageCountOf(total, size) {
  return Math.max(1, Math.ceil(total / size));
}

/**
 * 이전·다음 줄의 상태. 한 쪽에 다 들어가면 보이지 않는다.
 * @param {{page: number, total: number, size?: number, busy?: boolean}} state
 */
export function pagerModel({ page, total, size = REVIEW_PAGE_SIZE, busy = false }) {
  const count = pageCountOf(total, size);
  return {
    show: total > size,
    label: `${page} / ${count}`,
    prevDisabled: busy || page <= 1,
    nextDisabled: busy || page >= count,
  };
}

/**
 * 받은 첫 쪽에서 시작해 요청한 쪽으로 바꿔 넣는다.
 * 불러오는 동안은 기존 목록을 유지하고 다른 요청을 받지 않아 응답이 뒤섞이지 않는다.
 * dispose() 뒤에 도착한 응답과 실패는 알리지 않는다.
 *
 * @template T
 * @param {{
 *   first: {items: T[], total: number},
 *   fetchPage: (page: number) => Promise<{items: T[], total: number}>,
 *   onChange: (change: {moved: boolean, totalChanged: boolean}) => void,
 *   onError: (error: unknown) => void,
 *   size?: number,
 * }} options
 */
export function createPagedList({ first, fetchPage, onChange, onError, size = REVIEW_PAGE_SIZE }) {
  let state = { items: first.items, total: first.total, page: 1, busy: false };
  let disposed = false;

  /** 요청한 쪽을 받는다. 그 사이 목록이 줄어 없는 쪽이 됐으면 마지막 쪽을 다시 받는다. */
  async function load(page) {
    const result = await fetchPage(page);
    const last = pageCountOf(result.total, size);
    if (result.items.length > 0 || page <= last) return { ...result, page };
    return { ...(await fetchPage(last)), page: last };
  }

  return {
    get state() {
      return state;
    },

    /** @param {number} page */
    async goTo(page) {
      if (disposed || state.busy || page === state.page || page < 1 || page > pageCountOf(state.total, size)) return;
      const before = state;
      state = { ...state, busy: true };
      onChange({ moved: false, totalChanged: false });
      try {
        const next = await load(page);
        if (disposed) return;
        state = { items: next.items, total: next.total, page: next.page, busy: false };
        onChange({ moved: next.page !== before.page, totalChanged: next.total !== before.total });
      } catch (error) {
        if (disposed) return;
        state = before;
        onChange({ moved: false, totalChanged: false });
        onError(error);
      }
    },

    dispose() {
      disposed = true;
    },
  };
}
