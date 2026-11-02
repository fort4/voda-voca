/*
 * 2026-11-02 - voda-voca - 입력 검증·포맷 단위 테스트: 서버 제한값과 같은 경계 (72바이트, 255자, 50자 등)
 * 파일 위치: src/frontend/tests/validate.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { formatKst, formatRetry, utf8ByteLength } from "../js/core/format.js";
import {
  mapFieldErrors,
  validateEmail,
  validateNickname,
  validatePassword,
  validateWordbookDescription,
  validateWordbookName,
} from "../js/core/validate.js";

test("validateEmail: 빈 값, 형식 오류, 정상", () => {
  assert.match(validateEmail("  "), /이메일을 입력/);
  assert.match(validateEmail("not-an-email"), /형식/);
  assert.equal(validateEmail("  user@example.com "), null);
  assert.match(validateEmail(`${"a".repeat(260)}@b.co`), /255자/);
});

test("validatePassword: 최소 8자, 72바이트 경계 (한글 24자 = 72바이트)", () => {
  assert.match(validatePassword("1234567"), /8자 이상/);
  assert.equal(validatePassword("12345678"), null);
  assert.equal(validatePassword("가".repeat(24)), null);
  assert.match(validatePassword("가".repeat(25)), /72바이트/);
});

test("validateNickname / validateWordbookName: 공백만 불가, 길이 제한", () => {
  assert.match(validateNickname("   "), /닉네임을 입력/);
  assert.match(validateNickname("가".repeat(51)), /50자/);
  assert.equal(validateNickname("학습자"), null);
  assert.match(validateWordbookName(""), /단어장 이름/);
  assert.match(validateWordbookName("a".repeat(51)), /50자/);
  assert.equal(validateWordbookName("영어 단어"), null);
});

test("validateWordbookDescription: 200자 제한, 빈 값 허용", () => {
  assert.equal(validateWordbookDescription(""), null);
  assert.match(validateWordbookDescription("a".repeat(201)), /200자/);
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
