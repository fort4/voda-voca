/*
 * 2026-11-02 - voda-voca - 주간 차트 기하 단위 테스트: 막대 높이 정규화, 최댓값 0 처리, 막대 경로 (DOM 없이 실행)
 * 파일 위치: src/frontend/tests/weekly-chart.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { barGeometry, barPath, CHART_HEIGHT } from "../js/core/weekly-chart.js";

const day = (label, count) => ({ date: `2026-11-0${label}`, label: "월", count });

test("막대 높이는 최댓값을 기준으로 정규화된다", () => {
  const bars = barGeometry([day(1, 0), day(2, 5), day(3, 10)]);
  assert.equal(bars[0].barHeight, 0);
  assert.equal(bars[2].barHeight, Math.round(CHART_HEIGHT - 18 - 22)); // 최댓값 막대는 그릴 수 있는 높이 전부
  assert.ok(bars[1].barHeight > 0 && bars[1].barHeight < bars[2].barHeight);
});

test("모든 날이 0이면 막대 높이는 모두 0이다 (0으로 나누지 않는다)", () => {
  assert.deepEqual(
    barGeometry([day(1, 0), day(2, 0)]).map((bar) => bar.barHeight),
    [0, 0],
  );
});

test("원래 날짜, 라벨, 개수는 그대로 유지된다", () => {
  const [first] = barGeometry([{ date: "2026-11-02", label: "월", count: 3 }]);
  assert.deepEqual(first, { date: "2026-11-02", label: "월", count: 3, barHeight: first.barHeight });
});

test("막대 경로: 높이가 0이면 빈 문자열, 있으면 닫힌 경로", () => {
  assert.equal(barPath(0, 100, 20, 0), "");
  const path = barPath(0, 100, 20, 50);
  assert.ok(path.startsWith("M 0 100"));
  assert.ok(path.endsWith("Z"));
});
