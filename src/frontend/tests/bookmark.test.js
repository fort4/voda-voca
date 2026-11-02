/*
 * 2026-11-02 - voda-voca - 북마크 큐 단위 테스트: 즉시 전환, 요청 중 연타 합치기, 실패 시 되돌림, 초기 상태 보존 (REQ-017)
 * 파일 위치: src/frontend/tests/bookmark.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { createBookmarkQueue } from "../js/core/bookmark.js";

const settle = () => new Promise((resolve) => setImmediate(resolve));

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

/** 보낸 요청(단어 ID, 목표 상태)을 기록하고, 응답은 테스트가 정한다. */
function makeQueue(responses = []) {
  const sent = [];
  const changes = [];
  const errors = [];
  const queue = createBookmarkQueue({
    send: (wordId, on) => {
      sent.push([wordId, on]);
      return responses.length ? responses.shift().promise : Promise.resolve(null);
    },
    onChange: (wordId, on, pending) => changes.push([wordId, on, pending]),
    onError: (wordId, error, attempted) => errors.push([wordId, error, attempted]),
  });
  return { queue, sent, changes, errors };
}

test("init 은 서버 상태를 등록하고, 이미 진행 중인 항목은 덮어쓰지 않는다", () => {
  const { queue } = makeQueue();
  queue.init(1, false);
  assert.deepEqual(queue.getState(1), { bookmarked: false, pending: false });
  queue.init(1, true);
  assert.equal(queue.getState(1).bookmarked, false, "이미 있는 항목은 그대로");
  assert.equal(queue.getState(99), null);
});

test("toggle 은 즉시 상태를 바꾸고 PUT 을 보낸다 (낙관적 갱신)", async () => {
  const pending = deferred();
  const { queue, sent, changes } = makeQueue([pending]);
  queue.init(7, false);
  assert.equal(queue.toggle(7), true);
  assert.deepEqual(changes[0], [7, true, true], "전송 전에 화면이 먼저 바뀐다");
  assert.deepEqual(sent, [[7, true]]);
  pending.resolve(null);
  await settle();
  assert.deepEqual(queue.getState(7), { bookmarked: true, pending: false });
  assert.deepEqual(changes.at(-1), [7, true, false]);
});

test("요청 중 연타하면 중간 상태는 보내지 않고 최종 상태만 한 번 더 맞춘다", async () => {
  const first = deferred();
  const { queue, sent } = makeQueue([first]);
  queue.init(3, false);
  queue.toggle(3); // true, PUT 진행 중
  queue.toggle(3); // false (버퍼)
  first.resolve(null);
  await settle();
  assert.deepEqual(sent, [[3, true], [3, false]], "PUT 뒤에 최종 상태인 DELETE 한 번만 보낸다");
  assert.equal(queue.getState(3).bookmarked, false);
  assert.equal(queue.getState(3).pending, false);
});

test("연타 끝의 상태가 서버와 같으면 추가 요청을 보내지 않는다", async () => {
  const first = deferred();
  const { queue, sent } = makeQueue([first]);
  queue.init(4, false);
  queue.toggle(4); // true, PUT 진행 중
  queue.toggle(4); // false
  queue.toggle(4); // true (서버 상태 false 와 달라짐, 하지만 PUT 결과와 같음)
  first.resolve(null);
  await settle();
  assert.deepEqual(sent, [[4, true]], "최종 상태가 PUT 결과와 같으므로 한 번만 보낸다");
});

test("실패하면 서버 상태로 되돌리고 오류를 알린다", async () => {
  const failing = deferred();
  const { queue, changes, errors } = makeQueue([failing]);
  queue.init(5, false);
  queue.toggle(5);
  const error = new Error("network");
  failing.reject(error);
  await settle();
  assert.equal(queue.getState(5).bookmarked, false, "서버 상태(해제)로 되돌아간다");
  assert.equal(queue.getState(5).pending, false);
  assert.deepEqual(changes.at(-1), [5, false, false]);
  assert.equal(errors.length, 1);
  assert.equal(errors[0][1], error);
  assert.equal(errors[0][2], true, "시도했던 목표 상태를 함께 넘긴다");
});

test("존재하지 않는 단어 토글은 오류를 던진다", () => {
  const { queue } = makeQueue();
  assert.throws(() => queue.toggle(12345), /등록되지 않은/);
});

test("clear 는 모든 상태를 지운다", () => {
  const { queue } = makeQueue();
  queue.init(1, true);
  queue.clear();
  assert.equal(queue.getState(1), null);
});
