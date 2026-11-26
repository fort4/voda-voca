/*
 * 2026-11-26 - voda-voca - 학습 순위 뷰모델 테스트: 지표 이름과 값 표시, 본인 요약(공개·비공개), 공개 스위치의 저장과 되돌리기 (REQ-172, REQ-173)
 * 파일 위치: src/frontend/tests/ranking-model.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";

import { RANKING_METRICS, createRankingVisibility, rankingModel } from "../js/core/ranking-model.js";

const entry = (rank, nickname, learned, words, days, isMe = false) => ({ rank, nickname, learned_words: learned, week_words: words, week_days: days, is_me: isMe });
const response = (over = {}) => ({
  metric: "learned_words",
  items: [entry(1, "민지", 30, 12, 5), entry(2, "나야", 8, 8, 2, true)],
  total_public: 2,
  me: { public: true, rank: 2, learned_words: 8, week_words: 8, week_days: 2 },
  ...over,
});

test("지표는 서버와 같은 이름 3종이고 기본이 먼저다", () => {
  assert.deepEqual(RANKING_METRICS.map((m) => m.id), ["learned_words", "week_words", "week_days"]);
  for (const metric of RANKING_METRICS) assert.ok(metric.label && metric.description, metric.id);
});

test("순위 줄: 고른 지표를 크게, 나머지 두 지표를 보조 글로 보인다", () => {
  const [first, second] = rankingModel(response()).rows;
  assert.deepEqual(first, { rank: 1, nickname: "민지", isMe: false, valueText: "30개", otherText: "7일 단어 12개 · 7일 학습일 5일" });
  assert.equal(second.isMe, true);

  const byDays = rankingModel(response({ metric: "week_days" }));
  assert.equal(byDays.rows[0].valueText, "5일");
  assert.equal(byDays.rows[0].otherText, "학습 단어 30개 · 7일 단어 12개");
  assert.equal(byDays.description, RANKING_METRICS[2].description);
});

test("공개 중인 본인: 순위와 지표를 알린다", () => {
  const { me } = rankingModel(response());
  assert.equal(me.isPublic, true);
  assert.equal(me.title, "내 순위 2위");
  assert.equal(me.detail, "학습 단어 8개 · 7일 단어 8개 · 7일 학습일 2일");
});

test("비공개인 본인: 순위 대신 비공개와 나만 본다는 안내", () => {
  const { me } = rankingModel(response({ me: { public: false, rank: null, learned_words: 1, week_words: 0, week_days: 0 } }));
  assert.equal(me.isPublic, false);
  assert.equal(me.title, "비공개 상태예요");
  assert.equal(me.detail, "학습 단어 1개 · 7일 단어 0개 · 7일 학습일 0일");
  assert.match(me.hint, /순위표에 나오지 않/);
});

test("공개한 사람이 없으면 비어 있고, 목록보다 많으면 상위만 보인다고 알린다", () => {
  const empty = rankingModel(response({ items: [], total_public: 0 }));
  assert.equal(empty.isEmpty, true);
  assert.equal(empty.limitText, null);
  const many = rankingModel(response({ total_public: 51 }));
  assert.equal(many.totalText, "공개 51명");
  assert.equal(many.limitText, "상위 2명만 보여요");
});

/** 호출을 기록하고, 큐에 넣은 결과를 차례로 돌려주는 가짜 api */
function fakeApi(...results) {
  const calls = [];
  const api = (path, options) => {
    calls.push([path, options?.method ?? "GET", options?.body]);
    const next = results.shift();
    return next instanceof Error ? Promise.reject(next) : Promise.resolve(next);
  };
  return { api, calls };
}

function visibility(...results) {
  const { api, calls } = fakeApi(...results);
  const states = [];
  const store = createRankingVisibility({ api, onChange: (s) => states.push(s) });
  return { store, calls, states, last: () => states.at(-1) };
}

test("공개 스위치: 서버 값을 읽어 보인다", async () => {
  const { store, calls, last } = visibility({ public: true });
  await store.load();
  assert.deepEqual(calls, [["/users/me/ranking-visibility", "GET", undefined]]);
  assert.deepEqual(last(), { value: true, busy: false, failed: false });
});

test("공개 스위치: 먼저 바꾸고 PUT 으로 저장한다", async () => {
  const { store, calls, states, last } = visibility({ public: false }, { public: true });
  await store.load();
  const saved = store.toggle();
  assert.deepEqual(states.at(-1), { value: true, busy: true, failed: false });
  assert.equal(await saved, true);
  assert.deepEqual(calls[1], ["/users/me/ranking-visibility", "PUT", { public: true }]);
  assert.deepEqual(last(), { value: true, busy: false, failed: false });
});

test("공개 스위치: 저장에 실패하면 이전 값으로 되돌린다", async () => {
  const { store, last } = visibility({ public: false }, new Error("서버 오류"));
  await store.load();
  assert.equal(await store.toggle(), false);
  assert.deepEqual(last(), { value: false, busy: false, failed: false });
});

test("공개 스위치: 저장 중에 다시 눌러도 요청은 하나다", async () => {
  const { store, calls } = visibility({ public: false }, { public: true });
  await store.load();
  await Promise.all([store.toggle(), store.toggle()]);
  assert.equal(calls.length, 2);
});

test("공개 스위치: 읽기에 실패하면 알리고, 다시 누르면 읽기만 다시 한다", async () => {
  const { store, calls, last } = visibility(new Error("끊김"), { public: false });
  await store.load();
  assert.deepEqual(last(), { value: null, busy: false, failed: true });
  await store.toggle();
  assert.deepEqual(calls.map((c) => c[1]), ["GET", "GET"], "값을 모르는 상태에서 저장하지 않는다");
  assert.deepEqual(last(), { value: false, busy: false, failed: false });
});
