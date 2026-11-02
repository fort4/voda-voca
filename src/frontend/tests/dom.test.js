/*
 * 2026-11-02 - voda-voca - 아이콘 렌더링 헬퍼 단위 테스트: Lucide 가 없어도 안전, 있으면 createIcons 호출 (아이콘 미표기 버그 회귀 방지)
 * 파일 위치: src/frontend/tests/dom.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { refreshIcons } from "../js/core/dom.js";

test("Lucide 가 로드되지 않았으면 refreshIcons 는 예외 없이 false 를 돌려준다", () => {
  const saved = globalThis.lucide;
  delete globalThis.lucide;
  try {
    assert.doesNotThrow(() => refreshIcons());
    assert.equal(refreshIcons(), false);
  } finally {
    globalThis.lucide = saved;
  }
});

test("Lucide 가 있으면 createIcons 를 호출해 아이콘 자리표시자를 바꾼다", () => {
  const saved = globalThis.lucide;
  let calls = 0;
  globalThis.lucide = { createIcons: () => { calls += 1; } };
  try {
    assert.equal(refreshIcons(), true);
    refreshIcons();
    assert.equal(calls, 2, "화면을 그릴 때마다 호출된다");
  } finally {
    globalThis.lucide = saved;
  }
});

test("createIcons 가 없는 객체면 호출하지 않는다", () => {
  const saved = globalThis.lucide;
  globalThis.lucide = { icons: {} };
  try {
    assert.equal(refreshIcons(), false);
  } finally {
    globalThis.lucide = saved;
  }
});
