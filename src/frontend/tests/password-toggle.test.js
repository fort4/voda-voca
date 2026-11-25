/*
 * 2026-11-25 - voda-voca - 비밀번호 보기/숨기기 토글 검사: 상태 모델과 로그인·가입 화면 적용, 44px 터치 타깃, 접근성 속성 (로그인·가입 개선)
 * 파일 위치: src/frontend/tests/password-toggle.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { passwordToggleState } from "../js/core/password-toggle.js";

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), "utf8");

test("숨김 상태: 입력은 password, 버튼은 '비밀번호 보기', 눌림 아님, eye 아이콘", () => {
  assert.deepEqual(passwordToggleState(false), {
    type: "password",
    label: "비밀번호 보기",
    pressed: "false",
    iconName: "eye",
  });
});

test("표시 상태: 입력은 text, 버튼은 '비밀번호 숨기기', 눌림, eye-off 아이콘", () => {
  assert.deepEqual(passwordToggleState(true), {
    type: "text",
    label: "비밀번호 숨기기",
    pressed: "true",
    iconName: "eye-off",
  });
});

test("passwordField 는 토글 버튼을 만들고 aria-pressed·aria-label·44px 타깃을 쓴다", () => {
  const src = read("js/core/form.js");
  assert.match(src, /export function passwordField\(/);
  assert.match(src, /passwordToggleState\(/);
  assert.match(src, /aria-pressed/);
  assert.match(src, /aria-label/);
  assert.match(src, /type:\s*"button"/, "토글 버튼이 폼을 제출하면 안 된다");
  assert.match(src, /min-h-\[44px\]/);
  assert.match(src, /min-w-\[44px\]/);
});

test("로그인·가입 화면은 비밀번호 칸에 passwordField 를 쓴다", () => {
  for (const file of ["js/views/login.js", "js/views/signup.js"]) {
    const src = read(file);
    assert.match(src, /passwordField\(/, `${file}: passwordField 사용`);
    assert.doesNotMatch(src, /type:\s*"password"/, `${file}: 일반 field 로 비밀번호를 만들지 않는다`);
  }
});

test("로그인 실패 시 비밀번호를 비워도 다시 숨김 상태로 돌아간다", () => {
  const src = read("js/views/login.js");
  assert.match(src, /password\.hide\(\)/);
});
