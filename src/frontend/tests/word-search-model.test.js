/*
 * 2026-11-26 - voda-voca - 단어 검색 모델 검사: 검색어 정리, 페이지 이어 붙이기, 늦게 온 응답 버리기, 하단 안내 (REQ-163)
 * 파일 위치: src/frontend/tests/word-search-model.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { SEARCH_MAX_LENGTH, createWordPager, normalizeQuery, pagerFooter } from "../js/core/word-search-model.js";

/** 테스트가 응답 시점을 정하는 가짜 요청. */
function fakeFetch() {
  const calls = [];
  const fetchPage = (params) =>
    new Promise((resolve, reject) => {
      calls.push({ params, resolve, reject });
    });
  return { calls, fetchPage };
}

const reply = (items, total) => ({ items, total });

function setup() {
  const fake = fakeFetch();
  const events = [];
  const pager = createWordPager({ fetchPage: fake.fetchPage, onChange: (event) => events.push(event) });
  return { ...fake, events, pager };
}

test("normalizeQuery: 앞뒤 공백을 없애고 100자에서 자른다", () => {
  assert.equal(SEARCH_MAX_LENGTH, 100);
  assert.equal(normalizeQuery("  apple  "), "apple");
  assert.equal(normalizeQuery("   "), "");
  assert.equal(normalizeQuery(null), "");
  assert.equal(normalizeQuery("a".repeat(150)).length, 100);
});

test("loadMore: 다음 페이지를 요청해 이어 붙인다", async () => {
  const { pager, calls, events } = setup();
  const first = pager.loadMore();
  calls[0].resolve(reply(["a", "b"], 3));
  await first;
  const second = pager.loadMore();
  calls[1].resolve(reply(["c"], 3));
  await second;

  assert.deepEqual(calls.map((c) => c.params), [{ page: 1, query: "" }, { page: 2, query: "" }]);
  assert.deepEqual(pager.state.items, ["a", "b", "c"]);
  assert.deepEqual(events.filter((e) => e.type === "page").map((e) => e.added), [["a", "b"], ["c"]]);
});

test("loadMore: 불러오는 중에는 같은 페이지를 다시 요청하지 않는다", async () => {
  const { pager, calls } = setup();
  const first = pager.loadMore();
  pager.loadMore();
  assert.equal(calls.length, 1);
  calls[0].resolve(reply(["a"], 1));
  await first;
});

test("search: 목록을 비우고 1페이지부터 검색어로 요청한다", async () => {
  const { pager, calls, events } = setup();
  const first = pager.loadMore();
  calls[0].resolve(reply(["a", "b"], 2));
  await first;
  events.length = 0;

  const searched = pager.search("  ban ");
  assert.deepEqual(calls[1].params, { page: 1, query: "ban" });
  assert.deepEqual(pager.state.items, []);
  assert.equal(events[0].type, "reset");
  calls[1].resolve(reply(["banana"], 1));
  await searched;
  assert.deepEqual(pager.state.items, ["banana"]);
});

test("search: 늦게 온 이전 검색의 응답은 버린다", async () => {
  const { pager, calls, events } = setup();
  const old = pager.search("a");
  const latest = pager.search("ab");
  calls[1].resolve(reply(["ab"], 1));
  await latest;
  const count = events.length;
  calls[0].resolve(reply(["a", "ab"], 2));
  await old;

  assert.deepEqual(pager.state.items, ["ab"]);
  assert.equal(pager.state.total, 1);
  assert.equal(events.length, count, "버린 응답은 화면에 알리지 않는다");
});

test("search: 늦게 실패한 이전 검색은 새 검색의 상태를 건드리지 않는다", async () => {
  const { pager, calls } = setup();
  const old = pager.search("a");
  const latest = pager.search("ab");
  calls[0].reject(new Error("old"));
  await old;
  assert.equal(pager.state.error, null);
  assert.equal(pager.state.loading, true, "새 검색은 아직 불러오는 중이다");
  calls[1].resolve(reply(["ab"], 1));
  await latest;
});

test("search: 같은 검색어는 다시 요청하지 않는다", async () => {
  const { pager, calls } = setup();
  const first = pager.search("a");
  pager.search(" a ");
  calls[0].resolve(reply(["a"], 1));
  await first;
  pager.search("a");
  assert.equal(calls.length, 1);
});

test("search: 검색어를 지우면 전체 목록을 다시 요청한다", async () => {
  const { pager, calls } = setup();
  const first = pager.search("a");
  calls[0].resolve(reply(["a"], 1));
  await first;
  pager.search("");
  assert.deepEqual(calls[1].params, { page: 1, query: "" });
});

test("오류: 상태에 남기고, loadMore 로 같은 페이지를 다시 시도한다", async () => {
  const { pager, calls } = setup();
  const failed = pager.search("a");
  calls[0].reject({ detail: "서버 오류" });
  await failed;
  assert.equal(pager.state.error, "서버 오류");

  const retried = pager.loadMore();
  assert.deepEqual(calls[1].params, { page: 1, query: "a" });
  assert.equal(pager.state.error, null);
  calls[1].resolve(reply(["a"], 1));
  await retried;
});

test("pagerFooter: 상태별 하단 안내", () => {
  const base = { query: "", items: [], total: 0, page: 0, loading: false, error: null };
  assert.deepEqual(pagerFooter({ ...base, loading: true }), { kind: "loading", text: "불러오는 중…" });
  assert.deepEqual(pagerFooter({ ...base, error: "서버 오류" }), { kind: "error", text: "서버 오류" });
  assert.deepEqual(pagerFooter({ ...base, page: 1 }), { kind: "done", text: "단어가 없어요." });
  assert.deepEqual(pagerFooter({ ...base, page: 1, query: "zz" }), { kind: "done", text: "'zz' 검색 결과가 없어요." });
  assert.deepEqual(pagerFooter({ ...base, page: 1, items: [1, 2], total: 5 }), { kind: "more", text: "더 보기 (2/5)" });
  assert.deepEqual(pagerFooter({ ...base, page: 1, items: [1, 2], total: 2 }), { kind: "done", text: "전체 2단어" });
  assert.deepEqual(pagerFooter({ ...base, page: 1, query: "a", items: [1], total: 1 }), { kind: "done", text: "검색 결과 1단어" });
});
