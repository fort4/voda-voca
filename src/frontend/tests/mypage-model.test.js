/*
 * 2026-11-26 - voda-voca - 마이페이지 뷰모델 검사: 계정 정보 표시, 비밀번호 변경 입력 판정, 오류 배치 (REQ-164)
 * 파일 위치: src/frontend/tests/mypage-model.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { passwordChangeErrors, passwordChangeFailure, profileView } from "../js/core/mypage-model.js";

const ok = { current: "old-password-1", next: "new-password-2", confirm: "new-password-2" };

test("profileView: 닉네임, 첫 글자, 역할, 가입일(한국 날짜)", () => {
  const view = profileView({ nickname: "voca", is_admin: false, created_at: "2026-11-25T16:00:00Z" });
  assert.deepEqual(view, { nickname: "voca", initial: "V", role: "학습자", joined: "2026-11-26" });
  assert.equal(profileView({ nickname: "admin", is_admin: true, created_at: "2026-11-26T00:00:00Z" }).role, "관리자");
});

test("passwordChangeErrors: 모두 맞으면 오류가 없다", () => {
  assert.deepEqual(passwordChangeErrors(ok), {});
});

test("passwordChangeErrors: 빈 칸과 규칙 위반을 칸별로 알린다", () => {
  assert.equal(passwordChangeErrors({ ...ok, current: "" }).current, "현재 비밀번호를 입력해 주세요.");
  assert.match(passwordChangeErrors({ ...ok, next: "short", confirm: "short" }).next, /8자 이상/);
  assert.match(passwordChangeErrors({ ...ok, next: "가".repeat(25), confirm: "가".repeat(25) }).next, /72바이트/);
  assert.equal(passwordChangeErrors({ ...ok, confirm: "other-password" }).confirm, "비밀번호가 일치하지 않습니다.");
  assert.equal(passwordChangeErrors({ ...ok, confirm: "" }).confirm, "새 비밀번호를 한 번 더 입력해 주세요.");
});

test("passwordChangeErrors: 새 비밀번호가 현재와 같으면 막는다", () => {
  const same = { current: "same-password", next: "same-password", confirm: "same-password" };
  assert.equal(passwordChangeErrors(same).next, "현재 비밀번호와 다른 비밀번호를 입력해 주세요.");
});

test("passwordChangeFailure: 서버 오류를 입력 칸이나 상단 배너에 배치한다", () => {
  assert.deepEqual(
    passwordChangeFailure({ status: 400, code: "CURRENT_PASSWORD_MISMATCH", detail: "현재 비밀번호가 올바르지 않습니다." }),
    { current: "현재 비밀번호가 올바르지 않습니다." },
  );
  assert.deepEqual(
    passwordChangeFailure({ status: 422, fields: [{ field: "new_password_confirm", message: "비밀번호가 일치하지 않습니다." }] }),
    { confirm: "비밀번호가 일치하지 않습니다." },
  );
  assert.deepEqual(passwordChangeFailure({ status: 422, fields: [{ field: "new_password", message: "짧다" }] }), { next: "짧다" });
  assert.deepEqual(passwordChangeFailure({ status: 429, detail: "시도가 너무 많습니다.", retryAfter: 42 }), {
    banner: "시도가 너무 많습니다. (42초 뒤에 다시 시도)",
  });
  assert.deepEqual(passwordChangeFailure({ status: 0, detail: "인터넷 연결을 확인해 주세요." }), { banner: "인터넷 연결을 확인해 주세요." });
});
