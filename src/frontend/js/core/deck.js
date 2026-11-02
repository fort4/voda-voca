/*
 * 2026-11-02 - voda-voca - 플래시카드 덱 상태: 순서 관리, 셔플(현재 카드 유지), 앞·뒤 상태, 경계 처리 (REQ-012, REQ-013)
 * 파일 위치: src/frontend/js/core/deck.js
 */

/**
 * Fisher-Yates 셔플. rng 는 [0, 1) 난수 함수다 (테스트에서 고정 가능).
 * @template T
 * @param {T[]} items
 * @param {() => number} rng
 * @returns {T[]} 새 배열
 */
export function shuffled(items, rng = Math.random) {
  const out = items.slice();
  for (let i = out.length - 1; i > 0; i -= 1) {
    const j = Math.floor(rng() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

/**
 * @template T
 * @param {T[]} cards
 * @param {{shuffle?: boolean, rng?: () => number}} [opts]
 */
export function createDeck(cards, { shuffle = false, rng = Math.random } = {}) {
  let order = cards.map((_, i) => i);
  if (shuffle) order = shuffled(order, rng);
  let position = 0;
  let flipped = false;

  return {
    get total() {
      return cards.length;
    },
    get position() {
      return position;
    },
    get isShuffled() {
      return isShuffledOrder();
    },
    /** 지금 보고 있는 카드 (없으면 null) */
    current() {
      return cards.length ? cards[order[position]] : null;
    },
    /** 지금 카드의 원래 순서 번호 (0부터). 셔플 전환 때 같은 카드를 유지하는 데 쓴다. */
    currentIndex() {
      return cards.length ? order[position] : -1;
    },
    isFlipped() {
      return flipped;
    },
    flip() {
      flipped = !flipped;
      return flipped;
    },
    /** 다음 카드로. 마지막이면 false. 앞면으로 되돌린다. */
    next() {
      if (position >= cards.length - 1) return false;
      position += 1;
      flipped = false;
      return true;
    },
    /** 이전 카드로. 처음이면 false. 앞면으로 되돌린다. */
    prev() {
      if (position <= 0) return false;
      position -= 1;
      flipped = false;
      return true;
    },
    atEnd() {
      return cards.length > 0 && position === cards.length - 1;
    },
    /**
     * 셔플을 켜거나 끈다. 이미 본 카드(앞쪽)와 지금 카드는 그대로 두고, 아직 보지 않은 카드만 다시 섞거나 원래 순서로 되돌린다.
     * 그래서 진행도(위치)는 바뀌지 않고, 셔플 후 넘기면 남은 카드가 무작위로 나온다.
     * @param {boolean} on
     */
    setShuffle(on) {
      if (cards.length === 0) return;
      const visited = order.slice(0, position);
      const current = order[position];
      const unseen = order.slice(position + 1);
      const rest = on ? shuffled(unseen, rng) : unseen.slice().sort((a, b) => a - b);
      order = [...visited, current, ...rest];
      flipped = false;
    },
  };

  /** 원래 순서와 같은지 확인한다. */
  function isShuffledOrder() {
    return order.some((value, i) => value !== i);
  }
}
