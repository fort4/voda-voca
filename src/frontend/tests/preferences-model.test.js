/*
 * 2026-11-11 - voda-voca - 환경 설정 뷰모델 테스트: 효과음·다크 모드 스위치 행의 상태, 아이콘, 접근성 라벨
 * 파일 위치: src/frontend/tests/preferences-model.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";

import { preferenceRows, themeToggleView } from "../js/core/preferences-model.js";

test("행은 효과음, 다크 모드 순서로 둘이다", () => {
  const rows = preferenceRows({ muted: false, theme: "light" });
  assert.deepEqual(rows.map((r) => r.id), ["sound", "theme"]);
});

test("효과음: 켜져 있으면 checked 와 bell-ring, 꺼져 있으면 bell-off", () => {
  const [on] = preferenceRows({ muted: false, theme: "light" });
  const [off] = preferenceRows({ muted: true, theme: "light" });
  assert.equal(on.checked, true);
  assert.equal(on.icon, "bell-ring");
  assert.equal(off.checked, false);
  assert.equal(off.icon, "bell-off");
  assert.equal(on.label, "효과음");
});

test("다크 모드: dark 일 때만 checked, 아이콘은 현재 상태(moon/sun)를 보여 준다", () => {
  const [, dark] = preferenceRows({ muted: false, theme: "dark" });
  const [, light] = preferenceRows({ muted: false, theme: "light" });
  assert.equal(dark.checked, true);
  assert.equal(dark.icon, "moon");
  assert.equal(light.checked, false);
  assert.equal(light.icon, "sun");
  assert.equal(dark.label, "다크 모드");
});

test("각 행은 한 줄 설명을 갖고 상태 값을 지어내지 않는다", () => {
  for (const row of preferenceRows({ muted: false, theme: "light" })) {
    assert.ok(row.description.length > 0);
    assert.equal(typeof row.checked, "boolean");
  }
});

test("헤더 다크 모드 버튼: 아이콘과 라벨은 누르면 바뀔 모드를 알려 준다 (라이트면 moon, 다크면 sun)", () => {
  assert.deepEqual(themeToggleView("light"), { icon: "moon", label: "다크 모드로 전환" });
  assert.deepEqual(themeToggleView("dark"), { icon: "sun", label: "라이트 모드로 전환" });
});

test("헤더 다크 모드 버튼: 알 수 없는 값은 라이트로 본다", () => {
  assert.equal(themeToggleView(undefined).icon, "moon");
  assert.equal(themeToggleView("system").label, "다크 모드로 전환");
});
