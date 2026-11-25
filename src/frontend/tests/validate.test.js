/*
 * 2026-11-26 - voda-voca - 입력 검증·포맷 단위 테스트: 서버 제한값과 같은 경계 (72바이트, 닉네임 30자 등), 비밀번호 확인
 * 파일 위치: src/frontend/tests/validate.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { formatKst, formatRetry, utf8ByteLength } from "../js/core/format.js";
import {
  mapFieldErrors,
  nicknameConfirmationMatches,
  passwordConfirmState,
  validateNickname,
  validatePassword,
} from "../js/core/validate.js";

test("validateNickname: 공백 제거 후 2~30자 (로그인 식별자이자 고유한 이름)", () => {
  assert.match(validateNickname("   "), /닉네임을 입력/);
  assert.match(validateNickname("가"), /2자 이상/);
  assert.equal(validateNickname(" ab "), null, "앞뒤 공백을 빼고 2자면 통과");
  assert.equal(validateNickname("가".repeat(30)), null);
  assert.match(validateNickname("가".repeat(31)), /30자 이하/);
});

test("nicknameConfirmationMatches: 탈퇴 최종 확인은 닉네임과 정확히 같아야 한다", () => {
  assert.equal(nicknameConfirmationMatches("학습자", "학습자"), true);
  assert.equal(nicknameConfirmationMatches("  학습자 ", "학습자"), true, "앞뒤 공백만 무시한다");
  assert.equal(nicknameConfirmationMatches("학습", "학습자"), false);
  assert.equal(nicknameConfirmationMatches("Learner", "learner"), false, "대소문자는 구분한다");
});

test("validatePassword: 최소 8자, 72바이트 경계 (한글 24자 = 72바이트)", () => {
  assert.match(validatePassword("1234567"), /8자 이상/);
  assert.equal(validatePassword("12345678"), null);
  assert.equal(validatePassword("가".repeat(24)), null);
  assert.match(validatePassword("가".repeat(25)), /72바이트/);
});

test("mapFieldErrors: 알려진 입력에는 붙이고, 나머지는 _form 으로 모은다", () => {
  const out = mapFieldErrors(
    [
      { field: "email", message: "형식 오류" },
      { field: "unknown", message: "기타" },
      { field: null, message: "모델 오류" },
    ],
    ["email", "password"],
  );
  assert.deepEqual(out, { email: "형식 오류", _form: "기타" });
});

test("utf8ByteLength: 한글 한 글자는 3바이트", () => {
  assert.equal(utf8ByteLength("a"), 1);
  assert.equal(utf8ByteLength("가"), 3);
});

test("formatRetry: 올림한 초, 최소 1초", () => {
  assert.equal(formatRetry(36.1), "약 37초 후 다시 시도할 수 있습니다.");
  assert.equal(formatRetry(0.2), "약 1초 후 다시 시도할 수 있습니다.");
});

test("formatKst: UTC 시각을 한국 시각(+9시간)으로 보여 준다", () => {
  const text = formatKst("2026-11-02T05:30:00.123Z");
  assert.ok(text.includes("14:30"), text);
  assert.equal(formatKst("잘못된 값"), "");
});

test("passwordConfirmState: 비었으면 안내 없음, 같으면 '비밀번호가 동일합니다.', 다르면 불일치", () => {
  assert.deepEqual(passwordConfirmState("longenough1", ""), { kind: "empty", message: "" });
  assert.deepEqual(passwordConfirmState("longenough1", "longenough1"), {
    kind: "match",
    message: "비밀번호가 동일합니다.",
  });
  assert.deepEqual(passwordConfirmState("longenough1", "longenough"), {
    kind: "mismatch",
    message: "비밀번호가 일치하지 않습니다.",
  });
});

test("passwordConfirmState: 비밀번호가 비어 있으면 확인란이 비어 있을 때만 '비어 있음'이고, 확인란만 채우면 불일치", () => {
  assert.equal(passwordConfirmState("", "").kind, "empty");
  assert.equal(passwordConfirmState("", "x").kind, "mismatch");
});

test("passwordConfirmState: 공백도 글자로 비교한다 (앞뒤 공백을 지우지 않는다)", () => {
  assert.equal(passwordConfirmState("abc12345", "abc12345 ").kind, "mismatch");
});

test("이메일 검증 함수는 없다 (닉네임·비밀번호만 받는다)", async () => {
  const mod = await import("../js/core/validate.js");
  assert.equal(mod.validateEmail, undefined);
  assert.equal(mod.normalizeEmail, undefined);
});
