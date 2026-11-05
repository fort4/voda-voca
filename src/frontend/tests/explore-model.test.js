/*
 * 2026-11-05 - voda-voca - 탐색 화면 뷰모델 테스트: 카탈로그 필터(카테고리·레벨), 카드 표시 값, 활성 단어장 표시
 * 파일 위치: src/frontend/tests/explore-model.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";

import { categoryOptions, filterVocabularies, levelOptions, vocabularyCard } from "../js/core/explore-model.js";

const vocab = (id, category, level, extra = {}) => ({
  id,
  slug: `v${id}`,
  title: `단어장 ${id}`,
  category,
  level,
  description: null,
  total_words: 100,
  user_progress: { studied_words: 0, memorized_words: 0, progress_rate: 0, is_active: false },
  ...extra,
});

const CATALOG = [vocab(1, "ELEMENTARY", 1), vocab(2, "SECONDARY", 2), vocab(3, "SECONDARY", 3), vocab(4, "CSAT", 3)];

test("필터가 비어 있으면 카탈로그 전체를 순서 그대로 돌려준다", () => {
  assert.deepEqual(filterVocabularies(CATALOG, {}).map((v) => v.id), [1, 2, 3, 4]);
});

test("카테고리와 레벨 필터는 AND 로 적용된다", () => {
  assert.deepEqual(filterVocabularies(CATALOG, { category: "SECONDARY" }).map((v) => v.id), [2, 3]);
  assert.deepEqual(filterVocabularies(CATALOG, { level: 3 }).map((v) => v.id), [3, 4]);
  assert.deepEqual(filterVocabularies(CATALOG, { category: "SECONDARY", level: 3 }).map((v) => v.id), [3]);
});

test("'all' 이나 빈 값은 해당 필터를 끈다", () => {
  assert.equal(filterVocabularies(CATALOG, { category: "all", level: "all" }).length, 4);
  assert.equal(filterVocabularies(CATALOG, { category: "", level: null }).length, 4);
});

test("레벨 필터는 문자열(select 값)로 와도 숫자 레벨과 비교한다", () => {
  assert.deepEqual(filterVocabularies(CATALOG, { level: "1" }).map((v) => v.id), [1]);
});

test("카탈로그가 비었거나 맞는 게 없으면 빈 배열", () => {
  assert.deepEqual(filterVocabularies([], { category: "CSAT" }), []);
  assert.deepEqual(filterVocabularies(CATALOG, { category: "TOEIC" }), []);
});

test("카테고리 선택지: 카탈로그에 실제 있는 값만, 처음 나온 순서, 맨 앞에 '전체'", () => {
  assert.deepEqual(categoryOptions(CATALOG).map((o) => o.value), ["all", "ELEMENTARY", "SECONDARY", "CSAT"]);
  assert.equal(categoryOptions(CATALOG)[0].label, "전체");
  assert.equal(categoryOptions(CATALOG)[2].label, "중고등");
});

test("알 수 없는 카테고리는 코드 그대로 라벨로 쓴다", () => {
  assert.equal(categoryOptions([vocab(9, "NEW_CAT", 1)])[1].label, "NEW_CAT");
});

test("레벨 선택지: 중복 없이 오름차순, 맨 앞에 '전체'", () => {
  assert.deepEqual(levelOptions(CATALOG).map((o) => o.value), ["all", 1, 2, 3]);
  assert.equal(levelOptions(CATALOG)[3].label, "Lv.3");
});

test("카드: 진행률은 반올림 정수, 활성 여부와 단어 수 문구를 만든다", () => {
  const card = vocabularyCard(
    vocab(2, "SECONDARY", 2, {
      total_words: 1000,
      description: "빈출 기본 어휘",
      user_progress: { studied_words: 520, memorized_words: 140, progress_rate: 52.4, is_active: true },
    }),
  );
  assert.equal(card.progressPercent, 52);
  assert.equal(card.isActive, true);
  assert.equal(card.wordCountText, "1,000단어");
  assert.equal(card.progressText, "520 / 1,000 학습 · 140 숙련");
  assert.equal(card.levelLabel, "Lv.2");
  assert.equal(card.categoryLabel, "중고등");
  assert.equal(card.description, "빈출 기본 어휘");
});

test("카드: 설명이 없으면 빈 문자열이 아니라 null (줄을 그리지 않는다)", () => {
  assert.equal(vocabularyCard(vocab(1, "ELEMENTARY", 1)).description, null);
});

test("카드: 진행률은 0~100 으로 자른다", () => {
  const over = vocabularyCard(vocab(1, "CSAT", 1, { user_progress: { studied_words: 0, memorized_words: 0, progress_rate: 140, is_active: false } }));
  assert.equal(over.progressPercent, 100);
});
