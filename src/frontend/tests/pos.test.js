/*
 * 2026-11-10 - voda-voca - 품사(pos) 표시 테스트: 한글 라벨, 요소 명세, CSS 토큰, 미리보기·퀴즈·플래시카드·해설 시트 연동
 * 파일 위치: src/frontend/tests/pos.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { POS_LABELS, posLabel, posSpec } from "../js/core/pos.js";
import { flashcardFaces } from "../js/core/session-view-model.js";

const ROOT = new URL("..", import.meta.url).pathname;
const read = (rel) => readFileSync(join(ROOT, rel), "utf8");

test("posLabel: 시드의 품사 8종을 한글 라벨로 바꾼다", () => {
  assert.deepEqual(
    ["noun", "verb", "adjective", "adverb", "preposition", "conjunction", "pronoun", "interjection"].map(posLabel),
    ["명사", "동사", "형용사", "부사", "전치사", "접속사", "대명사", "감탄사"],
  );
  assert.equal(Object.keys(POS_LABELS).length, 8);
});

test("posLabel: 대소문자·공백을 무시하고, 모르는 값은 그대로, 없으면 null", () => {
  assert.equal(posLabel(" Noun "), "명사");
  assert.equal(posLabel("determiner"), "determiner");
  for (const raw of [null, undefined, "", "   "]) assert.equal(posLabel(raw), null, JSON.stringify(raw));
});

test("posSpec: .pos-tag 클래스와 라벨 텍스트, 값이 없으면 null (요소를 그리지 않는다)", () => {
  assert.deepEqual(posSpec("verb"), { class: "pos-tag", text: "동사" });
  assert.equal(posSpec(null), null);
});

test("flashcardFaces: 품사는 앞면에 있다", () => {
  assert.equal(flashcardFaces({ term: "run", pos: "verb", meaning: "달리다" }).front.pos, "verb");
  assert.equal("pos" in flashcardFaces({ term: "run", pos: "verb", meaning: "달리다" }).back, false);
});

test(".pos-tag CSS: 토큰만 쓴다 (다크 모드 자동 대응)", () => {
  const css = read("css/app.css");
  const rule = css.match(/\n\.pos-tag\s*\{([^}]*)\}/);
  assert.ok(rule, "app.css 에 .pos-tag 규칙이 필요하다");
  assert.match(rule[1], /color:\s*var\(--/);
  assert.doesNotMatch(rule[1].replace(/var\([^)]*\)/g, ""), /#[0-9a-fA-F]{3,8}\b|rgba?\(/, "리터럴 색 금지");
});

test("미리보기 시트·해설 시트·퀴즈 카드·플래시카드 앞면이 posTag 를 쓴다", () => {
  for (const file of ["js/views/components/word-sheet.js", "js/views/components/feedback-sheet.js", "js/views/study-session-view.js"]) {
    assert.match(read(file), /posTag\(/, `${file} 이 posTag 를 써야 한다`);
  }
  const session = read("js/views/study-session-view.js");
  const quiz = session.slice(session.indexOf("function renderQuizCard"), session.indexOf("function renderChoices"));
  assert.match(quiz, /posTag\(item\.pos\)/, "퀴즈 문제 화면에 품사가 있다");
  assert.doesNotMatch(quiz, /phonetic/i, "퀴즈 문제 화면에 발음기호는 없다 (품사만)");
  const back = session.slice(session.indexOf('"flip-face flip-back"'), session.indexOf("refs.card = card"));
  assert.doesNotMatch(back, /posTag/, "플래시카드 뒷면에는 품사가 없다");
});

test("퀴즈 문제 카드: 품사는 표제어 위에 놓인다 (힌트 → 품사 → 표제어)", () => {
  const session = read("js/views/study-session-view.js");
  const quiz = session.slice(session.indexOf("function renderQuizCard"), session.indexOf("function renderChoices"));
  const at = (s) => quiz.indexOf(s);
  assert.ok(at("session-hint") >= 0 && at('"session-meta"') >= 0 && at('"session-term"') >= 0);
  assert.ok(at("session-hint") < at('"session-meta"') && at('"session-meta"') < at('"session-term"'), "품사 줄이 표제어보다 앞에 있어야 한다");
});
