/*
 * 2026-11-03 - voda-voca - 플래시카드 전체 로딩 단위 테스트: 한도를 넘는 세트 이어 받기, 빈 응답, 상한 도달 (이슈 #9)
 * 파일 위치: src/frontend/tests/flashcard-load.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { loadAllCards } from "../js/core/flashcard-load.js";

/** 서버처럼 offset·limit 으로 자르는 가짜 fetchPage. 호출 기록을 calls 에 남긴다. */
function fakeServer(total) {
  const all = Array.from({ length: total }, (_, i) => ({ term: `w${i}` }));
  const calls = [];
  const fetchPage = async ({ limit, offset }) => {
    calls.push({ limit, offset });
    return { items: all.slice(offset, offset + limit), total };
  };
  return { fetchPage, calls, all };
}

test("loadAllCards: 한도를 넘는 세트(1,200장)를 빠짐없이, 겹침 없이 모은다", async () => {
  const server = fakeServer(1200);
  const result = await loadAllCards(server.fetchPage, { pageSize: 500 });
  assert.equal(result.items.length, 1200);
  assert.deepEqual(result.items, server.all, "서버 순서 그대로여야 한다");
  assert.equal(result.total, 1200);
  assert.equal(result.truncated, false);
  assert.deepEqual(server.calls.map((c) => c.offset), [0, 500, 1000]);
});

test("loadAllCards: 한도 이하면 한 번만 요청한다", async () => {
  const server = fakeServer(120);
  const result = await loadAllCards(server.fetchPage, { pageSize: 500 });
  assert.equal(result.items.length, 120);
  assert.equal(server.calls.length, 1);
});

test("loadAllCards: 정확히 페이지 크기만큼이면 빈 페이지를 더 요청하지 않는다", async () => {
  const server = fakeServer(1000);
  await loadAllCards(server.fetchPage, { pageSize: 500 });
  assert.equal(server.calls.length, 2);
});

test("loadAllCards: 카드가 없으면 빈 결과를 돌려준다", async () => {
  const server = fakeServer(0);
  const result = await loadAllCards(server.fetchPage);
  assert.deepEqual(result, { items: [], total: 0, truncated: false });
});

test("loadAllCards: 받는 도중 단어가 삭제되어 빈 응답이 오면 무한 반복하지 않고 끝낸다", async () => {
  let call = 0;
  const fetchPage = async () => {
    call += 1;
    return call === 1 ? { items: [{ term: "a" }, { term: "b" }], total: 5 } : { items: [], total: 3 };
  };
  const result = await loadAllCards(fetchPage, { pageSize: 2 });
  assert.equal(result.items.length, 2);
  assert.equal(call, 2);
  assert.equal(result.truncated, false, "빈 응답은 상한 도달이 아니다");
});

test("loadAllCards: maxPages 에 막히면 truncated 로 알린다", async () => {
  const server = fakeServer(100);
  const result = await loadAllCards(server.fetchPage, { pageSize: 10, maxPages: 3 });
  assert.equal(result.items.length, 30);
  assert.equal(result.total, 100);
  assert.equal(result.truncated, true);
});

test("loadAllCards: 요청 실패는 그대로 던진다 (화면이 오류 안내를 보여 준다)", async () => {
  const fetchPage = async () => {
    throw new Error("boom");
  };
  await assert.rejects(loadAllCards(fetchPage), /boom/);
});
