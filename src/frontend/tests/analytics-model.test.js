/*
 * 2026-11-25 - voda-voca - 학습 분석 뷰모델 단위 테스트: 자주 틀리는 단어 상위 N, 시험 성적 추이(회차별·날짜별 정답률) (VOCA-FR-032, 033)
 * 파일 위치: src/frontend/tests/analytics-model.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { frequentWrongListModel, frequentWrongModel, scoreTrendModel } from "../js/core/analytics-model.js";

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), "utf8");

const item = (id, wrong, answered) => ({
  word_id: id,
  vocabulary_id: 1,
  vocabulary_title: "초급 200제",
  term: `word${id}`,
  meaning: `뜻${id}`,
  wrong_count: wrong,
  answered_count: answered,
  last_wrong_at: "2026-11-25T02:00:00Z",
});

test("자주 틀리는 단어: 순위, 오답 횟수, 오답 비율 문구를 만든다", () => {
  const model = frequentWrongModel({ items: [item(1, 5, 8), item(2, 1, 1)] });
  assert.equal(model.isEmpty, false);
  assert.deepEqual(
    model.items.map((i) => [i.rank, i.term, i.countText, i.ratioText]),
    [
      [1, "word1", "5회 오답", "8번 중 5번 틀림"],
      [2, "word2", "1회 오답", "1번 중 1번 틀림"],
    ],
  );
});

test("자주 틀리는 단어: 막대는 최다 오답 횟수 대비 비율이다", () => {
  const model = frequentWrongModel({ items: [item(1, 4, 5), item(2, 2, 2), item(3, 1, 3)] });
  assert.deepEqual(model.items.map((i) => i.ratio), [100, 50, 25]);
});

test("자주 틀리는 단어: 비어 있으면 isEmpty", () => {
  assert.equal(frequentWrongModel({ items: [] }).isEmpty, true);
});

const session = (round, correct, total) => ({
  round,
  session_id: round * 10,
  taken_at: "2026-11-25T02:00:00Z",
  correct,
  total,
  accuracy: Math.round((correct / total) * 1000) / 10,
});

test("성적 추이: 둘 다 없을 때만 isEmpty", () => {
  assert.equal(scoreTrendModel({ sessions: [], daily: [] }).isEmpty, true);
  assert.equal(scoreTrendModel({ sessions: [session(1, 2, 4)], daily: [] }).isEmpty, false);
});

test("성적 추이: 회차 항목", () => {
  const model = scoreTrendModel({ sessions: [session(1, 2, 4), session(2, 3, 4)], daily: [] });
  assert.deepEqual(
    model.sessions.map((s) => [s.label, s.scoreText, s.percent]),
    [
      ["1회", "2 / 4", 50],
      ["2회", "3 / 4", 75],
    ],
  );
});

test("성적 추이: 직전 회차 대비 변화 문구 (오르면 +, 내리면 -, 같으면 변화 없음, 첫 회차는 없음)", () => {
  const model = scoreTrendModel({ sessions: [session(1, 2, 4), session(2, 3, 4), session(3, 3, 4), session(4, 1, 4)], daily: [] });
  assert.deepEqual(
    model.sessions.map((s) => s.change),
    [null, "+25%p", "변화 없음", "-50%p"],
  );
});

test("성적 추이: 날짜 라벨은 월/일, 정답률 문구와 막대", () => {
  const model = scoreTrendModel({
    sessions: [],
    daily: [{ date: "2026-11-24", answered: 4, correct: 2, accuracy: 50 }, { date: "2026-11-25", answered: 10, correct: 9, accuracy: 90 }],
  });
  assert.deepEqual(
    model.daily.map((d) => [d.label, d.percent, d.text]),
    [
      ["11/24", 50, "2 / 4 정답"],
      ["11/25", 90, "9 / 10 정답"],
    ],
  );
});

test("성적 추이: 정답률 소수는 막대에서만 반올림하고 문구에는 소수 첫째 자리를 쓴다", () => {
  const model = scoreTrendModel({ sessions: [{ ...session(1, 2, 3), accuracy: 66.7 }], daily: [] });
  assert.equal(model.sessions[0].percent, 67);
  assert.equal(model.sessions[0].accuracyText, "66.7%");
});

const frequentOf = (count) => frequentWrongModel({ items: Array.from({ length: count }, (_, i) => item(i + 1, count - i, count)) });

test("자주 틀리는 단어 접힘: 상위 5개만 보이고 '더 보기'를 준다", () => {
  const list = frequentWrongListModel(frequentOf(10), false);
  assert.deepEqual(list.items.map((w) => w.rank), [1, 2, 3, 4, 5]);
  assert.equal(list.countText, "상위 5개");
  assert.deepEqual(list.toggle, { label: "더 보기", iconName: "chevron-down", expanded: false });
});

test("자주 틀리는 단어 펼침: 10개를 보이고 '접기'를 준다", () => {
  const list = frequentWrongListModel(frequentOf(10), true);
  assert.equal(list.items.length, 10);
  assert.equal(list.countText, "상위 10개");
  assert.deepEqual(list.toggle, { label: "접기", iconName: "chevron-up", expanded: true });
});

test("자주 틀리는 단어: 6~9개면 펼쳤을 때 개수 문구가 실제 개수다", () => {
  assert.equal(frequentWrongListModel(frequentOf(7), false).countText, "상위 5개");
  assert.equal(frequentWrongListModel(frequentOf(7), true).countText, "상위 7개");
});

test("자주 틀리는 단어: 5개 이하이면 모두 보이고 버튼이 없다", () => {
  for (const count of [1, 5]) {
    const list = frequentWrongListModel(frequentOf(count), false);
    assert.equal(list.items.length, count);
    assert.equal(list.countText, `상위 ${count}개`);
    assert.equal(list.toggle, null);
  }
});

test("자주 틀리는 단어: 접어도 막대 비율은 전체 최다 오답 기준 그대로다", () => {
  const model = frequentOf(10);
  assert.deepEqual(frequentWrongListModel(model, false).items, model.items.slice(0, 5));
});

test("통계 화면은 성적 추이와 자주 틀리는 단어를 서버에서 받아 보여 준다", () => {
  const src = read("js/views/stats-view.js");
  assert.match(src, /\/study\/score-trend/);
  assert.match(src, /\/study\/frequent-wrong/);
  assert.match(src, /scoreTrendModel\(/);
  assert.match(src, /frequentWrongModel\(/);
});

test("통계 화면의 자주 틀리는 단어는 펼치기·접기 버튼의 상태를 알리고 아이콘을 다시 그린다", () => {
  const src = read("js/views/stats-view.js");
  assert.match(src, /frequentWrongListModel\(/);
  assert.match(src, /setAttribute\("aria-expanded", String\(toggle\.expanded\)\)/);
  assert.match(src, /variant: "ghost", full: true/);
  assert.match(src, /refreshIcons\(\)/);
  assert.match(src, /scrollIntoView\(\{ block: "nearest" \}\)/);
  assert.match(src, /classList\.add\("scroll-my-24"\)/); // 상단 헤더와 하단 탭바에 가려지지 않는 여백
});
