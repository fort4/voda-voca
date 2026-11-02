/*
 * 2026-11-02 - voda-voca - 주간 학습 활동 SVG 막대 차트: 막대 높이 정규화(순수 함수)와 인라인 SVG 렌더링, 탭·포커스 시 값 표시 (외부 차트 라이브러리 없음)
 * 파일 위치: src/frontend/js/core/weekly-chart.js
 */

const SVG_NS = "http://www.w3.org/2000/svg";
export const CHART_WIDTH = 280;
export const CHART_HEIGHT = 140;
const LABEL_BAND = 22; // 아래쪽 요일 라벨 자리
const TOP_PAD = 18; // 위쪽 값 표시 자리
const BAR_RADIUS = 6;

/**
 * 막대 높이를 최댓값 기준으로 정규화한다. 모두 0이면 막대는 0 높이다.
 * @param {Array<{date: string, label: string, count: number}>} days
 * @returns {Array<{date: string, label: string, count: number, barHeight: number}>}
 */
export function barGeometry(days) {
  const max = Math.max(1, ...days.map((day) => day.count));
  const drawable = CHART_HEIGHT - TOP_PAD - LABEL_BAND;
  return days.map((day) => ({
    ...day,
    barHeight: Math.round((Math.max(0, day.count) / max) * drawable),
  }));
}

/** @param {string} tag @param {Record<string, string|number>} attrs @param {Array<Element|string>} children */
function svgEl(tag, attrs = {}, children = []) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [name, value] of Object.entries(attrs)) el.setAttribute(name, String(value));
  for (const child of children) el.append(child);
  return el;
}

/**
 * 위쪽만 둥근 막대 경로. 높이가 0이면 빈 경로.
 * @returns {string}
 */
export function barPath(x, bottom, width, height) {
  if (height <= 0) return "";
  const top = bottom - height;
  const r = Math.min(BAR_RADIUS, width / 2, height);
  return [
    `M ${x} ${bottom}`,
    `L ${x} ${top + r}`,
    `Q ${x} ${top} ${x + r} ${top}`,
    `L ${x + width - r} ${top}`,
    `Q ${x + width} ${top} ${x + width} ${top + r}`,
    `L ${x + width} ${bottom}`,
    "Z",
  ].join(" ");
}

/**
 * 오늘 막대 위쪽에 붙는 작은 "오늘" 뱃지 (SVG 그룹). 값 표시 말풍선과 겹치면 CSS 로 숨긴다.
 * @param {number} cx 뱃지 중심 x 좌표
 * @returns {SVGGElement}
 */
function todayBadge(cx) {
  const w = 26;
  const h = 13;
  return svgEl("g", { class: "chart-today-badge" }, [
    svgEl("rect", { x: cx - w / 2, y: 1, width: w, height: h, rx: h / 2, ry: h / 2 }),
    svgEl("text", { x: cx, y: 1 + h / 2 + 0.5, "text-anchor": "middle", "dominant-baseline": "middle" }, [
      document.createTextNode("오늘"),
    ]),
  ]);
}

/**
 * 주간 활동 차트를 SVG 로 만든다. 막대를 누르거나 포커스하면 그 날의 단어 수를 막대 위에 보여 준다.
 * @param {Array<{date: string, label: string, count: number}>} days
 * @returns {SVGSVGElement}
 */
export function renderWeeklyChart(days) {
  const geometry = barGeometry(days);
  const bottom = CHART_HEIGHT - LABEL_BAND;
  const band = CHART_WIDTH / Math.max(1, geometry.length);
  const width = Math.round(band * 0.56);
  const tooltip = svgEl("text", { class: "chart-tooltip", "text-anchor": "middle", "aria-hidden": "true", visibility: "hidden" });
  const bars = [];

  const show = (index) => {
    const item = geometry[index];
    const x = index * band + (band - width) / 2;
    const y = item.count > 0 ? bottom - item.barHeight : bottom;
    tooltip.textContent = `${item.count}개`;
    tooltip.setAttribute("x", String(x + width / 2));
    tooltip.setAttribute("y", String(Math.max(12, y - 6)));
    tooltip.setAttribute("visibility", "visible");
    bars.forEach((bar, i) => bar.setAttribute("aria-current", i === index ? "true" : "false"));
  };
  const hide = () => {
    tooltip.setAttribute("visibility", "hidden");
    bars.forEach((bar) => bar.removeAttribute("aria-current"));
  };

  geometry.forEach((item, index) => {
    const x = index * band + (band - width) / 2;
    const hit = svgEl("rect", { x: index * band, y: 0, width: band, height: CHART_HEIGHT, fill: "transparent" });
    const bar = svgEl("path", { class: "chart-bar", d: barPath(x, bottom, width, item.barHeight) });
    const label = svgEl("text", { class: "chart-label", x: index * band + band / 2, y: CHART_HEIGHT - 6, "text-anchor": "middle" }, [
      document.createTextNode(item.label),
    ]);
    const children = [hit, bar, label];
    if (item.isToday) children.push(todayBadge(x + width / 2));
    const group = svgEl("g", {
      class: item.isToday ? "chart-day is-today" : "chart-day",
      tabindex: 0,
      role: "img",
      "aria-label": `${item.label}요일 ${item.count}개 단어${item.isToday ? ", 오늘" : ""}`,
    }, children);
    group.addEventListener("pointerenter", () => show(index));
    group.addEventListener("pointerdown", () => show(index));
    group.addEventListener("focus", () => show(index));
    group.addEventListener("pointerleave", hide);
    group.addEventListener("blur", hide);
    bars.push(group);
  });

  const svg = svgEl(
    "svg",
    { class: "weekly-chart", viewBox: `0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`, role: "img", "aria-label": "최근 7일 학습 활동", preserveAspectRatio: "xMidYMid meet" },
    [...bars, tooltip],
  );
  return /** @type {SVGSVGElement} */ (svg);
}
