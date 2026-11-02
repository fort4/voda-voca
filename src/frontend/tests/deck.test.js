/*
 * 2026-11-02 - voda-voca - 플래시카드 덱 상태 단위 테스트: 경계, 뒤집기 초기화, 셔플 시 현재 카드 유지 (REQ-012, REQ-013)
 * 파일 위치: src/frontend/tests/deck.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { createDeck, shuffled } from "../js/core/deck.js";

const CARDS = ["a", "b", "c", "d", "e"];

/** 항상 같은 값을 주는 난수 (테스트 재현용). */
function seeded(values) {
  let i = 0;
  return () => values[i++ % values.length];
}

test("next/prev 는 경계에서 멈추고 false 를 돌려준다", () => {
  const deck = createDeck(CARDS);
  assert.equal(deck.prev(), false);
  assert.equal(deck.position, 0);
  for (let i = 0; i < 4; i += 1) assert.equal(deck.next(), true);
  assert.equal(deck.atEnd(), true);
  assert.equal(deck.next(), false);
  assert.equal(deck.current(), "e");
});

test("뒤집기 상태는 카드를 옮기면 앞면으로 돌아온다", () => {
  const deck = createDeck(CARDS);
  assert.equal(deck.flip(), true);
  assert.equal(deck.isFlipped(), true);
  deck.next();
  assert.equal(deck.isFlipped(), false);
  deck.flip();
  deck.prev();
  assert.equal(deck.isFlipped(), false);
});

test("빈 덱은 현재 카드가 없고 넘길 수 없다", () => {
  const deck = createDeck([]);
  assert.equal(deck.current(), null);
  assert.equal(deck.currentIndex(), -1);
  assert.equal(deck.atEnd(), false);
  assert.equal(deck.next(), false);
});

test("셔플은 주어진 난수로 결정적이고, 원래 카드를 모두 포함한다", () => {
  const make = () => createDeck(CARDS, { shuffle: true, rng: seeded([0.99, 0.1, 0.5]) });
  const walk = (deck) => { const out = []; do { out.push(deck.current()); } while (deck.next()); return out; };
  assert.deepEqual(walk(make()), walk(make()), "같은 난수면 같은 순서");
  const fresh = make();
  assert.deepEqual(walk(fresh).slice().sort(), CARDS.slice().sort(), "모든 카드를 한 번씩 포함");
  assert.equal(make().isShuffled, true);
});

test("setShuffle 을 켜거나 꺼도 지금 보고 있던 카드는 그대로 보인다", () => {
  const deck = createDeck(CARDS, { rng: seeded([0.3, 0.7, 0.2, 0.9]) });
  deck.next();
  deck.next();
  const current = deck.current();
  deck.setShuffle(true);
  assert.equal(deck.current(), current);
  deck.setShuffle(false);
  assert.equal(deck.current(), current);
  assert.equal(deck.currentIndex(), CARDS.indexOf(current));
  assert.equal(deck.isShuffled, false, "끄면 원래 순서로 되돌아간다");
});

test("setShuffle 은 뒤집기 상태를 앞면으로 되돌린다", () => {
  const deck = createDeck(CARDS);
  deck.flip();
  deck.setShuffle(true);
  assert.equal(deck.isFlipped(), false);
});

test("shuffled 는 원본 배열을 바꾸지 않는다", () => {
  const original = [1, 2, 3, 4];
  const out = shuffled(original, seeded([0.5]));
  assert.deepEqual(original, [1, 2, 3, 4]);
  assert.equal(out.length, 4);
});

test("셔플을 켜도 진행도(위치)는 그대로이고, 이미 본 카드와 현재 카드는 바뀌지 않는다", () => {
  const deck = createDeck(CARDS, { rng: seeded([0.3, 0.7, 0.2, 0.9, 0.5]) });
  deck.next();
  deck.next(); // 위치 2 (세 번째 카드 'c')
  const seen = [deck.current(), CARDS[0], CARDS[1]];
  deck.setShuffle(true);
  assert.equal(deck.position, 2, "진행도 2 (3/5) 유지");
  assert.equal(deck.current(), "c", "현재 카드 유지");
  assert.deepEqual(seen.slice(1).sort(), ["a", "b"], "앞쪽에서 이미 본 카드는 그대로");
});

test("셔플을 켜면 아직 보지 않은 카드만 섞이고, 넘기면 남은 카드 중에서 나온다", () => {
  const deck = createDeck(CARDS);
  deck.next();
  deck.setShuffle(true);
  const after = [deck.current()];
  while (deck.next()) after.push(deck.current());
  assert.equal(after[0], "b", "현재 카드는 그대로");
  assert.deepEqual(after.slice().sort(), ["b", "c", "d", "e"], "남은 카드 전부가 나온다");
  assert.equal(deck.position, CARDS.length - 1);
});

test("셔플을 끄면 아직 보지 않은 카드가 원래 순서(오름차순)로 돌아온다", () => {
  const deck = createDeck(CARDS, { shuffle: true, rng: seeded([0.9, 0.1, 0.4, 0.6, 0.2]) });
  const firstViewed = deck.current();
  deck.next();
  const current = deck.current();
  deck.setShuffle(false);
  assert.equal(deck.current(), current, "보던 카드는 그대로");
  const rest = [];
  while (deck.next()) rest.push(deck.current());
  const expected = CARDS.filter((c) => c !== firstViewed && c !== current);
  assert.deepEqual(rest, expected, "이미 본 두 카드를 뺀 나머지가 원래 순서로 나온다");
});
