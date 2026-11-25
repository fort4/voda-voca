/*
 * 2026-11-26 - voda-voca - 마이페이지 배선 검사: 계정 메뉴 항목, 라우트, 변경 폼, 관리자 표시와 탈퇴 숨김 (REQ-159, REQ-164)
 * 파일 위치: src/frontend/tests/mypage-ui.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
const app = read("js/app.js");

test("계정 메뉴: '마이페이지'가 학습 설정보다 위에 있고 /mypage 로 이동한다", () => {
  assert.match(app, /menuItem\("user", "마이페이지", openMyPageFromMenu\)/);
  assert.ok(app.indexOf('"마이페이지"') < app.indexOf('"학습 설정"'));
  assert.match(app, /router\.navigate\("\/mypage"\)/);
  assert.match(app, /mypage:\s*myPageView/);
});

test("계정 메뉴: 관리자는 '관리자'로 표시하고 회원 탈퇴를 보이지 않는다", () => {
  assert.match(app, /user\.is_admin \? "관리자" : "학습자"|profileView\(user\)\.role/);
  assert.match(app, /user\.is_admin \? null : [\s\S]{0,200}"회원 탈퇴"/);
});

test("마이페이지: 현재·새·확인 세 칸이 보기 토글을 쓰고 autocomplete 가 맞다", () => {
  const src = read("js/views/mypage-view.js");
  assert.equal((src.match(/passwordField\(/g) ?? []).length, 3);
  assert.match(src, /autocomplete:\s*"current-password"/);
  assert.equal((src.match(/autocomplete:\s*"new-password"/g) ?? []).length, 2);
});

test("마이페이지: 변경 API 를 PUT 으로 부르고 성공하면 입력을 비운다", () => {
  const src = read("js/views/mypage-view.js");
  assert.match(src, /"\/auth\/me\/password"/);
  assert.match(src, /method:\s*"PUT"/);
  for (const key of ["current_password", "new_password", "new_password_confirm"]) assert.ok(src.includes(key), key);
  assert.match(src, /\.reset\(\)/);
  assert.match(src, /toast\(/);
});

test("마이페이지: 중복 제출을 막고, 확인란 일치 여부를 aria-live 로 알린다", () => {
  const src = read("js/views/mypage-view.js");
  assert.match(src, /submit\.disabled/);
  assert.match(src, /passwordConfirmState\(/);
  assert.match(src, /"aria-live":\s*"polite"/);
});
