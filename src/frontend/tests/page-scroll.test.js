/*
 * 2026-11-26 - voda-voca - 문서 스크롤 회귀 방지 테스트: body 가 스크롤 컨테이너가 되어 휠·터치 스크롤을 막지 않는지 검사한다
 * 파일 위치: src/frontend/tests/page-scroll.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const css = readFileSync(new URL("../css/app.css", import.meta.url), "utf8").replace(/\/\*[\s\S]*?\*\//g, "");

/** @param {string} tag @returns {string} 선택자 목록에 `tag` 만 단독으로 쓴 규칙들의 선언 모음 */
function declarationsFor(tag) {
  return [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)]
    .filter(([, selectors]) => selectors.split(",").some((s) => s.trim() === tag))
    .map(([, , body]) => body)
    .join("\n");
}

test("body 는 스크롤 컨테이너가 아니다 (hidden·auto·scroll 금지, 가로 넘침은 clip)", () => {
  assert.doesNotMatch(declarationsFor("body"), /overflow(-[xy])?\s*:\s*(hidden|auto|scroll)/);
});

test("overscroll-behavior 는 문서 루트(html)에만 건다", () => {
  // body 에 contain 을 걸면 스크롤할 내용이 없어도 휠·터치가 문서로 전달되지 않는다
  assert.doesNotMatch(declarationsFor("body"), /overscroll-behavior/);
  assert.match(declarationsFor("html"), /overscroll-behavior-y\s*:\s*contain/);
});
