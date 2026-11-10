/*
 * 2026-11-06 - voda-voca - 발음기호(IPA) 표시 테스트: 서식 함수, 플래시카드 뒷면, CSS 토큰, 3개 뷰 연동과 퀴즈 비노출 (v2.2 IPA 4단계)
 * 파일 위치: src/frontend/tests/phonetic.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { formatPhonetic, phoneticSpec } from "../js/core/phonetic.js";
import { flashcardFaces } from "../js/core/session-view-model.js";

const ROOT = new URL("..", import.meta.url).pathname;
const read = (rel) => readFileSync(join(ROOT, rel), "utf8");

test("formatPhonetic: 순수 IPA 문자열을 슬래시로 감싼다", () => {
  assert.equal(formatPhonetic("ˈæpəl"), "/ˈæpəl/");
});

test("formatPhonetic: null·undefined·빈 값·공백은 null", () => {
  for (const raw of [null, undefined, "", "   ", "//", "/ /"]) assert.equal(formatPhonetic(raw), null, JSON.stringify(raw));
});

test("formatPhonetic: 슬래시가 섞여 들어와도 한 쌍만 남기고 앞뒤 공백을 지운다", () => {
  assert.equal(formatPhonetic(" /ˈæpəl/ "), "/ˈæpəl/");
  assert.equal(formatPhonetic("/ˈæpəl"), "/ˈæpəl/");
});

test("phoneticSpec: 값이 없으면 null — 요소 자체를 그리지 않는다", () => {
  assert.equal(phoneticSpec(null), null);
  assert.equal(phoneticSpec(""), null);
});

test("phoneticSpec: .phonetic 클래스, aria-hidden, 슬래시 서식 텍스트", () => {
  assert.deepEqual(phoneticSpec("ˈæpəl"), { class: "phonetic", "aria-hidden": "true", text: "/ˈæpəl/" });
});

test("phonetic-line 컴포넌트: 스펙이 없으면 null 을 돌려주고, 있으면 aria-hidden 요소를 만든다", () => {
  const src = read("js/views/components/phonetic-line.js");
  assert.match(src, /phoneticSpec\(/);
  assert.match(src, /if \(!spec\) return null/);
  assert.match(src, /h\("span"/);
});

test("flashcardFaces: 앞면에 표제어와 발음기호가 있고, 뒷면에는 표제어·발음기호가 없다 (2026-11-10 사양 변경)", () => {
  const faces = flashcardFaces({ term: "apple", phonetic: "ˈæpəl", meaning: "사과", context: null, example_meaning: null });
  assert.equal(faces.front.term, "apple");
  assert.equal(faces.front.phonetic, "ˈæpəl");
  assert.equal("term" in faces.back, false);
  assert.equal("phonetic" in faces.back, false);
});

test("flashcardFaces: phonetic 이 없는 문항은 앞면 phonetic 이 null", () => {
  assert.equal(flashcardFaces({ term: "apple", meaning: "사과" }).front.phonetic, null);
});

test(".phonetic CSS: 토큰만 쓰고 IPA 폴백 폰트 체인을 가진다", () => {
  const css = read("css/app.css");
  const rule = css.match(/\n\.phonetic\s*\{([^}]*)\}/);
  assert.ok(rule, "app.css 에 .phonetic 규칙이 필요하다");
  const body = rule[1];
  assert.match(body, /font-size:\s*var\(--fs-caption\)/);
  assert.match(body, /color:\s*var\(--muted\)/);
  assert.match(body, /font-weight:\s*400/);
  assert.match(body, /font-family:\s*var\(--font-ipa\)/);
  assert.match(body, /letter-spacing:\s*0/);
  assert.doesNotMatch(body.replace(/var\([^)]*\)/g, ""), /#[0-9a-fA-F]{3,8}\b|rgba?\(/, "리터럴 색 금지(다크 모드 누락 방지)");
  assert.match(css, /--font-ipa:\s*var\(--font-sans\),\s*'Lucida Sans Unicode',\s*sans-serif/);
});

test("해설 시트·플래시카드 뒷면·단어 시트는 phoneticLine 을 쓴다", () => {
  for (const file of ["js/views/components/feedback-sheet.js", "js/views/components/word-sheet.js", "js/views/study-session-view.js"]) {
    assert.match(read(file), /phoneticLine\(/, `${file} 이 phoneticLine 을 써야 한다`);
  }
});

test("4지선다 문제 화면 렌더러(renderQuestion~renderChoices)에는 발음기호가 없다", () => {
  const src = read("js/views/study-session-view.js");
  const start = src.indexOf("function renderQuestion");
  const end = src.indexOf("function renderFlashcard(");
  assert.ok(start >= 0 && end > start, "퀴즈 렌더러 구간을 찾지 못했다");
  assert.doesNotMatch(src.slice(start, end), /phonetic/i);
});

test("플래시카드: 앞면(.flip-face)에는 발음기호가 있고, 뒷면(.flip-back)에는 없다", () => {
  const src = read("js/views/study-session-view.js");
  const start = src.indexOf('{ class: "flip-face" }');
  const split = src.indexOf('"flip-face flip-back"');
  assert.ok(start >= 0 && split > start, "앞면 구간을 찾지 못했다");
  assert.match(src.slice(start, split), /phoneticLine\(/);
  const back = src.slice(split, src.indexOf("refs.card = card"));
  assert.doesNotMatch(back, /phonetic|faces\.back\.term/i);
});
