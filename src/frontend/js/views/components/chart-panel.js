/*
 * 2026-11-26 - voda-voca - 차트 패널: Chart.js 캔버스(키보드 탐색)와 같은 값을 담은 표 보기. 브라우저의 Chart 전역과 차트 수명 관리를 연결한다 (REQ-132, REQ-155)
 * 파일 위치: src/frontend/js/views/components/chart-panel.js
 */

import { crosshairPlugin, nextIndex, readChartPalette, valueLabelPlugin } from "../../core/chart-model.js";
import { createChartSet, watchDarkClass } from "../../core/chart-set.js";
import { h } from "../../core/dom.js";

let registered = false;

/** @returns {ReturnType<typeof createChartSet>} 화면 하나가 쓰는 차트 묶음 */
export function browserChartSet() {
  const ChartCtor = globalThis.Chart;
  if (ChartCtor && !registered) {
    ChartCtor.register(valueLabelPlugin, crosshairPlugin);
    registered = true;
  }
  const root = document.documentElement;
  return createChartSet({
    ChartCtor,
    readPalette: () => {
      const style = getComputedStyle(root);
      return readChartPalette((token) => style.getPropertyValue(token));
    },
    observeTheme: (listener) => watchDarkClass(root, MutationObserver, listener),
    reducedMotion: () => globalThis.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches === true,
  });
}

/** 가리킨 값의 말풍선을 키보드로도 띄운다. index 가 null 이면 지운다. */
function highlight(chart, index) {
  const active = index === null ? [] : [{ datasetIndex: 0, index }];
  const point = index === null ? { x: 0, y: 0 } : chart.getDatasetMeta(0).data[index];
  chart.setActiveElements(active);
  chart.tooltip?.setActiveElements(active, { x: point.x, y: point.y });
  chart.update();
}

function dataTable(caption, head, rows) {
  return h(
    "table",
    { class: "w-full" },
    h("caption", { class: "sr-only" }, caption),
    h("thead", {}, h("tr", {}, head.map((text) => h("th", { scope: "col" }, text)))),
    h("tbody", {}, rows.map((row) => h("tr", {}, row.map((text, i) => (i === 0 ? h("th", { scope: "row" }, text) : h("td", {}, text)))))),
  );
}

/**
 * @param {ReturnType<typeof createChartSet>} charts
 * @param {{label: string, summary: string, build: (palette: object, options: {animate: boolean}) => object,
 *          table: {head: string[], rows: string[][]}, tall?: boolean}} options
 * @returns {HTMLElement}
 */
export function chartPanel(charts, { label, summary, build, table, tall = false }) {
  let index = 0;
  const length = table.rows.length;
  const canvas = h("canvas", { role: "img", tabindex: "0", "aria-label": `${label} 그래프. ${summary}. 좌우 화살표로 값을 확인합니다.` });
  const show = (next) => {
    const chart = charts.chartOf(canvas);
    if (chart) highlight(chart, next);
  };
  canvas.addEventListener("focus", () => {
    index = length - 1;
    // 터치·마우스로 얻은 포커스는 누른 위치의 값을 그대로 둔다
    if (canvas.matches(":focus-visible")) show(index);
  });
  canvas.addEventListener("blur", () => show(null));
  canvas.addEventListener("keydown", (event) => {
    const next = nextIndex(index, event.key, length);
    if (next === null) return;
    event.preventDefault();
    index = next;
    show(index);
  });

  const box = h("div", { class: tall ? "chart-box chart-box--tall" : "chart-box" }, canvas);
  const details = h("details", { class: "chart-table" }, h("summary", { class: "focus-ring" }, "표로 보기"), h("div", { class: "chart-table-scroll" }, dataTable(label, table.head, table.rows)));
  charts.add(canvas, build, () => {
    box.hidden = true;
    details.open = true;
  });
  return h("div", { class: "space-y-1" }, box, details);
}
