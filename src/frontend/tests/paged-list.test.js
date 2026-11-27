/*
 * 2026-11-27 - voda-voca - 복습함 페이징 단위 테스트: 쪽 계산, 목록만 바꿔 넣기, 늦은 응답·실패·쪽 초과 처리 (REQ-018, REQ-129)
 * 파일 위치: src/frontend/tests/paged-list.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { REVIEW_PAGE_SIZE, createPagedList, pagerModel } from "../js/core/paged-list.js";

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), "utf8");

/** total 개 목록의 page 번째 응답을 만든다. 항목은 1부터 매긴 번호다. */
const pageOf = (total, page, size = 10) => ({
  items: Array.from({ length: Math.max(0, Math.min(size, total - (page - 1) * size)) }, (_, i) => (page - 1) * size + i + 1),
  total,
});

/** 요청 기록과 응답 시점을 테스트가 정하는 가짜 서버 */
function fakeServer() {
  const calls = [];
  const fetchPage = (page) => new Promise((resolve, reject) => calls.push({ page, resolve, reject }));
  return { calls, fetchPage };
}

function setup(total = 23) {
  const server = fakeServer();
  const events = [];
  const list = createPagedList({
    first: pageOf(total, 1),
    fetchPage: server.fetchPage,
    onChange: (change) => events.push({ type: "change", ...change }),
    onError: (error) => events.push({ type: "error", error }),
  });
  return { list, events, calls: server.calls };
}

test("복습함은 10개씩 보인다", () => {
  assert.equal(REVIEW_PAGE_SIZE, 10);
});

test("페이지 버튼: 10개 이하이면 보이지 않는다", () => {
  assert.equal(pagerModel({ page: 1, total: 0 }).show, false);
  assert.equal(pagerModel({ page: 1, total: 10 }).show, false);
  assert.equal(pagerModel({ page: 1, total: 11 }).show, true);
});

test("페이지 버튼: 첫 쪽은 이전이, 마지막 쪽은 다음이 잠긴다", () => {
  assert.deepEqual(pagerModel({ page: 1, total: 23 }), { show: true, label: "1 / 3", prevDisabled: true, nextDisabled: false });
  assert.deepEqual(pagerModel({ page: 2, total: 23 }), { show: true, label: "2 / 3", prevDisabled: false, nextDisabled: false });
  assert.deepEqual(pagerModel({ page: 3, total: 23 }), { show: true, label: "3 / 3", prevDisabled: false, nextDisabled: true });
});

test("페이지 버튼: 불러오는 중에는 둘 다 잠긴다", () => {
  const model = pagerModel({ page: 2, total: 23, busy: true });
  assert.equal(model.prevDisabled, true);
  assert.equal(model.nextDisabled, true);
});

test("처음에는 받은 첫 쪽을 그대로 갖고 서버를 부르지 않는다", () => {
  const { list, calls } = setup();
  assert.deepEqual(list.state, { items: pageOf(23, 1).items, total: 23, page: 1, busy: false });
  assert.equal(calls.length, 0);
});

test("다음 쪽은 목록을 덧붙이지 않고 바꿔 넣는다", async () => {
  const { list, events, calls } = setup();
  const done = list.goTo(2);
  assert.equal(list.state.busy, true);
  assert.deepEqual(list.state.items, pageOf(23, 1).items, "불러오는 동안은 기존 목록");
  assert.equal(calls[0].page, 2);
  calls[0].resolve(pageOf(23, 2));
  await done;
  assert.deepEqual(list.state, { items: pageOf(23, 2).items, total: 23, page: 2, busy: false });
  assert.deepEqual(events.map((e) => [e.type, e.moved, e.totalChanged]), [["change", false, false], ["change", true, false]]);
});

test("불러오는 중의 연타는 무시해 응답이 뒤섞이지 않는다", async () => {
  const { list, calls } = setup();
  const done = list.goTo(2);
  await list.goTo(3);
  assert.equal(calls.length, 1);
  calls[0].resolve(pageOf(23, 2));
  await done;
  assert.equal(list.state.page, 2);
});

test("없는 쪽과 지금 쪽은 요청하지 않는다", async () => {
  const { list, calls } = setup();
  for (const page of [0, 1, 4]) await list.goTo(page);
  assert.equal(calls.length, 0);
});

test("실패하면 보던 쪽을 유지하고 알린 뒤 다시 누를 수 있다", async () => {
  const { list, events, calls } = setup();
  const done = list.goTo(2);
  const error = new Error("offline");
  calls[0].reject(error);
  await done;
  assert.deepEqual(list.state, { items: pageOf(23, 1).items, total: 23, page: 1, busy: false });
  assert.equal(events.at(-2).type, "change", "잠금을 풀어 다시 그린다");
  assert.deepEqual(events.at(-1), { type: "error", error });
  list.goTo(2);
  assert.equal(calls.length, 2);
});

test("그 사이 목록이 줄어 요청한 쪽이 없으면 마지막 쪽을 받는다", async () => {
  const { list, events, calls } = setup(23);
  const done = list.goTo(3);
  calls[0].resolve(pageOf(15, 3));
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(calls[1].page, 2);
  calls[1].resolve(pageOf(15, 2));
  await done;
  assert.deepEqual(list.state, { items: pageOf(15, 2).items, total: 15, page: 2, busy: false });
  assert.equal(events.at(-1).totalChanged, true);
});

test("목록이 모두 비면 1쪽의 빈 목록이 된다", async () => {
  const { list, calls } = setup(23);
  const done = list.goTo(2);
  calls[0].resolve(pageOf(0, 2));
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(calls[1].page, 1);
  calls[1].resolve(pageOf(0, 1));
  await done;
  assert.deepEqual(list.state, { items: [], total: 0, page: 1, busy: false });
});

test("화면을 떠난 뒤 도착한 응답과 실패는 알리지 않는다", async () => {
  for (const settle of [(call) => call.resolve(pageOf(23, 2)), (call) => call.reject(new Error("late"))]) {
    const { list, events, calls } = setup();
    const done = list.goTo(2);
    const before = events.length;
    list.dispose();
    settle(calls[0]);
    await done;
    assert.equal(events.length, before);
  }
});

test("복습함 화면은 10개씩 받고 더 보기 대신 이전·다음을 둔다", () => {
  const view = read("js/views/review-view.js");
  assert.match(view, /createPagedList\(/);
  assert.match(view, /pagerModel\(/);
  assert.match(view, /size: REVIEW_PAGE_SIZE/);
  assert.doesNotMatch(view, /더 보기|PAGE_SIZE = 20/);
  assert.match(view, /icon\("chevron-left"/);
  assert.match(view, /icon\("chevron-right"/);
});

test("복습함 페이지 버튼은 aria-disabled 로 잠가 포커스를 지키고, 쪽 표시를 알린다", () => {
  const view = read("js/views/review-view.js");
  assert.match(view, /setAttribute\("aria-disabled", String\(/);
  assert.match(view, /"aria-live": "polite"/);
  const css = read("css/app.css");
  assert.match(css, /\.btn\[aria-disabled="true"\]\s*\{[^}]*opacity:\s*0\.5/);
  assert.match(css, /\.btn\[aria-disabled="true"\]:active\s*\{[^}]*transform:\s*none/);
});

test("복습함은 쪽을 옮기면 가려진 목록 첫 줄로 스크롤하고, 실패는 토스트로, 화면을 떠나면 정리한다", () => {
  const view = read("js/views/review-view.js");
  assert.match(view, /scroll-mt-20/);
  assert.match(view, /scrollIntoView\(\{ block: "start" \}\)/);
  assert.match(view, /toast\([^)]*"error"\)/);
  assert.match(view, /\.dispose\(\)/);
});
