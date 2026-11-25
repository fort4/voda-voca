/*
 * 2026-11-26 - voda-voca - 단어 미리보기 시트의 검색 입력 구성 검사: 접근성, 터치 크기, 지연 요청, API 파라미터 (REQ-163)
 * 파일 위치: src/frontend/tests/word-search-ui.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { INPUT_CLASS } from "../js/core/form.js";

const src = readFileSync(new URL("../js/views/components/word-sheet.js", import.meta.url), "utf8");

test("검색 입력: type=search, 이름표, 길이 제한, 44px 터치 크기, iOS 확대를 막는 글자 크기", () => {
  assert.match(src, /type:\s*"search"/);
  assert.match(src, /"aria-label":\s*"표제어 또는 뜻 검색"/);
  assert.match(src, /maxlength:\s*SEARCH_MAX_LENGTH/);
  assert.match(src, /class:\s*INPUT_CLASS/, "공통 입력 스타일을 쓴다 (다크 모드 포함)");
  assert.match(INPUT_CLASS, /min-h-\[44px\]/);
  assert.match(INPUT_CLASS, /\btext-base\b/);
});

test("검색어는 q 파라미터로 보내고, 비어 있으면 보내지 않는다", () => {
  assert.match(src, /q:\s*query\s*\|\|\s*undefined/);
});

test("입력은 잠시 멈춘 뒤 검색하고, 시트를 닫으면 예약을 취소한다", () => {
  assert.match(src, /SEARCH_DEBOUNCE_MS/);
  assert.match(src, /clearTimeout\(/);
  const close = src.slice(src.indexOf("const close"), src.indexOf("const onKey"));
  assert.match(close, /clearTimeout\(/);
});

test("한글 조합 중 Enter 는 무시하고, 결과 안내는 화면낭독기에 알린다", () => {
  assert.match(src, /isComposing/);
  assert.match(src, /"aria-live":\s*"polite"/);
});
