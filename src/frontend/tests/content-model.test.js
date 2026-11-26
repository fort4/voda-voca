/*
 * 2026-11-26 - voda-voca - 개인 단어장 화면 모델 검사: 수정 가능 판정, 입력 검증과 요청 본문, 오류 문구, 삭제 안내 (#39, REQ-170)
 * 파일 위치: src/frontend/tests/content-model.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  canEditContent,
  contentFailureMessage,
  deleteVocabularyPrompt,
  deleteWordPrompt,
  vocabularyForm,
  wordForm,
  wordSheetEntry,
} from "../js/core/content-model.js";
import { cardActionVariants, categoryLabel, normalizeFilter, vocabularyCard } from "../js/core/explore-model.js";

const progress = { studied_words: 0, memorized_words: 0, progress_rate: 0, is_active: false };
const card = (extra) => vocabularyCard({ id: 1, title: "t", category: "ELEMENTARY", level: 2, description: null, total_words: 5, user_progress: progress, ...extra });

test("canEditContent: 내 단어장만 고칠 수 있다", () => {
  assert.equal(canEditContent({ is_mine: true }), true);
  assert.equal(canEditContent({ is_mine: false }), false);
  assert.equal(canEditContent({}), false);
  assert.equal(canEditContent(null), false);
});

test("단어 시트 진입: 내 단어장은 '단어 관리', 표준 단어장은 '미리보기'다", () => {
  assert.deepEqual(wordSheetEntry({ is_mine: true }), { label: "단어 관리", icon: "list-checks" });
  assert.deepEqual(wordSheetEntry({ is_mine: false }), { label: "미리보기", icon: "eye" });
});

test("개인 단어장 카드: 분류는 '내 단어장'이고 레벨을 보이지 않는다", () => {
  assert.equal(categoryLabel("PERSONAL"), "내 단어장");
  assert.equal(card({ category: "PERSONAL", is_mine: true }).metaText, "내 단어장 · 5단어");
  assert.equal(card({ is_mine: false }).metaText, "초등 · Lv.2 · 5단어");
});

test("단어가 없는 단어장은 학습으로 고를 수 없다", () => {
  assert.equal(card({ total_words: 0 }).canStudy, false);
  assert.equal(card({ total_words: 1 }).canStudy, true);
  assert.deepEqual(cardActionVariants({ isActive: false }), { preview: "ghost", main: "secondary" });
});

test("wordForm: 앞뒤 공백을 지우고, 빈 선택 항목은 null, 예문이 없으면 예문 뜻도 null", () => {
  const { errors, body } = wordForm({ term: "  ladle ", meaning: " 국자 ", example: "   ", example_meaning: "남으면 안 됨" });
  assert.deepEqual(errors, {});
  assert.deepEqual(body, { term: "ladle", meaning: "국자", example: null, example_meaning: null });
});

test("wordForm: 필수 항목과 길이 한도를 칸별로 알린다", () => {
  const empty = wordForm({ term: " ", meaning: "", example: "", example_meaning: "" }).errors;
  assert.equal(empty.term, "표제어를 입력해 주세요.");
  assert.equal(empty.meaning, "뜻을 입력해 주세요.");
  const long = wordForm({ term: "t".repeat(101), meaning: "m".repeat(201), example: "e".repeat(501), example_meaning: "e".repeat(501) }).errors;
  assert.match(long.term, /100자/);
  assert.match(long.meaning, /200자/);
  assert.match(long.example, /500자/);
  assert.match(long.example_meaning, /500자/);
});

test("vocabularyForm: 제목과 설명만 보낸다 (분류·레벨은 서버 기본값)", () => {
  assert.deepEqual(vocabularyForm({ title: " 우리 반 ", description: " " }), { errors: {}, body: { title: "우리 반", description: null } });
});

test("vocabularyForm: 제목 필수, 길이 한도", () => {
  const { errors } = vocabularyForm({ title: "", description: "d".repeat(256) });
  assert.equal(errors.title, "제목을 입력해 주세요.");
  assert.match(errors.description, /255자/);
});

test("contentFailureMessage: 서버 문구를 쓰고, 422 는 항목 이름을 붙인다", () => {
  assert.equal(contentFailureMessage({ status: 409, detail: "이 단어장에 이미 있는 표제어입니다." }), "이 단어장에 이미 있는 표제어입니다.");
  assert.equal(contentFailureMessage({ status: 422, detail: "x", fields: [{ field: "meaning", message: "너무 깁니다." }] }), "뜻: 너무 깁니다.");
  assert.equal(contentFailureMessage({}), "저장하지 못했어요. 다시 시도해 주세요.");
});

test("삭제 안내: 내 학습 기록이 함께 지워짐을 알린다", () => {
  const word = deleteWordPrompt({ term: "ladle" });
  assert.match(word.title, /ladle/);
  for (const part of [/학습 이력/, /북마크/, /되돌릴 수 없/]) assert.match(word.text, part);
  const vocabulary = deleteVocabularyPrompt({ title: "우리 반", total_words: 12 });
  assert.match(vocabulary.title, /우리 반/);
  assert.match(vocabulary.text, /12단어/);
  assert.doesNotMatch(word.text + vocabulary.text, /모든 사용자/);
});

test("normalizeFilter: 목록에서 사라진 분류·레벨의 필터는 전체로 되돌린다", () => {
  const catalog = [{ category: "ELEMENTARY", level: 1 }];
  assert.deepEqual(normalizeFilter(catalog, { category: "PERSONAL", level: "3" }), { category: "all", level: "all" });
  assert.deepEqual(normalizeFilter(catalog, { category: "ELEMENTARY", level: 1 }), { category: "ELEMENTARY", level: 1 });
});
