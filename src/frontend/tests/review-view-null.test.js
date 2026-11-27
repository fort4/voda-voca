/*
 * 2026-11-05 - voda-voca - 복습함 화면 회귀 방지: 조건부 자식(null)이 네이티브 append 로 들어가 "null" 글자가 보이던 결함
 * 파일 위치: src/frontend/tests/review-view-null.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("../js/views/review-view.js", import.meta.url), "utf8");

test("복습함 본문은 조건부 자식을 거르는 appendNodes 로 붙인다", () => {
  assert.match(source, /appendNodes\(\s*this\.body,/);
  assert.equal(/this\.body\.append\(/.test(source), false, "this.body.append 는 null 을 \"null\" 글자로 그린다");
});

test("복습함 행은 예문을 그리지 않고 품사 태그와 발음기호를 그린다", () => {
  assert.equal(/r\.example/.test(source), false, "예문 줄을 그리지 않는다");
  assert.match(source, /posTag\(r\.pos\)/);
  assert.match(source, /phoneticLine\(r\.phonetic\)/);
});

test("복습함은 통계의 오늘 복습 개수로 SRS 카드를 그리고 due 세션을 시작한다 (#25)", () => {
  assert.match(source, /dueSource\(/);
  assert.match(source, /api\("\/study\/stats"\)/);
  assert.match(source, /openSession\(.*"due"\)/);
  assert.match(source, /due_review_count/);
});

test("빈 목록에는 안내 문장 아래에 홈으로 가는 secondary 버튼을 둔다 (UI/UX §3.4, REQ-018·129)", () => {
  const paintList = source.slice(source.indexOf("  paintList() {"), source.indexOf("  /** 다른 탭의 늦은 응답은"));
  assert.match(paintList, /items\.length === 0 \? \[this\.emptyCard\(\)\]/, "목록이 비었을 때만 그린다");
  const card = source.slice(source.indexOf("  emptyCard() {"), source.indexOf("  paintList() {"));
  assert.match(card, /북마크한 단어가 없어요/);
  assert.match(card, /틀린 단어가 없어요/);
  assert.match(card, /button\(\{ variant: "secondary", onClick: \(\) => this\.ctx\.navigate\("\/"\) \}, "홈으로"\)/);
});
