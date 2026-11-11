/*
 * 2026-11-10 - voda-voca - UI 다듬기 회귀 테스트: 해설 시트 예문-해석 간격, 다크 모드 3D 버튼 가장자리, 단어 시트의 예문 듣기 제거
 * 파일 위치: src/frontend/tests/ui-polish.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const ROOT = new URL("..", import.meta.url).pathname;
const read = (rel) => readFileSync(join(ROOT, rel), "utf8");
const css = read("css/app.css");

// ---------- 1. 해설 시트: 예문과 예문 해석을 한 덩어리로 ----------

test("해설 시트: 예문 해석은 예문과 같은 열(.sheet-example-text)에 있고, 발음 버튼 줄 밖에 따로 놓이지 않는다", () => {
  const src = read("js/views/components/feedback-sheet.js");
  const start = src.indexOf("sheet-example-text");
  assert.ok(start >= 0, "예문과 해석을 담는 .sheet-example-text 열이 필요하다");
  const column = src.slice(start, src.indexOf('kind: "sentence"', start));
  assert.match(column, /feedback\.example\b/);
  assert.match(column, /feedback\.example_meaning/, "예문 해석이 예문과 같은 열 안에 있어야 간격이 벌어지지 않는다");
});

// ---------- 2. 다크 모드: 3D 버튼 가장자리는 표면보다 어두워야 '튀어나와' 보인다 ----------

/** @param {string} hex #rrggbb 또는 rgba(r,g,b,a) @returns {number} 상대 밝기 근사 (0~255) */
function luma(value) {
  const hex = value.match(/^#([0-9a-f]{6})$/i);
  const rgb = hex ? [0, 2, 4].map((i) => parseInt(hex[1].slice(i, i + 2), 16)) : value.match(/\d+/g).slice(0, 3).map(Number);
  return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2];
}

/** @param {string} block CSS 블록 문자열 @param {string} name 토큰 이름 @returns {string|null} */
function token(block, name) {
  return block.match(new RegExp(`${name}:\\s*([^;]+);`))?.[1].trim() ?? null;
}

test("다크 모드: .btn-secondary 가장자리 토큰이 표면(--surface)보다 어둡다 (밝은 가장자리는 움푹 들어가 보인다)", () => {
  const dark = css.slice(css.indexOf("html.dark {"));
  const darkBlock = dark.slice(0, dark.indexOf("}"));
  const surface = token(darkBlock, "--surface");
  const edge = token(darkBlock, "--btn-secondary-edge");
  assert.ok(edge, "html.dark 에서 --btn-secondary-edge 를 정의해야 한다");
  assert.ok(luma(edge) < luma(surface), `가장자리(${edge})가 표면(${surface})보다 어두워야 한다`);
});

test(".btn-secondary 는 가장자리에 --btn-secondary-edge 토큰을 쓴다", () => {
  assert.match(css, /\.btn-secondary\s*\{[^}]*--btn-edge:\s*var\(--btn-secondary-edge\)/);
  assert.match(css, /:root\s*\{[^}]*--btn-secondary-edge:/s, "라이트 값도 :root 에 있어야 한다");
});

// ---------- 3. 단어 미리보기 시트: 예문 듣기 없음 (표제어 듣기만) ----------

test("단어 미리보기 시트에는 예문 발음 버튼이 없고 표제어 발음 버튼만 있다", () => {
  const src = read("js/views/components/word-sheet.js");
  assert.doesNotMatch(src, /kind:\s*"sentence"/);
  assert.match(src, /kind:\s*"word"/);
});

// ---------- 3. 플래시카드 뒷면: 예문과 예문 해석을 한 열로 (해설 시트와 같은 구조) ----------

test("플래시카드 뒷면: 예문 해석은 예문과 같은 열에 있고, 발음 버튼 줄 밖에 따로 놓이지 않는다", () => {
  const src = read("js/views/study-session-view.js");
  const start = src.indexOf("card-example-text");
  assert.ok(start >= 0, "예문과 해석을 담는 .card-example-text 열이 필요하다");
  const column = src.slice(start, src.indexOf('kind: "sentence"', start));
  assert.match(column, /faces\.back\.example\b/);
  assert.match(column, /faces\.back\.exampleMeaning/, "해석이 같은 열 안에 있어야 44px 버튼 줄 높이만큼 틈이 벌어지지 않는다");
});
