/*
 * 2026-11-02 - voda-voca - 단축키 가드 단위 테스트: 입력 칸·모달·버튼 판정 (v1.1)
 * 파일 위치: src/frontend/tests/shortcuts.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { isButtonTarget, isTypingTarget, shortcutsBlocked } from "../js/core/shortcuts.js";

test("입력 칸(input, textarea, select)과 편집 가능 요소에서는 단축키를 막는다", () => {
  assert.equal(isTypingTarget({ tagName: "INPUT" }), true);
  assert.equal(isTypingTarget({ tagName: "textarea" }), true);
  assert.equal(isTypingTarget({ tagName: "SELECT" }), true);
  assert.equal(isTypingTarget({ tagName: "DIV", isContentEditable: true }), true);
  assert.equal(isTypingTarget({ tagName: "DIV" }), false);
  assert.equal(isTypingTarget(null), false);
});

test("활성 모달이 열려 있으면 어느 대상에서든 단축키를 막는다", () => {
  assert.equal(shortcutsBlocked({ target: { tagName: "DIV" }, modalOpen: true }), true);
  assert.equal(shortcutsBlocked({ target: { tagName: "DIV" }, modalOpen: false }), false);
});

test("입력 칸에 포커스가 있으면 모달이 없어도 막는다", () => {
  assert.equal(shortcutsBlocked({ target: { tagName: "INPUT" }, modalOpen: false }), true);
});

test("버튼 포커스는 구분해서 알려 준다 (Enter·Space 는 브라우저가 클릭하므로 중복 처리하지 않는다)", () => {
  assert.equal(isButtonTarget({ tagName: "BUTTON" }), true);
  assert.equal(isButtonTarget({ tagName: "DIV" }), false);
});
