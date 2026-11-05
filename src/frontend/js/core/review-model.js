/*
 * 2026-11-05 - voda-voca - 복습함 뷰모델: 북마크·오답 출처별 시작 가능 여부와 안내 문구, 북마크 행 표시 값 (DOM 없는 순수 로직)
 * 파일 위치: src/frontend/js/core/review-model.js
 */

import { QUIZ_MIN_WORDS } from "../lib/study-source.js";

/** 복습 세션을 시작하는 데 필요한 최소 단어 수 (퀴즈 출제 기준과 같다) */
export const REVIEW_MIN_WORDS = QUIZ_MIN_WORDS;

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
 * 북마크·오답 목록 한 줄. 예문이 없으면 그 줄을 그리지 않도록 null 로 둔다.
 * @param {{word_id: number, vocabulary_title: string, term: string, meaning: string, example?: string|null, example_meaning?: string|null}} item
 */
export function bookmarkRow(item) {
  return {
    wordId: item.word_id,
    term: item.term,
    meaning: item.meaning,
    example: item.example || null,
    exampleMeaning: item.example_meaning || null,
    source: item.vocabulary_title,
  };
}
