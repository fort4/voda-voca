/*
 * 2026-11-02 - voda-voca - 테마 관리자 단위 테스트: 초기 판정 우선순위(저장값 > 시스템), toggle, localStorage 동기화, 저장 실패 내성 (v1.1)
 * 파일 위치: src/frontend/tests/theme.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { createThemeManager, resolveInitialTheme, THEME_KEY } from "../js/core/theme.js";

class FakeStorage {
  constructor(initial = {}, { failing = false } = {}) {
    this.map = new Map(Object.entries(initial));
    this.failing = failing;
  }
  getItem(k) {
    if (this.failing) throw new Error("SecurityError");
    return this.map.has(k) ? this.map.get(k) : null;
  }
  setItem(k, v) {
    if (this.failing) throw new Error("QuotaExceeded");
    this.map.set(k, String(v));
  }
}

function fakeRoot() {
  const classes = new Set();
  return {
    classList: {
      toggle(name, on) {
        const want = on === undefined ? !classes.has(name) : Boolean(on);
        if (want) classes.add(name);
        else classes.delete(name);
      },
      contains: (name) => classes.has(name),
    },
  };
}

const mediaDark = (matches) => () => ({ matches });

test("저장된 값이 있으면 시스템 설정보다 우선한다", () => {
  assert.equal(resolveInitialTheme({ stored: "light", prefersDark: true }), "light");
  assert.equal(resolveInitialTheme({ stored: "dark", prefersDark: false }), "dark");
});

test("저장된 값이 없거나 잘못되면 시스템 설정을 따른다", () => {
  assert.equal(resolveInitialTheme({ stored: null, prefersDark: true }), "dark");
  assert.equal(resolveInitialTheme({ stored: null, prefersDark: false }), "light");
  assert.equal(resolveInitialTheme({ stored: "blue", prefersDark: true }), "dark");
});

test("관리자는 생성 즉시 초기 테마를 루트에 반영한다 (.dark 클래스)", () => {
  const root = fakeRoot();
  const mgr = createThemeManager({ storage: new FakeStorage({ [THEME_KEY]: "dark" }), root, matchMedia: mediaDark(false) });
  assert.equal(mgr.current(), "dark");
  assert.equal(root.classList.contains("dark"), true);
});

test("저장값 light 는 시스템이 다크여도 라이트로 시작한다", () => {
  const root = fakeRoot();
  const mgr = createThemeManager({ storage: new FakeStorage({ [THEME_KEY]: "light" }), root, matchMedia: mediaDark(true) });
  assert.equal(mgr.current(), "light");
  assert.equal(root.classList.contains("dark"), false);
});

test("toggle 은 테마를 뒤집고, 클래스와 저장소를 함께 맞춘다", () => {
  const root = fakeRoot();
  const storage = new FakeStorage();
  const mgr = createThemeManager({ storage, root, matchMedia: mediaDark(false) });
  assert.equal(mgr.current(), "light");
  assert.equal(mgr.toggle(), "dark");
  assert.equal(root.classList.contains("dark"), true);
  assert.equal(storage.getItem(THEME_KEY), "dark");
  assert.equal(mgr.toggle(), "light");
  assert.equal(root.classList.contains("dark"), false);
  assert.equal(storage.getItem(THEME_KEY), "light");
});

test("초기 판정만으로는 저장하지 않는다 (사용자가 고르기 전까지 시스템 설정을 따른다)", () => {
  const storage = new FakeStorage();
  createThemeManager({ storage, root: fakeRoot(), matchMedia: mediaDark(true) });
  assert.equal(storage.getItem(THEME_KEY), null);
});

test("저장소가 실패해도 테마 전환은 동작한다", () => {
  const root = fakeRoot();
  const mgr = createThemeManager({ storage: new FakeStorage({}, { failing: true }), root, matchMedia: mediaDark(false) });
  assert.doesNotThrow(() => mgr.toggle());
  assert.equal(mgr.current(), "dark");
  assert.equal(root.classList.contains("dark"), true);
});

test("matchMedia 가 없으면 라이트로 시작한다", () => {
  const mgr = createThemeManager({ storage: new FakeStorage(), root: fakeRoot(), matchMedia: undefined });
  assert.equal(mgr.current(), "light");
});
