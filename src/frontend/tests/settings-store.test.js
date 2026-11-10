/*
 * 2026-11-10 - voda-voca - 학습 설정 저장소 테스트: 사용자별 캐시, 낙관적 변경·롤백, 구독 알림, 동시 로드 합치기 (REQ-147)
 * 파일 위치: src/frontend/tests/settings-store.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";

import { createSettingsStore } from "../js/core/settings-store.js";
import { FALLBACK_SETTINGS } from "../js/core/settings-model.js";

const server = (over = {}) => ({ quiz_count: 10, flashcard_count: 10, daily_goal: 10, options: [10, 20, 30], ...over });

/** 호출을 기록하는 가짜 api. handlers[경로 또는 "METHOD 경로"] 가 응답을 만든다. */
function fakeApi(handlers) {
  const calls = [];
  const api = async (path, options = {}) => {
    calls.push({ path, method: options.method ?? "GET", body: options.body });
    const handler = handlers[`${options.method ?? "GET"} ${path}`];
    if (!handler) throw new Error(`unexpected ${path}`);
    return handler(options);
  };
  return { api, calls };
}

test("초기값은 폴백이다 (불러오기 전에도 화면이 그려진다)", () => {
  const store = createSettingsStore({ api: fakeApi({}).api });
  assert.deepEqual(store.get(), FALLBACK_SETTINGS);
});

test("load: 서버 값을 정규화해 담고, 같은 사용자는 다시 요청하지 않는다", async () => {
  const { api, calls } = fakeApi({ "GET /users/me/settings": () => server({ quiz_count: 20 }) });
  const store = createSettingsStore({ api });
  assert.equal((await store.load(1)).quiz_count, 20);
  assert.equal((await store.load(1)).quiz_count, 20);
  assert.equal(calls.length, 1);
  assert.equal(store.get().quiz_count, 20);
});

test("load: 동시에 불러도 요청은 한 번이다", async () => {
  const { api, calls } = fakeApi({ "GET /users/me/settings": () => server() });
  const store = createSettingsStore({ api });
  await Promise.all([store.load(1), store.load(1)]);
  assert.equal(calls.length, 1);
});

test("load: 사용자가 바뀌면 이전 사용자의 설정을 버리고 다시 받는다", async () => {
  let next = server({ quiz_count: 20 });
  const { api, calls } = fakeApi({ "GET /users/me/settings": () => next });
  const store = createSettingsStore({ api });
  await store.load(1);
  next = server({ quiz_count: 30 });
  assert.equal((await store.load(2)).quiz_count, 30);
  assert.equal(calls.length, 2);
});

test("load: 실패하면 거부하고, 다음 호출에서 다시 시도하며, 값은 폴백으로 남는다", async () => {
  let fail = true;
  const { api, calls } = fakeApi({ "GET /users/me/settings": () => { if (fail) throw new Error("down"); return server({ daily_goal: 30 }); } });
  const store = createSettingsStore({ api });
  await assert.rejects(store.load(1));
  assert.deepEqual(store.get(), FALLBACK_SETTINGS);
  fail = false;
  assert.equal((await store.load(1)).daily_goal, 30);
  assert.equal(calls.length, 2);
});

test("change: 먼저 반영하고(낙관적) PATCH 로 저장하며 구독자에게 알린다", async () => {
  const { api, calls } = fakeApi({ "GET /users/me/settings": () => server(), "PATCH /users/me/settings": () => server() });
  const store = createSettingsStore({ api });
  await store.load(1);
  const seen = [];
  store.subscribe((s) => seen.push(s.daily_goal));
  const pending = store.change("daily_goal", 30);
  assert.equal(store.get().daily_goal, 30, "응답 전에 이미 바뀐다");
  assert.equal(await pending, true);
  assert.deepEqual(calls.at(-1), { path: "/users/me/settings", method: "PATCH", body: { daily_goal: 30 } });
  assert.deepEqual(seen, [30]);
});

test("change: 저장에 실패하면 이전 값으로 되돌리고 false 를 돌려주며 알린다", async () => {
  const { api } = fakeApi({ "GET /users/me/settings": () => server({ quiz_count: 20 }), "PATCH /users/me/settings": () => { throw new Error("500"); } });
  const store = createSettingsStore({ api });
  await store.load(1);
  const seen = [];
  store.subscribe((s) => seen.push(s.quiz_count));
  assert.equal(await store.change("quiz_count", 30), false);
  assert.equal(store.get().quiz_count, 20);
  assert.deepEqual(seen, [30, 20]);
});

test("change: 옵션에 없는 값·같은 값은 요청 없이 true (변경 없음)", async () => {
  const { api, calls } = fakeApi({ "GET /users/me/settings": () => server() });
  const store = createSettingsStore({ api });
  await store.load(1);
  assert.equal(await store.change("quiz_count", 15), true);
  assert.equal(await store.change("quiz_count", 10), true);
  assert.equal(calls.length, 1, "GET 한 번뿐");
});

test("change: 롤백은 그 사이 다른 값으로 바뀌지 않았을 때만 한다", async () => {
  let rejectFirst;
  const first = new Promise((_, reject) => { rejectFirst = reject; });
  let n = 0;
  const { api } = fakeApi({ "GET /users/me/settings": () => server(), "PATCH /users/me/settings": () => (++n === 1 ? first : server()) });
  const store = createSettingsStore({ api });
  await store.load(1);
  const a = store.change("daily_goal", 20);
  const b = store.change("daily_goal", 30);
  rejectFirst(new Error("x"));
  assert.equal(await a, false);
  assert.equal(await b, true);
  assert.equal(store.get().daily_goal, 30, "나중에 고른 값이 유지된다");
});

test("subscribe: 해제하면 더 이상 알리지 않는다. reset 은 폴백으로 되돌리고 알린다", async () => {
  const { api } = fakeApi({ "GET /users/me/settings": () => server({ quiz_count: 20 }) });
  const store = createSettingsStore({ api });
  await store.load(1);
  const seen = [];
  const off = store.subscribe((s) => seen.push(s.quiz_count));
  store.reset();
  assert.deepEqual(seen, [10]);
  off();
  store.reset();
  assert.deepEqual(seen, [10]);
  assert.deepEqual(store.get(), FALLBACK_SETTINGS);
});
