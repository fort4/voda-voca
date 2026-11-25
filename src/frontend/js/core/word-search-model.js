/*
 * 2026-11-26 - voda-voca - 단어 목록 검색 모델: 검색어 정리, 페이지 이어 붙이기, 늦게 온 응답 버리기, 하단 안내 (DOM 없는 순수 로직, REQ-163)
 * 파일 위치: src/frontend/js/core/word-search-model.js
 */

/** 서버가 받는 검색어 길이 한도 (표제어 길이와 같다). */
export const SEARCH_MAX_LENGTH = 100;
/** 입력이 이만큼 멈추면 검색한다. */
export const SEARCH_DEBOUNCE_MS = 300;

/** @param {unknown} raw @returns {string} 앞뒤 공백을 없애고 한도에서 자른 검색어 */
export function normalizeQuery(raw) {
  return String(raw ?? "").trim().slice(0, SEARCH_MAX_LENGTH);
}

/**
 * @typedef {{query: string, items: any[], total: number, page: number, loading: boolean, error: string|null}} PagerState
 * @typedef {{type: "reset"|"loading"|"error"} | {type: "page", added: any[]}} PagerEvent
 */

/** @param {string} query @returns {PagerState} */
const initialState = (query) => ({ query, items: [], total: 0, page: 0, loading: false, error: null });

/**
 * 검색어별 페이지 목록. 검색어가 바뀌면 처음부터 다시 받고, 그 전에 보낸 요청의 응답은 버린다.
 * @param {{fetchPage: (params: {page: number, query: string}) => Promise<{items: any[], total: number}>,
 *          onChange?: (event: PagerEvent) => void}} options
 */
export function createWordPager({ fetchPage, onChange = () => {} }) {
  let state = initialState("");
  let generation = 0; // 검색어가 바뀔 때마다 올린다

  async function loadMore() {
    if (state.loading) return;
    const mine = generation;
    const target = state;
    const page = target.page + 1;
    target.loading = true;
    target.error = null;
    onChange({ type: "loading" });
    try {
      const data = await fetchPage({ page, query: target.query });
      if (mine !== generation) return;
      target.page = page;
      target.total = data.total;
      target.items = [...target.items, ...data.items];
      target.loading = false;
      onChange({ type: "page", added: data.items });
    } catch (error) {
      if (mine !== generation) return;
      target.loading = false;
      target.error = error?.detail ?? "불러오지 못했어요.";
      onChange({ type: "error" });
    }
  }

  /** @param {unknown} raw */
  async function search(raw) {
    const query = normalizeQuery(raw);
    // 같은 검색어를 이미 받았거나 받는 중이면 그대로 둔다. 실패했던 검색어는 다시 받는다.
    if (query === state.query && !state.error && (state.loading || state.page > 0)) return;
    await restart(query);
  }

  /** @param {string} query */
  async function restart(query) {
    generation += 1;
    state = initialState(query);
    onChange({ type: "reset" });
    await loadMore();
  }

  return {
    get state() {
      return state;
    },
    loadMore,
    search,
    /** 지금 검색어로 처음부터 다시 받는다 (단어를 추가·수정·삭제한 뒤). */
    reload: () => restart(state.query),
  };
}

/**
 * 목록 아래에 보일 안내. 'more' 는 더 보기 버튼, 'error' 는 다시 시도 버튼과 함께 그린다.
 * @param {PagerState} state
 * @returns {{kind: "loading"|"error"|"more"|"done", text: string}}
 */
export function pagerFooter({ query, items, total, loading, error }) {
  if (loading) return { kind: "loading", text: "불러오는 중…" };
  if (error) return { kind: "error", text: error };
  if (total === 0) return { kind: "done", text: query ? `'${query}' 검색 결과가 없어요.` : "단어가 없어요." };
  if (items.length < total) return { kind: "more", text: `더 보기 (${items.length}/${total})` };
  return { kind: "done", text: query ? `검색 결과 ${total}단어` : `전체 ${total}단어` };
}
