/*
 * 2026-11-26 - voda-voca - 닉네임 "중복 확인" 상태 모델 단위 테스트: 확인한 값에만 유효, 고치면 무효, 오래된 응답 무시, 가입 제출 가능 판정 (REQ-158)
 * 파일 위치: src/frontend/tests/availability.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  IDLE,
  canSubmitSignup,
  checkResultText,
  failCheck,
  finishCheck,
  invalidateOnEdit,
  isConfirmed,
  startCheck,
} from "../js/core/availability.js";

test("처음에는 확인하지 않은 상태(idle)이고 확인된 것으로 보지 않는다", () => {
  assert.equal(IDLE.status, "idle");
  assert.equal(isConfirmed(IDLE, "학습자"), false);
});

test("확인 시작 → 사용 가능이면 그 값에 대해서만 확인된 것이다 (앞뒤 공백은 무시)", () => {
  const checking = startCheck(" 학습자 ");
  assert.equal(checking.status, "checking");
  const done = finishCheck(checking, " 학습자 ", true);
  assert.equal(done.status, "available");
  assert.equal(isConfirmed(done, "학습자"), true);
  assert.equal(isConfirmed(done, "학습자2"), false);
});

test("이미 쓰는 값이면 taken 이고 확인된 것이 아니다", () => {
  const done = finishCheck(startCheck("학습자"), "학습자", false);
  assert.equal(done.status, "taken");
  assert.equal(isConfirmed(done, "학습자"), false);
});

test("확인 뒤 값을 고치면 idle 로 돌아간다 (무효화), 앞뒤 공백만 다르면 유지한다", () => {
  const done = finishCheck(startCheck("학습자"), "학습자", true);
  assert.equal(invalidateOnEdit(done, "학습자 ").status, "available");
  assert.equal(invalidateOnEdit(done, "학습자2"), IDLE);
});

test("확인 중에 값이 바뀌어 도착한 오래된 응답은 무시한다", () => {
  const edited = invalidateOnEdit(startCheck("old-name"), "new-name");
  assert.equal(edited, IDLE);
  assert.equal(finishCheck(edited, "old-name", true), edited, "응답이 늦게 와도 상태를 바꾸지 않는다");
  assert.equal(failCheck(edited, "old-name", "오류"), edited);
});

test("확인 실패(네트워크·429)는 error 상태와 메시지를 담고 확인된 것이 아니다", () => {
  const failed = failCheck(startCheck("학습자"), "학습자", "확인 요청이 너무 많습니다.");
  assert.equal(failed.status, "error");
  assert.equal(failed.message, "확인 요청이 너무 많습니다.");
  assert.equal(isConfirmed(failed, "학습자"), false);
});

test("결과 문구와 색조", () => {
  const ok = finishCheck(startCheck("학습자"), "학습자", true);
  const taken = finishCheck(startCheck("학습자"), "학습자", false);
  const failed = failCheck(startCheck("학습자"), "학습자", "네트워크 오류");
  assert.deepEqual(checkResultText(IDLE), { text: "", tone: "neutral" });
  assert.deepEqual(checkResultText(startCheck("학습자")), { text: "확인하는 중…", tone: "neutral" });
  assert.deepEqual(checkResultText(ok), { text: "사용할 수 있는 닉네임입니다.", tone: "ok" });
  assert.deepEqual(checkResultText(taken), { text: "이미 사용 중인 닉네임입니다.", tone: "bad" });
  assert.deepEqual(checkResultText(failed), { text: "네트워크 오류", tone: "bad" });
});

// --- 가입 제출 가능 판정 ---

const GOOD = { nickname: "학습자", password: "longenough1", confirm: "longenough1" };
const CONFIRMED = finishCheck(startCheck(GOOD.nickname), GOOD.nickname, true);

test("값이 올바르고 닉네임 확인을 마쳤으며 비밀번호가 같으면 제출할 수 있다", () => {
  assert.deepEqual(canSubmitSignup(GOOD, { nicknameState: CONFIRMED }), { ok: true, reason: null });
});

test("닉네임 확인을 안 했거나 값을 바꿨으면 제출할 수 없고 이유를 알려 준다", () => {
  assert.deepEqual(canSubmitSignup(GOOD, { nicknameState: IDLE }), {
    ok: false,
    reason: "닉네임 중복 확인을 해 주세요.",
  });
  assert.equal(canSubmitSignup({ ...GOOD, nickname: "다른이름" }, { nicknameState: CONFIRMED }).ok, false);
});

test("이미 쓰는 닉네임(taken)이면 제출할 수 없다", () => {
  const taken = finishCheck(startCheck(GOOD.nickname), GOOD.nickname, false);
  assert.equal(canSubmitSignup(GOOD, { nicknameState: taken }).ok, false);
});

test("형식이 틀린 값이나 비밀번호 불일치는 확인 여부보다 먼저 이유를 알려 준다", () => {
  assert.match(canSubmitSignup({ ...GOOD, nickname: "가" }, { nicknameState: CONFIRMED }).reason, /2자 이상/);
  assert.match(
    canSubmitSignup({ ...GOOD, password: "short", confirm: "short" }, { nicknameState: CONFIRMED }).reason,
    /8자 이상/,
  );
  assert.deepEqual(canSubmitSignup({ ...GOOD, confirm: "different1" }, { nicknameState: CONFIRMED }), {
    ok: false,
    reason: "비밀번호가 일치하지 않습니다.",
  });
});
