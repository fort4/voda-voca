/*
 * 2026-11-02 - voda-voca - 검색 파이프라인 단위 테스트: 300ms 디바운스, 중복 검색어 억제, 요청 취소, 오래된 응답 버림 (가짜 타이머)
 * 파일 위치: src/frontend/tests/search.test.js
 */

import { test, mock } from "node:test";
import assert from "node:assert/strict";
import { createSearch } from "../js/core/search.js";

const settle = () => new Promise((resolve) => setImmediate(resolve));

/** 외부에서 resolve/reject 할 수 있는 요청을 만든다. */
function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

/** @param {import("node:test").TestContext} t */
function fakeTimers(t) {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  return t.mock.timers;
}

test("디바운스: 연속 입력은 마지막 값으로 한 번만 요청한다 (300ms)", (t) => {
  const timers = fakeTimers(t);
  const calls = [];
  const search = createSearch({
    run: (query) => {
      calls.push(query);
      return new Promise(() => {});
    },
    onLoading: () => {},
    onResult: () => {},
    onError: () => {},
  });
  search.setQuery("a");
  timers.tick(100);
  search.setQuery("ap");
  timers.tick(200);
  assert.deepEqual(calls, [], "300ms 가 지나기 전에는 요청하지 않는다");
  search.setQuery("apple ");
  timers.tick(299);
  assert.deepEqual(calls, []);
  timers.tick(1);
  assert.deepEqual(calls, ["apple"], "공백은 잘라 보내고 한 번만 보낸다");
});

test("같은 검색어가 연속으로 오면 다시 보내지 않는다", async (t) => {
  const timers = fakeTimers(t);
  let count = 0;
  const search = createSearch({
    run: () => {
      count += 1;
      return Promise.resolve({ items: [] });
    },
    onLoading: () => {},
    onResult: () => {},
    onError: () => {},
  });
  search.setQuery("ap");
  timers.tick(300);
  await settle();
  search.setQuery("ap");
  timers.tick(300);
  await settle();
  assert.equal(count, 1);
});

test("새 검색을 보내면 이전 요청의 AbortSignal 을 취소한다", (t) => {
  const timers = fakeTimers(t);
  const signals = [];
  const search = createSearch({
    run: (_query, signal) => {
      signals.push(signal);
      return new Promise(() => {});
    },
    onLoading: () => {},
    onResult: () => {},
    onError: () => {},
  });
  search.setQuery("a");
  timers.tick(300);
  search.setQuery("ab");
  timers.tick(300);
  assert.equal(signals.length, 2);
  assert.equal(signals[0].aborted, true);
  assert.equal(signals[1].aborted, false);
});

test("늦게 도착한 옛 응답은 버린다 (증가 번호 기준)", async (t) => {
  const timers = fakeTimers(t);
  const first = deferred();
  const second = deferred();
  const queue = [first, second];
  const shown = [];
  const search = createSearch({
    run: () => queue.shift().promise,
    onLoading: () => {},
    onResult: (data, query) => shown.push([query, data]),
    onError: () => {},
  });
  search.setQuery("a");
  timers.tick(300);
  search.setQuery("ab");
  timers.tick(300);
  second.resolve({ items: ["ab"] });
  await settle();
  first.resolve({ items: ["a"] }); // 취소가 늦어도 옛 응답은 화면에 나오지 않는다
  await settle();
  assert.deepEqual(shown, [["ab", { items: ["ab"] }]]);
});

test("취소로 생긴 AbortError 는 오류로 보고하지 않는다", async (t) => {
  const timers = fakeTimers(t);
  const errors = [];
  const search = createSearch({
    run: (_query, signal) =>
      new Promise((_resolve, reject) => {
        signal.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
      }),
    onLoading: () => {},
    onResult: () => {},
    onError: (error) => errors.push(error),
  });
  search.setQuery("a");
  timers.tick(300);
  search.setQuery("ab");
  timers.tick(300);
  await settle();
  assert.equal(errors.length, 0);
});

test("flush 는 디바운스를 건너뛰고, cancel 은 대기 중 검색과 진행 중 요청을 멈춘다", async (t) => {
  const timers = fakeTimers(t);
  const calls = [];
  const search = createSearch({
    run: (query, signal) => {
      calls.push({ query, signal });
      return new Promise(() => {});
    },
    onLoading: () => {},
    onResult: () => {},
    onError: () => {},
  });
  search.flush("  사과 ");
  assert.deepEqual(calls.map((c) => c.query), ["사과"]);
  search.setQuery("사과나무");
  search.cancel();
  timers.tick(500);
  assert.equal(calls.length, 1, "취소한 대기 검색은 실행되지 않는다");
  assert.equal(calls[0].signal.aborted, true, "진행 중 요청은 취소된다");
});
