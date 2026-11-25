/*
 * 2026-11-25 - voda-voca - 출제 방향·형식 프론트 테스트: 시작 요청, 문제 문구, OX 키, 시작 경로·선택 기억 (VOCA-FR-023, 024)
 * 파일 위치: src/frontend/tests/quiz-variants.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";

import { ACTION, EFFECT, PHASE, initialState, reduce } from "../js/core/session-runner.js";
import { loadQuizOptions, saveQuizOptions, startPath } from "../js/core/home-model.js";
import { DIRECTION_OPTIONS, FORMAT_OPTIONS, questionCopy, sessionKeyAction } from "../js/core/session-view-model.js";

function memoryStorage(initial = {}) {
  const data = { ...initial };
  return { getItem: (k) => data[k] ?? null, setItem: (k, v) => { data[k] = v; }, data };
}

const choiceItem = { question_id: 0, word_id: 1, term: "apple", prompt: "apple", direction: "en_to_ko", format: "choice", options: ["a", "b", "c", "d"], proposed: null };
const koItem = { ...choiceItem, term: null, prompt: "사과", direction: "ko_to_en", options: ["apple", "pear", "kiwi", "plum"] };
const oxItem = { ...choiceItem, format: "ox", options: ["O", "X"], proposed: "사과" };
const oxKoItem = { ...oxItem, term: null, prompt: "사과", direction: "ko_to_en", proposed: "apple" };

function active(item) {
  return { ...initialState(), phase: PHASE.QUESTION_ACTIVE, mode: "quiz", sessionId: 1, items: [item], index: 0 };
}

// --- 시작 요청 ---

test("START: direction·format 을 요청 본문에 싣는다", () => {
  const { state, effects } = reduce(initialState(), { type: ACTION.START, mode: "quiz", direction: "ko_to_en", format: "ox" });
  assert.equal(effects[0].type, EFFECT.CREATE_SESSION);
  assert.equal(effects[0].body.direction, "ko_to_en");
  assert.equal(effects[0].body.format, "ox");
  assert.equal(state.direction, "ko_to_en");
  assert.equal(state.format, "ox");
});

test("START: 값이 없거나 이상하면 영→한 4지선다", () => {
  for (const action of [{ type: ACTION.START }, { type: ACTION.START, direction: "x", format: "short" }]) {
    const { effects } = reduce(initialState(), action);
    assert.equal(effects[0].body.direction, "en_to_ko");
    assert.equal(effects[0].body.format, "choice");
  }
});

test("START: 다시 시작은 직전 방향·형식을 잇는다", () => {
  let state = reduce(initialState(), { type: ACTION.START, direction: "mixed", format: "ox" }).state;
  state = { ...state, phase: PHASE.SESSION_COMPLETE };
  const { effects } = reduce(state, { type: ACTION.START });
  assert.equal(effects[0].body.direction, "mixed");
  assert.equal(effects[0].body.format, "ox");
});

// --- 문제 문구 ---

test("questionCopy: 영→한 4지선다는 단어를 보이고 뜻을 묻는다", () => {
  assert.deepEqual(questionCopy(choiceItem), { hint: "알맞은 뜻을 고르세요", prompt: "apple", proposed: null, isOx: false, labels: ["a", "b", "c", "d"], promptIsKorean: false, proposedIsKorean: true });
});

test("questionCopy: 한→영 4지선다는 뜻을 보이고 단어를 묻는다", () => {
  const copy = questionCopy(koItem);
  assert.equal(copy.hint, "알맞은 단어를 고르세요");
  assert.equal(copy.prompt, "사과");
});

test("questionCopy: OX 는 보기를 제시하고 O/X 를 묻는다", () => {
  const ko = questionCopy(oxItem);
  assert.equal(ko.isOx, true);
  assert.equal(ko.hint, "이 단어의 뜻이 맞을까요?");
  assert.deepEqual([ko.prompt, ko.proposed, ko.labels], ["apple", "사과", ["O", "X"]]);
  const en = questionCopy(oxKoItem);
  assert.equal(en.hint, "이 뜻의 단어가 맞을까요?");
  assert.deepEqual([en.prompt, en.proposed], ["사과", "apple"]);
});

test("questionCopy: 옛 세션(방향·형식·prompt 없음)은 영→한 4지선다로 읽는다", () => {
  const legacy = { question_id: 0, word_id: 1, term: "apple", options: ["a", "b", "c", "d"] };
  const copy = questionCopy(legacy);
  assert.equal(copy.prompt, "apple");
  assert.equal(copy.isOx, false);
});

// --- 키 ---

test("키: OX 는 1·2 와 O·X 로 답하고 3·4 는 무시한다", () => {
  const state = active(oxItem);
  assert.deepEqual(sessionKeyAction("1", state), { type: ACTION.SUBMIT_ANSWER, choiceIndex: 0 });
  assert.deepEqual(sessionKeyAction("2", state), { type: ACTION.SUBMIT_ANSWER, choiceIndex: 1 });
  assert.deepEqual(sessionKeyAction("o", state), { type: ACTION.SUBMIT_ANSWER, choiceIndex: 0 });
  assert.deepEqual(sessionKeyAction("O", state), { type: ACTION.SUBMIT_ANSWER, choiceIndex: 0 });
  assert.deepEqual(sessionKeyAction("x", state), { type: ACTION.SUBMIT_ANSWER, choiceIndex: 1 });
  assert.equal(sessionKeyAction("3", state), null);
  assert.equal(sessionKeyAction("4", state), null);
});

test("키: 4지선다에서 o·x 는 무시한다", () => {
  assert.equal(sessionKeyAction("o", active(choiceItem)), null);
});

test("OX 에서 선지 번호 2 이상은 서버로 보내지 않는다", () => {
  const { effects } = reduce(active(oxItem), { type: ACTION.SUBMIT_ANSWER, choiceIndex: 2 });
  assert.deepEqual(effects, []);
});

// --- 시작 경로와 선택 기억 ---

test("startPath: 기본값이면 쿼리를 늘리지 않는다", () => {
  assert.equal(startPath("quiz"), "/study/session?mode=quiz");
  assert.equal(startPath("quiz", "all", { direction: "en_to_ko", format: "choice" }), "/study/session?mode=quiz");
});

test("startPath: 퀴즈에서 기본이 아닌 방향·형식은 쿼리에 싣는다", () => {
  assert.equal(startPath("quiz", "all", { direction: "ko_to_en", format: "ox" }), "/study/session?mode=quiz&direction=ko_to_en&format=ox");
  assert.equal(startPath("quiz", "due", { direction: "mixed", format: "choice" }), "/study/session?mode=quiz&source=due&direction=mixed");
});

test("startPath: 플래시카드에는 방향·형식을 싣지 않는다", () => {
  assert.equal(startPath("flashcard", "all", { direction: "ko_to_en", format: "ox" }), "/study/session?mode=flashcard");
});

test("선택 기억: 저장·복원, 깨진 값은 기본값", () => {
  const storage = memoryStorage();
  assert.deepEqual(loadQuizOptions(storage), { direction: "en_to_ko", format: "choice" });
  saveQuizOptions(storage, { direction: "mixed", format: "ox" });
  assert.deepEqual(loadQuizOptions(storage), { direction: "mixed", format: "ox" });
  assert.deepEqual(loadQuizOptions(memoryStorage({ "voda.study.quiz-options": "{깨짐" })), { direction: "en_to_ko", format: "choice" });
  assert.deepEqual(loadQuizOptions(memoryStorage({ "voda.study.quiz-options": JSON.stringify({ direction: "x", format: "y" }) })), { direction: "en_to_ko", format: "choice" });
  assert.deepEqual(loadQuizOptions(undefined), { direction: "en_to_ko", format: "choice" });
});

test("선택지 목록: 서버가 받는 값과 같다", () => {
  assert.deepEqual(DIRECTION_OPTIONS.map((o) => o.id), ["en_to_ko", "ko_to_en", "mixed"]);
  assert.deepEqual(FORMAT_OPTIONS.map((o) => o.id), ["choice", "ox"]);
});

// --- OX 글자 비율: 한글은 같은 px 에서 영문보다 커 보이므로 한글 쪽을 낮춘다 ---

test("questionCopy: 한→영 OX 는 문제(뜻)가 한글, 영→한 OX 는 제시 보기(뜻)가 한글이다", () => {
  assert.deepEqual([questionCopy(oxKoItem).promptIsKorean, questionCopy(oxKoItem).proposedIsKorean], [true, false]);
  assert.deepEqual([questionCopy(oxItem).promptIsKorean, questionCopy(oxItem).proposedIsKorean], [false, true]);
});

test("CSS: 한글 쪽은 영문 쪽보다 작은 글자 크기를 쓴다 (OX)", async () => {
  const { readFile } = await import("node:fs/promises");
  const css = await readFile(new URL("../css/app.css", import.meta.url), "utf8");
  const size = (selector) => {
    const rule = css.match(new RegExp(`${selector.replace(/[.]/g, "\\.")}\\s*\\{([^}]*)\\}`));
    assert.ok(rule, `${selector} 규칙이 없다`);
    return rule[1].match(/font-size:\s*([^;]+);/)?.[1].trim();
  };
  assert.equal(size(".session-term--ko"), "var(--fs-heading)");
  assert.equal(size(".session-proposed--en"), "var(--fs-display)");
});

// --- 플래시카드 전환: 이동 없이 사라지고 나타난다 ---

test("CSS: 플래시카드 카드 전환은 투명도만 바꾼다 (이동·회전·확대 없음)", async () => {
  const { readFile } = await import("node:fs/promises");
  const css = await readFile(new URL("../css/app.css", import.meta.url), "utf8");
  for (const name of ["card-exit-known", "card-exit-unsure", "card-enter"]) {
    const block = css.match(new RegExp(`@keyframes ${name}\\s*\\{([\\s\\S]*?)\\n\\}`))?.[1];
    assert.ok(block, `${name} 키프레임이 없다`);
    assert.ok(!/transform/.test(block), `${name} 에 transform 이 있다: ${block}`);
    assert.match(block, /opacity/);
  }
});
