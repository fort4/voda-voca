/*
 * 2026-11-26 - voda-voca - 통계 화면 차트 연결 검사: Chart.js 자체 호스팅, 표 대체, 정리 함수, 요약 값, 차트 색 토큰
 * 파일 위치: src/frontend/tests/stats-charts-ui.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { scoreTrendModel } from "../js/core/analytics-model.js";
import { statsPageModel } from "../js/core/stats-page-model.js";

const path = (rel) => new URL(`../${rel}`, import.meta.url);
const read = (rel) => readFileSync(path(rel), "utf8");
const css = read("css/app.css").replace(/\/\*[\s\S]*?\*\//g, "");
const view = read("js/views/stats-view.js");

test("index.html 은 vendor 의 Chart.js 를 불러오고 출처를 기록한다", () => {
  assert.match(read("index.html"), /src="vendor\/chart\.js-4\.6\.2\/chart\.umd\.js"/);
  assert.ok(existsSync(path("vendor/chart.js-4.6.2/chart.umd.js")));
  assert.ok(existsSync(path("vendor/chart.js-4.6.2/LICENSE.md")));
  assert.match(read("vendor/README.md"), /Chart\.js \(UMD\) \| 4\.6\.2/);
});

test("통계 화면은 세 차트를 만들고, 화면을 떠날 때 차트를 정리한다", () => {
  for (const name of ["sessionChartConfig", "dailyChartConfig", "weeklyChartConfig"]) {
    assert.match(view, new RegExp(`${name}\\(`));
  }
  assert.match(view, /charts\.mount\(\)/);
  assert.match(view, /charts\.destroy\(\)/);
  assert.doesNotMatch(view, /weekly-chart/);
  assert.equal(existsSync(path("js/core/weekly-chart.js")), false, "쓰지 않는 SVG 차트는 남기지 않는다");
});

test("차트마다 표 보기를 함께 두고, 캔버스는 키보드로 값을 읽을 수 있다", () => {
  const panel = read("js/views/components/chart-panel.js");
  assert.match(panel, /"details"/);
  assert.match(panel, /"table"/);
  assert.match(panel, /tabindex:\s*"0"/);
  assert.match(panel, /role:\s*"img"/);
  assert.match(panel, /nextIndex\(/);
  assert.match(css, /\.chart-table\s+summary\s*\{[^}]*min-height:\s*44px/);
});

test("차트 색 토큰은 라이트와 다크에 모두 있고 검증한 값이다", () => {
  const block = (selector) => [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)].filter((m) => m[1].trim() === selector).map((m) => m[2]).join(";");
  const expected = {
    ":root": { "--chart-sessions": "#4f46e5", "--chart-daily": "#0d9488", "--chart-weekly": "#d97706" },
    "html.dark": { "--chart-sessions": "#7c7ff2", "--chart-daily": "#12a594", "--chart-weekly": "#d9820a" },
  };
  for (const [selector, tokens] of Object.entries(expected)) {
    for (const [name, value] of Object.entries(tokens)) {
      assert.match(block(selector), new RegExp(`${name}:\\s*${value}`), `${selector} ${name}`);
    }
  }
});

test("회차 요약: 최근 정답률과 직전 대비 방향", () => {
  const session = (round, accuracy) => ({ round, session_id: round, correct: 1, total: 2, accuracy });
  const summary = (...list) => scoreTrendModel({ sessions: list.map((a, i) => session(i + 1, a)), daily: [] }).latestSession;
  assert.deepEqual(summary(50, 75), { accuracyText: "75%", change: "+25%p", direction: "up" });
  assert.deepEqual(summary(75, 50), { accuracyText: "50%", change: "-25%p", direction: "down" });
  assert.deepEqual(summary(50, 50), { accuracyText: "50%", change: "변화 없음", direction: "flat" });
  assert.deepEqual(summary(50), { accuracyText: "50%", change: null, direction: null });
  assert.equal(summary(), null);
});

test("날짜 요약: 기간 평균은 푼 문항 수로 가중한다", () => {
  const model = scoreTrendModel({
    sessions: [],
    daily: [
      { date: "2026-11-24", answered: 1, correct: 1, accuracy: 100 },
      { date: "2026-11-25", answered: 9, correct: 0, accuracy: 0 },
    ],
  });
  assert.equal(model.dailyAverageText, "10%");
  assert.equal(scoreTrendModel({ sessions: [], daily: [] }).dailyAverageText, null);
});

test("누적 정답률 고리는 숫자 퍼센트를 쓴다", () => {
  const stats = { answered: 3, accuracy: 66.7, streak_days: 0, weekly: [], total_words: 0, vocabulary_progress: [], wrong_word_count: 0 };
  assert.equal(statsPageModel(stats, null).accuracyPercent, 67);
  assert.equal(statsPageModel({ ...stats, accuracy: null }, null).accuracyPercent, 0);
});

test("자주 틀리는 단어와 단어장 진행률은 서로 다른 색의 막대를 쓴다", () => {
  assert.match(view, /"wrong"/);
  assert.match(view, /"progress"/);
  assert.match(css, /\.meter--wrong\s*\{[^}]*--meter-from:\s*var\(--meter-wrong-from\)/);
  assert.match(css, /\.progress-fill\s*\{[^}]*linear-gradient/);
});
