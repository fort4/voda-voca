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
