/*
 * 2026-11-03 - voda-voca - 플래시카드 전체 로딩: 서버 한도(limit)를 넘는 세트를 offset 으로 이어 받아 빠짐없이 모은다 (이슈 #9)
 * 파일 위치: src/frontend/js/core/flashcard-load.js
 */

export const FLASHCARD_PAGE_SIZE = 500; // 서버 FLASHCARD_LIMIT_MAX 와 같다
export const FLASHCARD_MAX_PAGES = 20; // 무한 반복 방지. 20 x 500 = 최대 10,000장

/**
 * 첫 응답의 total 만큼 모두 받을 때까지 offset 을 늘려 가며 이어 받는다.
 * 서버는 표제어 순서로만 이어 받을 수 있으므로 호출자는 shuffle 을 요청하지 않는다 (섞기는 받은 뒤 화면에서 한다).
 *
 * @template T
 * @param {(page: {limit: number, offset: number}) => Promise<{items: T[], total: number}>} fetchPage
 * @param {{pageSize?: number, maxPages?: number}} [opts]
 * @returns {Promise<{items: T[], total: number, truncated: boolean}>}
 *   total 은 서버가 알려 준 전체 개수, truncated 는 maxPages 에 막혀 전부 받지 못했는지다.
 */
export async function loadAllCards(fetchPage, { pageSize = FLASHCARD_PAGE_SIZE, maxPages = FLASHCARD_MAX_PAGES } = {}) {
  /** @type {T[]} */
  const items = [];
  let total = 0;
  for (let page = 0; page < maxPages; page += 1) {
    const data = await fetchPage({ limit: pageSize, offset: items.length });
    items.push(...data.items);
    total = data.total;
    // 빈 응답이면 더 받을 것이 없다 (받는 도중 단어가 삭제되어 total 보다 적어진 경우 포함)
    if (data.items.length === 0 || items.length >= total) return { items, total, truncated: false };
  }
  return { items, total, truncated: items.length < total };
}
