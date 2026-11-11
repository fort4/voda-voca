/*
 * 2026-11-05 - voda-voca - 콤보 모델 테스트: 증가/리셋/최대, 노출 기준(2콤보), 마일스톤(5·10·15), 뱃지 바운스 판정, 사운드 큐 정책, 러너 위임 (v2.2)
 * 파일 위치: src/frontend/tests/combo-model.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { COMBO_MIN_VISIBLE, MILESTONES, advanceCombo, badgeView, comboVisible, isMilestone, soundCueFor } from "../js/core/combo-model.js";

const ROOT = new URL("..", import.meta.url).pathname;
const start = { count: 0, max: 0 };

// ---------- advanceCombo ----------

test("advanceCombo: 정답이면 count 가 1 늘고 max 가 따라간다", () => {
  let combo = start;
  for (const expected of [1, 2, 3]) {
    combo = advanceCombo(combo, "correct");
    assert.deepEqual(combo, { count: expected, max: expected });
  }
});

test("advanceCombo: 오답이면 count 만 0 으로 끊기고 max 는 남는다", () => {
  assert.deepEqual(advanceCombo({ count: 4, max: 4 }, "wrong"), { count: 0, max: 4 });
});

test("advanceCombo: 건너뜀도 콤보를 끊는다 (max 유지)", () => {
  assert.deepEqual(advanceCombo({ count: 3, max: 5 }, "skip"), { count: 0, max: 5 });
});

test("advanceCombo: 끊긴 뒤 다시 쌓아도 이전 max 를 넘기 전에는 max 가 그대로다", () => {
  let combo = { count: 0, max: 4 };
  combo = advanceCombo(combo, "correct");
  combo = advanceCombo(combo, "correct");
  assert.deepEqual(combo, { count: 2, max: 4 });
  for (let i = 0; i < 3; i += 1) combo = advanceCombo(combo, "correct");
  assert.deepEqual(combo, { count: 5, max: 5 });
});

test("advanceCombo: 입력 객체를 바꾸지 않는다 (순수)", () => {
  const input = Object.freeze({ count: 2, max: 2 });
  assert.doesNotThrow(() => advanceCombo(input, "correct"));
  assert.deepEqual(input, { count: 2, max: 2 });
});

test("advanceCombo: 알 수 없는 결과나 깨진 입력은 안전하게 0 으로 본다", () => {
  assert.deepEqual(advanceCombo({ count: 3, max: 3 }, "???"), { count: 0, max: 3 });
  assert.deepEqual(advanceCombo(undefined, "correct"), { count: 1, max: 1 });
  assert.deepEqual(advanceCombo({ count: "x", max: null }, "correct"), { count: 1, max: 1 });
});

// ---------- 노출·마일스톤 ----------

test("콤보는 2 부터 보인다 (결정: 2연속 정답부터 노출)", () => {
  assert.equal(COMBO_MIN_VISIBLE, 2);
  assert.deepEqual([0, 1, 2, 3, 15].map(comboVisible), [false, false, true, true, true]);
});

test("마일스톤은 5·10·15 이다", () => {
  assert.deepEqual([...MILESTONES], [5, 10, 15]);
  assert.deepEqual([0, 1, 4, 5, 6, 9, 10, 14, 15, 16].map(isMilestone), [false, false, false, true, false, false, true, false, true, false]);
});

// ---------- 뱃지 ----------

test("badgeView: 1 이하면 숨기고, 2 이상이면 'N콤보' 라벨을 보인다", () => {
  assert.deepEqual(badgeView(0, 1), { visible: false, bounce: false, milestone: false, label: "" });
  assert.deepEqual(badgeView(1, 2), { visible: true, bounce: true, milestone: false, label: "2콤보" });
});

test("badgeView: 바운스는 직전보다 늘어난 렌더에서만 (관련 없는 재렌더에는 튀지 않는다)", () => {
  assert.equal(badgeView(3, 4).bounce, true);
  assert.equal(badgeView(4, 4).bounce, false, "같은 값으로 다시 그릴 때");
  assert.equal(badgeView(5, 0).bounce, false, "끊겼을 때");
  assert.equal(badgeView(5, 0).visible, false);
});

test("badgeView: 마일스톤에 닿으면 milestone 표시", () => {
  assert.equal(badgeView(4, 5).milestone, true);
  assert.equal(badgeView(5, 5).milestone, true, "다시 그려도 마일스톤 모양은 유지");
  assert.equal(badgeView(5, 6).milestone, false);
});

test("badgeView: 콤보가 처음 2 가 되는 순간(1→2)도 바운스한다", () => {
  assert.equal(badgeView(1, 2).bounce, true);
});

test("badgeView: 깨진 입력은 숨김", () => {
  assert.equal(badgeView(undefined, undefined).visible, false);
  assert.equal(badgeView(null, "x").visible, false);
});

// ---------- 사운드 큐 정책 ----------

const answer = (mode, isCorrect, count) => ({ type: "answer", mode, isCorrect, count });

test("soundCueFor: 퀴즈 정답은 correct, 오답은 wrong", () => {
  assert.equal(soundCueFor(answer("quiz", true, 1)), "correct");
  assert.equal(soundCueFor(answer("quiz", true, 4)), "correct");
  assert.equal(soundCueFor(answer("quiz", false, 0)), "wrong");
});

test("soundCueFor: 마일스톤(5·10·15)에 닿는 정답은 milestone 하나만 (정답음과 겹치지 않는다)", () => {
  for (const count of [5, 10, 15]) assert.equal(soundCueFor(answer("quiz", true, count)), "milestone", String(count));
});

test("soundCueFor: 플래시카드 '알아요'·'헷갈려요' 는 모두 무음 (퀴즈 정답음과 같아 중복 — 2026-11-10)", () => {
  assert.equal(soundCueFor(answer("flashcard", true, 2)), null);
  assert.equal(soundCueFor(answer("flashcard", true, 5)), null);
  assert.equal(soundCueFor(answer("flashcard", false, 0)), null);
});

test("soundCueFor: 완료 팡파레는 정상 완주 + 정답 1개 이상일 때만", () => {
  const complete = (over) => ({ type: "complete", aborted: false, answered: 15, correct: 9, ...over });
  assert.equal(soundCueFor(complete({})), "complete");
  assert.equal(soundCueFor(complete({ correct: 1 })), "complete");
  assert.equal(soundCueFor(complete({ correct: 0 })), null, "전부 틀렸으면 승리 음 없음");
  assert.equal(soundCueFor(complete({ aborted: true })), null, "중단");
  assert.equal(soundCueFor(complete({ answered: 0, correct: 0 })), null, "푼 문항 없음");
});

test("soundCueFor: 모르는 이벤트나 깨진 입력은 무음", () => {
  assert.equal(soundCueFor({ type: "skip" }), null);
  assert.equal(soundCueFor(undefined), null);
  assert.equal(soundCueFor({}), null);
});

// ---------- 러너 위임 ----------

test("세션 러너는 콤보 산술을 combo-model 에 위임한다 (진실의 원천 하나)", () => {
  const runner = readFileSync(`${ROOT}js/core/session-runner.js`, "utf8");
  assert.match(runner, /from "\.\/combo-model\.js"/);
  assert.match(runner, /advanceCombo\(/);
  assert.doesNotMatch(runner, /state\.streak \+ 1/, "직접 계산이 남아 있다");
  assert.doesNotMatch(runner, /Math\.max\(state\.bestStreak/, "직접 계산이 남아 있다");
});
