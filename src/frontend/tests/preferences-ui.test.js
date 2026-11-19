/*
 * 2026-11-11 - voda-voca - 환경 설정 UI 배선·모션 테스트: 헤더 버튼 제거, 계정 메뉴 항목, 모달 구조, 설정 모달 등장 모션 정돈
 * 파일 위치: src/frontend/tests/preferences-ui.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const ROOT = new URL("..", import.meta.url).pathname;
const read = (path) => readFileSync(join(ROOT, path), "utf8");
const app = read("js/app.js");
const html = read("index.html");
const modal = read("js/views/preferences-modal.js");
const css = read("css/app.css");

test("헤더에는 효과음·다크 모드 버튼이 없다 (환경 설정으로 옮겼다)", () => {
  assert.doesNotMatch(html, /id="sound-toggle"|id="theme-toggle"/);
  assert.doesNotMatch(app, /sound-toggle|theme-toggle|function initSound/);
});

test("계정 메뉴: 학습 설정(book-open) → 환경 설정(settings) → 로그아웃 순서이고, 톱니바퀴는 환경 설정만 쓴다", () => {
  assert.match(app, /menuItem\("book-open", "학습 설정", openSettingsFromMenu\)/);
  assert.match(app, /menuItem\("settings", "환경 설정", openPreferencesFromMenu\)/);
  const i = (s) => app.indexOf(s);
  assert.ok(i('"학습 설정"') < i('"환경 설정"') && i('"환경 설정"') < i('"로그아웃"'));
  assert.match(app, /function openPreferencesFromMenu\(\)[\s\S]*?closeAccountMenu\(\);[\s\S]*?openPreferencesModal\(/);
});

test("환경 설정 모달: SweetAlert2 로 열고 스위치(role=switch)로 효과음·테마를 바꾸며 닫을 때 구독을 해제한다", () => {
  assert.match(modal, /Swal\.fire\(/);
  assert.match(modal, /title: "환경 설정"/);
  assert.match(modal, /confirmButtonText: "닫기"/);
  assert.match(modal, /role: "switch"/);
  assert.match(modal, /"aria-checked"/);
  assert.match(modal, /toggleMute\(\)/);
  assert.match(modal, /themeManager\.toggle\(\)/);
  assert.match(modal, /willClose[\s\S]*?unsubscribe/);
  assert.match(modal, /min-h-\[44px\]/, "터치 높이 44px 이상");
});

test("모달 등장: 튀는 scale 오버슈트 대신 짧은 페이드와 작은 이동만 쓴다", () => {
  assert.match(css, /\.swal2-popup\.swal2-show:not\(\.voda-toast\)\s*\{[^}]*animation:\s*voda-modal-in/);
  assert.match(css, /\.swal2-popup\.swal2-hide:not\(\.voda-toast\)\s*\{[^}]*animation:\s*voda-modal-out/);
  const frames = css.match(/@keyframes voda-modal-in\s*\{[\s\S]*?\n\}/)[0];
  const scales = [...frames.matchAll(/scale\(([\d.]+)\)/g)].map((m) => Number(m[1]));
  assert.ok(scales.every((s) => s <= 1), "1 을 넘는 scale 은 통통 튀는 느낌을 만든다");
  assert.match(css, /@keyframes voda-modal-out/);
});

test("모달 등장: 토스트 모션은 건드리지 않고, 동작 줄이기에서는 끈다", () => {
  assert.doesNotMatch(css, /\.swal2-popup\.swal2-show\s*\{[^}]*voda-modal-in/, "토스트까지 덮지 않는다");
  assert.match(css, /prefers-reduced-motion: reduce\)[\s\S]*?swal2-popup[\s\S]*?animation:\s*none/);
});

/** renderUserbar 의 로그인 상태(if)와 로그아웃 상태(else) 본문을 나눈다. */
function userbarBranches() {
  const body = app.slice(app.indexOf("function renderUserbar()"), app.indexOf("function initialOf"));
  const at = body.indexOf("} else {");
  return { loggedIn: body.slice(0, at), loggedOut: body.slice(at) };
}

test("로그인 전 헤더: 다크 모드 버튼이 로그인 링크의 왼쪽(앞)에 있다", () => {
  const { loggedOut } = userbarBranches();
  const toggle = loggedOut.indexOf("themeToggleButton()");
  const login = loggedOut.indexOf('href: "#/login"');
  assert.ok(toggle >= 0, "로그인 전 헤더에 다크 모드 버튼이 있다");
  assert.ok(login > toggle, "버튼이 로그인 링크보다 앞(왼쪽)이다");
});

test("로그인 후 헤더에는 다크 모드 버튼을 따로 두지 않는다 (계정 메뉴의 환경 설정을 쓴다)", () => {
  assert.doesNotMatch(userbarBranches().loggedIn, /themeToggleButton/);
});

test("다크 모드 버튼: 44px 아이콘 버튼이고 라벨·툴팁을 갖고, 누르면 테마를 바꾼 뒤 헤더를 다시 그린다", () => {
  const fn = app.slice(app.indexOf("function themeToggleButton()"), app.indexOf("/** @param {string} nickname"));
  assert.ok(fn.length > 0, "themeToggleButton 이 정의되어 있다");
  assert.match(fn, /themeToggleView\(themeManager\.current\(\)\)/);
  assert.match(fn, /btn-icon/);
  assert.match(fn, /"aria-label": view\.label/);
  assert.match(fn, /title: view\.label/);
  assert.match(fn, /themeManager\.toggle\(\)[\s\S]*?renderUserbar\(\)/);
  assert.match(fn, /icon\(view\.icon/);
});
