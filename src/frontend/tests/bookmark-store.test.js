/*
 * 2026-11-10 - voda-voca - 세션 북마크 저장소 테스트: 문항에서 초기 상태 채우기, 낙관적 토글·롤백, 중복 요청 차단, 구독 알림
 * 파일 위치: src/frontend/tests/bookmark-store.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";

import { createBookmarkStore } from "../js/core/bookmark-store.js";

/** 호출을 기록하는 가짜 api. fail 이 true 면 거부한다. gate 가 있으면 그 Promise 가 풀릴 때까지 응답을 미룬다. */
function fakeApi({ fail = false, gate = null } = {}) {
  const calls = [];
  const api = async (path, options = {}) => {
    calls.push({ path, method: options.method });
    if (gate) await gate;
    if (fail) throw new Error("network");
    return null;
  };
  return { api, calls };
}

const items = [
  { word_id: 1, bookmarked: true },
  { word_id: 2, bookmarked: false },
  { word_id: 3 }, // 옛 응답: 필드 없음 → false
];

test("seed: 문항의 bookmarked 로 초기 상태를 채운다 (없으면 false)", () => {
  const store = createBookmarkStore({ api: fakeApi().api });
  store.seed(items);
  assert.equal(store.isBookmarked(1), true);
  assert.equal(store.isBookmarked(2), false);
  assert.equal(store.isBookmarked(3), false);
  assert.equal(store.isBookmarked(999), false);
});

test("seed: 이미 아는 단어는 덮어쓰지 않는다 (화면이 다시 그려져도 사용자의 토글이 유지된다)", async () => {
  const store = createBookmarkStore({ api: fakeApi().api });
  store.seed(items);
  await store.toggle(2); // false → true
  store.seed(items); // 서버가 준 옛 값(false)으로 되돌리면 안 된다
  assert.equal(store.isBookmarked(2), true);
});

test("toggle: 꺼져 있으면 PUT, 켜져 있으면 DELETE 를 보내고 상태를 뒤집는다", async () => {
  const { api, calls } = fakeApi();
  const store = createBookmarkStore({ api });
  store.seed(items);
  assert.equal(await store.toggle(2), true);
  assert.equal(await store.toggle(1), false);
  assert.deepEqual(calls, [
    { path: "/bookmarks/2", method: "PUT" },
    { path: "/bookmarks/1", method: "DELETE" },
  ]);
  assert.equal(store.isBookmarked(2), true);
  assert.equal(store.isBookmarked(1), false);
});

test("toggle: 응답을 기다리는 동안 이미 새 상태를 보여 준다 (낙관적 갱신)", async () => {
  let release;
  const gate = new Promise((resolve) => (release = resolve));
  const store = createBookmarkStore({ api: fakeApi({ gate }).api });
  store.seed(items);
  const pending = store.toggle(2);
  assert.equal(store.isBookmarked(2), true);
  assert.equal(store.isPending(2), true);
  release();
  await pending;
  assert.equal(store.isPending(2), false);
});

test("toggle: 요청이 실패하면 원래 상태로 되돌리고 오류를 다시 던진다", async () => {
  const store = createBookmarkStore({ api: fakeApi({ fail: true }).api });
  store.seed(items);
  await assert.rejects(store.toggle(2), /network/);
  assert.equal(store.isBookmarked(2), false);
  assert.equal(store.isPending(2), false);
});

test("toggle: 같은 단어의 요청이 진행 중이면 두 번째 호출은 무시한다 (연타 방지)", async () => {
  let release;
  const gate = new Promise((resolve) => (release = resolve));
  const { api, calls } = fakeApi({ gate });
  const store = createBookmarkStore({ api });
  store.seed(items);
  const first = store.toggle(2);
  const second = await store.toggle(2);
  assert.equal(second, true, "진행 중인 값을 그대로 돌려준다");
  release();
  await first;
  assert.equal(calls.length, 1);
});

test("subscribe: 변경(낙관적 갱신·롤백)마다 알리고, 해제하면 더 알리지 않는다", async () => {
  const store = createBookmarkStore({ api: fakeApi({ fail: true }).api });
  store.seed(items);
  const seen = [];
  const off = store.subscribe((wordId, on) => seen.push([wordId, on]));
  await assert.rejects(store.toggle(2));
  assert.deepEqual(seen, [[2, true], [2, false]]);
  off();
  await assert.rejects(store.toggle(2));
  assert.equal(seen.length, 2);
});
