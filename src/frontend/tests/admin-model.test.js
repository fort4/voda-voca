/*
 * 2026-11-26 - voda-voca - 관리자 화면 모델 검사: 관리 가능 판정, 입력 검증과 요청 본문, 오류 문구, 삭제 안내 (REQ-160, REQ-161)
 * 파일 위치: src/frontend/tests/admin-model.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  VOCABULARY_CATEGORIES,
  adminFailureMessage,
  canEditContent,
  deleteVocabularyPrompt,
  deleteWordPrompt,
  vocabularyForm,
  wordForm,
} from "../js/core/admin-model.js";
import { categoryLabel, normalizeFilter } from "../js/core/explore-model.js";

const admin = { is_admin: true };
const learner = { is_admin: false };

test("canEditContent: 관리자이면서 관리자 등록분일 때만 수정·삭제한다", () => {
  assert.equal(canEditContent(admin, { source: "admin" }), true);
  assert.equal(canEditContent(admin, { source: "seed" }), false);
  assert.equal(canEditContent(learner, { source: "admin" }), false);
  assert.equal(canEditContent(null, { source: "admin" }), false);
});

test("단어장 분류 선택지: 서버 시드의 다섯 분류와 기타. 기타는 한글로 보인다", () => {
  assert.deepEqual(
    VOCABULARY_CATEGORIES.map((c) => c.value),
    ["ELEMENTARY", "SECONDARY", "CSAT", "EXAM", "BUSINESS", "ETC"],
  );
  assert.equal(categoryLabel("ETC"), "기타");
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

test("vocabularyForm: 새 단어장은 네 항목, 수정은 제목과 설명만 보낸다", () => {
  const values = { title: " 우리 반 ", description: " ", category: "ETC", level: "3" };
  assert.deepEqual(vocabularyForm(values, { creating: true }), {
    errors: {},
    body: { title: "우리 반", description: null, category: "ETC", level: 3 },
  });
  assert.deepEqual(vocabularyForm(values, { creating: false }).body, { title: "우리 반", description: null });
});

test("vocabularyForm: 제목 필수, 길이 한도", () => {
  const { errors } = vocabularyForm({ title: "", description: "d".repeat(256), category: "ETC", level: "1" }, { creating: true });
  assert.equal(errors.title, "제목을 입력해 주세요.");
  assert.match(errors.description, /255자/);
});

test("adminFailureMessage: 서버 문구를 쓰고, 422 는 항목 이름을 붙인다", () => {
  assert.equal(adminFailureMessage({ status: 409, detail: "이 단어장에 이미 있는 표제어입니다." }), "이 단어장에 이미 있는 표제어입니다.");
  assert.equal(
    adminFailureMessage({ status: 422, detail: "x", fields: [{ field: "meaning", message: "너무 깁니다." }] }),
    "뜻: 너무 깁니다.",
  );
  assert.equal(adminFailureMessage({}), "저장하지 못했어요. 다시 시도해 주세요.");
});

test("삭제 안내: 모든 사용자의 기록이 함께 지워짐을 알린다", () => {
  const word = deleteWordPrompt({ term: "ladle" });
  assert.match(word.title, /ladle/);
  assert.match(word.text, /모든 사용자/);
  assert.match(word.text, /학습 이력/);
  assert.match(word.text, /북마크/);
  const vocabulary = deleteVocabularyPrompt({ title: "우리 반", total_words: 12 });
  assert.match(vocabulary.title, /우리 반/);
  assert.match(vocabulary.text, /12단어/);
  assert.match(vocabulary.text, /모든 사용자/);
});

test("normalizeFilter: 목록에서 사라진 분류·레벨의 필터는 전체로 되돌린다", () => {
  const catalog = [{ category: "ELEMENTARY", level: 1 }];
  assert.deepEqual(normalizeFilter(catalog, { category: "ETC", level: "3" }), { category: "all", level: "all" });
  assert.deepEqual(normalizeFilter(catalog, { category: "ELEMENTARY", level: 1 }), { category: "ELEMENTARY", level: 1 });
});
