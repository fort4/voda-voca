/*
 * 2026-11-05 - voda-voca - 복습함 뷰모델: 북마크·오답 출처별 시작 가능 여부와 안내 문구, 목록 행 표시 값(품사·발음기호) (DOM 없는 순수 로직)
 * 파일 위치: src/frontend/js/core/review-model.js
 */

/** 복습 세션을 시작하는 데 필요한 최소 단어 수 (서버의 퀴즈 출제 최소 단어 수와 같다) */
export const REVIEW_MIN_WORDS = 4;

/**
 * 복습함에 처음 보일 탭. 다른 화면이 `#/review?tab=wrong` 으로 보내면 틀린 단어를 연다.
 * @param {Record<string, string>|undefined} query
 * @returns {"bookmarks"|"wrong"}
 */
export function initialReviewTab(query) {
  return query?.tab === "wrong" ? "wrong" : "bookmarks";
}

/**
 * 복습 출처 두 개(북마크, 오답)의 시작 가능 여부와 문구. 개수를 모르면(null) 막되 숫자를 지어내지 않는다.
 * @param {{bookmarkCount: number|null, wrongCount: number|null}} counts
 * @returns {Array<{id: "bookmarks"|"wrong", count: number|null, ready: boolean, message: string}>}
 */
export function reviewSources({ bookmarkCount, wrongCount }) {
  return [
    sourceState("bookmarks", bookmarkCount, "북마크한 단어", "북마크"),
    sourceState("wrong", wrongCount, "틀린 단어", "틀린 단어"),
  ];
}

/**
 * 오늘 복습(SRS) 카드의 상태. 복습 예정 시각이 도래한 단어 수 기준이며 1개 이상이면 시작할 수 있다.
 * (퀴즈의 4개 최소 기준은 서버가 안내한다. 플래시카드는 1개로도 가능하다.)
 * @param {number|null|undefined} count
 * @returns {{id: "due", count: number|null, ready: boolean, message: string}}
 */
export function dueSource(count) {
  if (count === null || count === undefined) return { id: "due", count: null, ready: false, message: "불러오는 중이에요." };
  return {
    id: "due",
    count,
    ready: count >= 1,
    message: count >= 1 ? `오늘 복습할 단어 ${count}개예요.` : "오늘 복습할 단어를 모두 마쳤어요.",
  };
}

/** @param {"bookmarks"|"wrong"} id @param {number|null} count @param {string} readyLabel @param {string} lackLabel */
function sourceState(id, count, readyLabel, lackLabel) {
  if (count === null || count === undefined) {
    return { id, count: null, ready: false, message: "불러오는 중이에요." };
  }
  const ready = count >= REVIEW_MIN_WORDS;
  return {
    id,
    count,
    ready,
    message: ready
      ? `${readyLabel} ${count}개로 복습합니다.`
      : `${lackLabel}가 ${REVIEW_MIN_WORDS}개 이상이어야 복습할 수 있어요 (현재 ${count}개).`,
  };
}

/**
 * 북마크·오답 목록 한 줄. 예문은 싣지 않고, 품사·발음기호는 없으면 null 로 둔다.
 * @param {{word_id: number, vocabulary_title: string, term: string, meaning: string, pos?: string|null, phonetic?: string|null}} item
 */
export function bookmarkRow(item) {
  return {
    wordId: item.word_id,
    term: item.term,
    meaning: item.meaning,
    pos: item.pos || null,
    phonetic: item.phonetic || null,
    source: item.vocabulary_title,
  };
}
