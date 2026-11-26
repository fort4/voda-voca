/*
 * 2026-11-26 - voda-voca - 탐색의 단어장 카드 플랫 스타일 검사: 그림자 없음, 1px 회색 테두리, 호버는 테두리·배경색 변화
 * 파일 위치: src/frontend/tests/flat-vocab-card.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const ROOT = new URL("..", import.meta.url).pathname;
const read = (rel) => readFileSync(join(ROOT, rel), "utf8");
const css = read("css/app.css").replace(/\/\*[\s\S]*?\*\//g, "");

/** @param {string} selector @returns {string} 선택자 목록에 selector 가 정확히 들어 있는 규칙들의 선언 */
function declarations(selector) {
  return [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)]
    .filter((m) => m[1].split(",").some((s) => s.trim() === selector))
    .map((m) => m[2])
    .join(";");
}

test("탐색의 단어장 카드는 .vocab-card 를 쓰고 shadow-* 유틸리티가 없다", () => {
  const src = read("js/views/explore-view.js");
  assert.match(src, /class:\s*"card vocab-card rise-in/);
  assert.doesNotMatch(src, /shadow/);
});

// 상태별 선택자는 .btn 의 상태 규칙(.btn:active:not(:disabled) 등)보다 명시도가 높아야 이긴다
for (const selector of [
  ".vocab-card",
  ".vocab-card:hover",
  ".vocab-card:focus-within",
  ".vocab-card:active",
  ".vocab-card .btn",
  ".vocab-card .btn:hover:not(:disabled)",
  ".vocab-card .btn:focus",
  ".vocab-card .btn:active:not(:disabled)",
]) {
  test(`${selector} 는 그림자가 없다`, () => {
    assert.match(declarations(selector), /box-shadow:\s*none/);
  });
}

test("카드와 내부 버튼은 1px 회색 테두리를 쓴다", () => {
  assert.match(declarations(".vocab-card"), /border:\s*1px solid var\(--border\)/);
  assert.match(declarations(".vocab-card .btn"), /border:\s*1px solid var\(--border\)/);
});

test("호버는 그림자 대신 테두리 색이 바뀌고, 눌러도 움직이지 않는다", () => {
  assert.match(declarations(".vocab-card:hover"), /border-color:\s*var\(--border-strong\)/);
  assert.match(declarations(".vocab-card .btn:hover:not(:disabled)"), /border-color:\s*var\(--border-strong\)/);
  assert.match(declarations(".vocab-card .btn:active:not(:disabled)"), /transform:\s*none/);
});
