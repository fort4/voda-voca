/*
 * 2026-11-26 - voda-voca - 통계 차트 설정 단위 테스트: 팔레트 읽기, 회차·날짜·주간 차트의 Chart.js 설정, 값 라벨 위치, 키보드 이동 (DOM 없이 실행)
 * 파일 위치: src/frontend/tests/chart-model.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  dailyChartConfig,
  nextIndex,
  readChartPalette,
  sessionChartConfig,
  verticalGradient,
  weeklyChartConfig,
  withAlpha,
} from "../js/core/chart-model.js";
import { scoreTrendModel } from "../js/core/analytics-model.js";

const palette = {
  sessions: "#111111",
  daily: "#222222",
  weekly: "#333333",
  text: "#444444",
  muted: "#555555",
  grid: "#666666",
  surface: "#777777",
  tooltipBg: "#888888",
  tooltipBorder: "#999999",
  font: "sans-serif",
};

const trend = scoreTrendModel({
  sessions: [
    { round: 4, session_id: 40, correct: 2, total: 4, accuracy: 50 },
    { round: 5, session_id: 50, correct: 3, total: 4, accuracy: 75 },
  ],
  daily: [
    { date: "2026-11-24", answered: 4, correct: 0, accuracy: 0 },
    { date: "2026-11-25", answered: 12, correct: 9, accuracy: 75 },
  ],
});

const weekly = [
  { date: "2026-11-23", label: "월", count: 20, isToday: false },
  { date: "2026-11-24", label: "화", count: 0, isToday: false },
  { date: "2026-11-25", label: "수", count: 7, isToday: true },
];

test("withAlpha: #rrggbb 를 rgba 로 바꾼다", () => {
  assert.equal(withAlpha("#4f46e5", 0.5), "rgba(79, 70, 229, 0.5)");
});

test("readChartPalette: CSS 토큰을 읽고 앞뒤 공백을 지운다", () => {
  const read = (name) => ` value-of${name} `;
  const result = readChartPalette(read);
  assert.equal(result.sessions, "value-of--chart-sessions");
  assert.equal(result.daily, "value-of--chart-daily");
  assert.equal(result.weekly, "value-of--chart-weekly");
  assert.equal(result.text, "value-of--text");
  assert.equal(result.grid, "value-of--border");
});

test("verticalGradient: 차트 영역이 잡히기 전에는 단색, 잡힌 뒤에는 위→아래 그라데이션", () => {
  const paint = verticalGradient("#000000", 1, 0.2);
  assert.equal(paint({ chart: {} }), "rgba(0, 0, 0, 1)");
  const stops = [];
  let line;
  const ctx = {
    createLinearGradient: (...args) => {
      line = args;
      return { addColorStop: (at, color) => stops.push([at, color]) };
    },
  };
  paint({ chart: { ctx, chartArea: { top: 10, bottom: 110 } } });
  assert.deepEqual(line, [0, 10, 0, 110]);
  assert.deepEqual(stops, [[0, "rgba(0, 0, 0, 1)"], [1, "rgba(0, 0, 0, 0.2)"]]);
});

test("회차 차트: 면적이 채워진 선 그래프이고 세로축은 0~100% 이다", () => {
  const config = sessionChartConfig(trend.sessions, palette);
  assert.equal(config.type, "line");
  assert.deepEqual(config.data.labels, ["4회", "5회"]);
  const [set] = config.data.datasets;
  assert.deepEqual(set.data, [50, 75]);
  assert.equal(set.borderColor, palette.sessions);
  assert.equal(set.fill, true);
  assert.equal(set.cubicInterpolationMode, "monotone", "곡선이 0%·100% 밖으로 튀지 않아야 한다");
  assert.deepEqual(set.pointRadius, [4, 6], "점은 지름 8px 이상이고 마지막 회차를 크게 찍는다");
  assert.equal(config.options.scales.y.min, 0);
  assert.equal(config.options.scales.y.max, 100);
  assert.equal(config.options.scales.y.ticks.callback(50), "50%");
});

test("회차 차트: 회차가 하나뿐이면 점을 가운데에 놓는다", () => {
  assert.equal(sessionChartConfig(trend.sessions.slice(0, 1), palette).options.scales.x.offset, true);
  assert.equal(sessionChartConfig(trend.sessions, palette).options.scales.x.offset, false);
});

test("회차 차트: 말풍선은 정답률, 맞힌 수, 직전 회차 대비를 보인다", () => {
  const { callbacks } = sessionChartConfig(trend.sessions, palette).options.plugins.tooltip;
  assert.equal(callbacks.label({ dataIndex: 1 }), "정답률 75%");
  // 값이 먼저 보이도록 보조 정보는 옅은 글자인 footer 에 둔다
  assert.deepEqual(callbacks.footer([{ dataIndex: 1 }]), ["3 / 4 정답", "직전 회차 대비 +25%p"]);
  assert.deepEqual(callbacks.footer([{ dataIndex: 0 }]), ["2 / 4 정답"]);
});

test("회차 차트: 값 라벨은 마지막 회차 하나만 붙인다", () => {
  const labels = sessionChartConfig(trend.sessions, palette).options.plugins.vodaValueLabels;
  assert.deepEqual(labels.indices, [1]);
  assert.equal(labels.format(75), "75%");
});

test("날짜 차트: 폭 24px 이하의 둥근 막대, 0% 인 날도 흔적이 보인다", () => {
  const config = dailyChartConfig(trend.daily, palette);
  assert.equal(config.type, "bar");
  assert.deepEqual(config.data.labels, ["11/24", "11/25"]);
  const [set] = config.data.datasets;
  assert.deepEqual(set.data, [0, 75]);
  assert.ok(set.maxBarThickness <= 24);
  assert.equal(set.borderRadius, 4);
  assert.ok(set.minBarLength >= 2);
  assert.equal(config.options.plugins.tooltip.callbacks.footer([{ dataIndex: 1 }]), "9 / 12 정답");
});

test("주간 차트: 오늘은 라벨에 표시하고 막대를 더 진하게 그린다", () => {
  const config = weeklyChartConfig(weekly, palette);
  assert.deepEqual(config.data.labels, ["월", "화", ["수", "오늘"]]);
  const [set] = config.data.datasets;
  const chart = {};
  assert.equal(set.backgroundColor({ chart, dataIndex: 2 }), withAlpha(palette.weekly, 1));
  assert.notEqual(set.backgroundColor({ chart, dataIndex: 0 }), withAlpha(palette.weekly, 1));
  assert.equal(config.options.scales.y.beginAtZero, true);
  assert.equal(config.options.scales.y.ticks.precision, 0);
  assert.equal(config.options.plugins.tooltip.callbacks.label({ dataIndex: 0 }), "20개 단어");
});

test("주간 차트: 값 라벨은 가장 많은 날과 오늘에만, 0 에는 붙이지 않는다", () => {
  assert.deepEqual(weeklyChartConfig(weekly, palette).options.plugins.vodaValueLabels.indices, [0, 2]);
  const idle = weekly.map((d) => ({ ...d, count: 0 }));
  assert.deepEqual(weeklyChartConfig(idle, palette).options.plugins.vodaValueLabels.indices, []);
});

test("모든 차트: 범례 없이(계열 1개) 크기는 컨테이너를 따르고, animate=false 면 움직이지 않는다", () => {
  const builds = [
    (o) => sessionChartConfig(trend.sessions, palette, o),
    (o) => dailyChartConfig(trend.daily, palette, o),
    (o) => weeklyChartConfig(weekly, palette, o),
  ];
  for (const build of builds) {
    const still = build({ animate: false });
    assert.equal(still.options.animation, false);
    assert.equal(still.options.plugins.legend.display, false);
    assert.equal(still.options.responsive, true);
    assert.equal(still.options.maintainAspectRatio, false);
    assert.equal(still.options.interaction.intersect, false, "손가락이 막대에 정확히 닿지 않아도 값이 보여야 한다");
    assert.notEqual(build({ animate: true }).options.animation, false);
  }
});

test("nextIndex: 좌우 화살표·Home·End 로 이동하고 끝에서 멈춘다", () => {
  assert.equal(nextIndex(2, "ArrowLeft", 5), 1);
  assert.equal(nextIndex(0, "ArrowLeft", 5), 0);
  assert.equal(nextIndex(4, "ArrowRight", 5), 4);
  assert.equal(nextIndex(2, "Home", 5), 0);
  assert.equal(nextIndex(2, "End", 5), 4);
  assert.equal(nextIndex(2, "Enter", 5), null);
  assert.equal(nextIndex(0, "ArrowRight", 0), null);
});
