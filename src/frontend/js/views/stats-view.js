/*
 * 2026-11-05 - voda-voca - 통계 화면: 누적 정답률·연속 학습일, 성적 추이·주간 활동 차트(Chart.js), 자주 틀리는 단어, 표준 단어장별 진행률
 * 파일 위치: src/frontend/js/views/stats-view.js
 */

import { api } from "../core/api.js";
import { button, h, icon, notice, refreshIcons } from "../core/dom.js";
import { frequentWrongListModel, frequentWrongModel, scoreTrendModel } from "../core/analytics-model.js";
import { dailyChartConfig, sessionChartConfig, weeklyChartConfig } from "../core/chart-model.js";
import { statsPageModel } from "../core/stats-page-model.js";
import { cardHeading, iconBadge } from "./components/card-heading.js";
import { browserChartSet, chartPanel } from "./components/chart-panel.js";
import { progressBar } from "./components/progress-bar.js";
import { mountLoader } from "./components/loader.js";
import { statsSwitch } from "./components/stats-switch.js";

/**
 * 단어장 제목은 있으면 좋은 정보라 카탈로그 실패는 무시한다.
 * 성적 추이와 자주 틀리는 단어도 부가 섹션이라 실패하면 그 섹션만 빼고 나머지 통계는 그대로 보여 준다.
 */
async function loadStats() {
  const [stats, catalog, trend, frequent] = await Promise.all([
    api("/study/stats"),
    api("/vocabularies").catch(() => null),
    api("/study/score-trend").catch(() => null),
    api("/study/frequent-wrong", { query: { limit: 10 } }).catch(() => null),
  ]);
  return {
    ...statsPageModel(stats, catalog),
    trend: trend ? scoreTrendModel(trend) : null,
    frequent: frequent ? frequentWrongModel(frequent) : null,
  };
}

/**
 * @param {HTMLElement} root
 * @param {{navigate: (path: string, query?: Record<string, string>) => void}} ctx
 * @returns {() => void}
 */
export function statsView(root, ctx) {
  const charts = browserChartSet();
  const body = h("div");
  root.append(h("h1", { class: "text-title mb-3 tracking-tight text-zinc-900" }, "학습 통계"));
  root.append(statsSwitch("stats"), body); // 전환은 불러오는 중이나 기록이 없을 때도 보인다
  const dispose = mountLoader(body, loadStats, (m) => {
    body.append(renderStats(m, ctx, charts));
    charts.mount(); // 캔버스가 문서에 붙은 뒤에 그려야 크기를 읽는다
  });
  return () => {
    dispose();
    charts.destroy();
  };
}

/** 요약 카드. 아이콘 색은 지표를 알아보는 표시이고, 값은 본문 글자색을 쓴다. */
function card({ label, value, hint, iconName, tone, aside }) {
  return h(
    "div",
    { class: `card tone-${tone}` },
    h("div", { class: "flex items-center gap-2" }, iconBadge(iconName), h("p", { class: "text-xs font-medium text-zinc-500" }, label)),
    h("div", { class: "mt-2 flex items-center justify-between gap-2" }, h("p", { class: "text-2xl font-extrabold tracking-tight text-zinc-900" }, value), aside ?? null),
    hint ? h("p", { class: "text-xs text-zinc-500" }, hint) : null,
  );
}

/** 누적 정답률 고리. 값은 옆의 숫자가 읽어 주므로 장식으로 숨긴다. */
function accuracyRing(percent) {
  return h("span", { class: "stat-ring", style: `--ring: ${percent}`, "aria-hidden": "true" });
}

const DELTA_ICONS = { up: "trending-up", down: "trending-down", flat: "minus" };

/** 차트 위의 제목 줄: 제목, 대표 값, 직전 대비(색과 아이콘, 글자를 함께 쓴다) */
function chartHeading(title, value, valueLabel, delta) {
  return h(
    "div",
    { class: "flex items-end justify-between gap-2" },
    h("h3", { class: "text-sm font-semibold text-zinc-600" }, title),
    h(
      "p",
      { class: "flex items-center gap-2" },
      delta?.direction ? h("span", { class: `delta delta--${delta.direction}` }, icon(DELTA_ICONS[delta.direction], "h-3.5 w-3.5"), delta.change) : null,
      h("span", { class: "text-xs text-zinc-500" }, valueLabel),
      h("span", { class: "text-heading text-zinc-900" }, value),
    ),
  );
}

function renderTrend(trend, charts) {
  if (!trend || trend.isEmpty) return null;
  const { sessions, daily, latestSession } = trend;
  return h(
    "section",
    { class: "card tone-accent space-y-5" },
    cardHeading({ iconName: "trending-up", title: "시험 성적 추이" }),
    sessions.length > 0
      ? h(
          "div",
          { class: "space-y-2" },
          chartHeading("회차별 정답률", latestSession.accuracyText, "최근", latestSession),
          chartPanel(charts, {
            label: "회차별 정답률",
            summary: `${sessions.length}회, 최근 ${latestSession.accuracyText}`,
            build: (palette, options) => sessionChartConfig(sessions, palette, options),
            table: { head: ["회차", "정답률", "정답", "직전 대비"], rows: sessions.map((s) => [s.label, s.accuracyText, s.scoreText, s.change ?? "—"]) },
            tall: true,
          }),
        )
      : null,
    daily.length > 0
      ? h(
          "div",
          { class: "space-y-2" },
          chartHeading("날짜별 정답률", trend.dailyAverageText ?? "—", "평균"),
          chartPanel(charts, {
            label: "날짜별 정답률",
            summary: `${daily.length}일, 평균 ${trend.dailyAverageText}`,
            build: (palette, options) => dailyChartConfig(daily, palette, options),
            table: { head: ["날짜", "정답률", "푼 결과"], rows: daily.map((d) => [d.label, d.accuracyText, d.text]) },
          }),
        )
      : null,
  );
}

function frequentWrongItem(w) {
  return h(
    "li",
    { class: "flex items-start gap-3" },
    h("span", { class: w.rank <= 3 ? "rank-badge rank-badge--top" : "rank-badge" }, String(w.rank)),
    h(
      "div",
      { class: "min-w-0 flex-1 space-y-1.5" },
      h("div", { class: "flex items-baseline justify-between gap-2" }, h("p", { class: "min-w-0 truncate text-sm font-semibold text-zinc-800" }, w.term), h("span", { class: "shrink-0 text-sm text-zinc-500" }, w.countText)),
      progressBar(w.ratio, `${w.term} 오답 횟수`, "wrong"),
      h("p", { class: "text-xs text-zinc-500" }, `${w.meaning} · ${w.ratioText}`),
    ),
  );
}

/** 처음에는 접힌 상태다. 펼치기·접기는 개수, 목록, 버튼만 다시 그려 버튼의 포커스를 지킨다. */
function renderFrequentWrong(frequent, ctx) {
  if (!frequent || frequent.isEmpty) return null;
  const count = h("span", { class: "text-sm text-zinc-500" });
  const list = h("ol", { class: "space-y-3" });
  let expanded = false;
  const toggleButton = button({
    variant: "ghost", full: true,
    onClick: () => {
      expanded = !expanded;
      draw();
      refreshIcons();
      if (!expanded) toggleButton.scrollIntoView({ block: "nearest" }); // 목록이 줄면 버튼이 화면 위로 밀릴 수 있다
    },
  });

  toggleButton.classList.add("scroll-my-24"); // 상단 헤더와 하단 탭바에 가려지지 않게 남기는 여백

  function draw() {
    const { items, countText, toggle } = frequentWrongListModel(frequent, expanded);
    count.textContent = countText;
    list.replaceChildren(...items.map(frequentWrongItem));
    toggleButton.hidden = !toggle;
    if (!toggle) return;
    toggleButton.setAttribute("aria-expanded", String(toggle.expanded));
    toggleButton.replaceChildren(toggle.label, icon(toggle.iconName, "h-4 w-4"));
  }

  draw();
  return h(
    "section",
    { class: "card tone-wrong space-y-4" },
    cardHeading({ iconName: "rotate-ccw", title: "자주 틀리는 단어", aside: count }),
    list,
    toggleButton.hidden ? null : toggleButton,
    button({ variant: "secondary", full: true, onClick: () => ctx.navigate("/review", { tab: "wrong" }) }, icon("rotate-ccw", "h-4 w-4"), "복습함에서 오답 복습하기"),
  );
}

function renderWeekly(m, charts) {
  return h(
    "section",
    { class: "card tone-activity space-y-2" },
    cardHeading({ iconName: "calendar-days", title: "최근 7일", aside: h("span", { class: "text-sm text-zinc-500" }, `${m.weekTotal}개`) }),
    chartPanel(charts, {
      label: "최근 7일 학습 단어 수",
      summary: `합계 ${m.weekTotal}개`,
      build: (palette, options) => weeklyChartConfig(m.weekly, palette, options),
      table: { head: ["날짜", "요일", "학습 단어"], rows: m.weekly.map((d) => [d.date.slice(5).replace("-", "/"), d.isToday ? `${d.label} (오늘)` : d.label, `${d.count}개`]) },
    }),
  );
}

function renderStats(m, ctx, charts) {
  if (m.isEmpty) {
    return notice({
      iconName: "bar-chart-3",
      title: "아직 학습 기록이 없어요",
      text: "첫 세션을 마치면 정답률과 진행률이 여기에 쌓여요.",
      action: button({ variant: "primary", onClick: () => ctx.navigate("/") }, "학습 시작하기"),
    });
  }
  return h(
    "div",
    { class: "stack pb-4" },
    h(
      "div",
      { class: "grid grid-cols-2 gap-3" },
      card({ label: "누적 정답률", value: m.accuracy.value, hint: m.accuracy.hint, iconName: "target", tone: "accent", aside: accuracyRing(m.accuracyPercent) }),
      card({ label: "연속 학습일", value: m.streak?.value ?? "0일", hint: m.streak?.hint ?? "오늘 학습하면 시작돼요", iconName: "flame", tone: "activity" }),
      card({ label: "전체 단어", value: m.totalWords, hint: "제공 단어장 합계", iconName: "book-open", tone: "words" }),
      card({ label: "복습할 오답", value: `${m.wrongWordCount}개`, hint: "마지막 결과가 오답", iconName: "rotate-ccw", tone: "wrong" }),
    ),
    renderTrend(m.trend, charts),
    renderFrequentWrong(m.frequent, ctx),
    renderWeekly(m, charts),
    h(
      "section",
      { class: "card tone-accent space-y-4" }, // 막대(학습 진행)와 같은 색
      cardHeading({ iconName: "book-open", title: "단어장별 진행률" }),
      m.vocabulariesActiveFirst.map((v) =>
        h("div", { class: "space-y-1.5" }, h("div", { class: "flex items-center justify-between gap-2" }, h("p", { class: "min-w-0 truncate text-sm font-semibold text-zinc-800" }, v.isActive ? [h("span", { class: "mr-1.5 text-indigo-600" }, "학습 중"), v.title] : v.title), h("span", { class: "text-sm font-bold text-zinc-900" }, `${v.percent}%`)), progressBar(v.percent, `${v.title} 진행률`, "progress"), h("p", { class: "text-xs text-zinc-500" }, v.text)),
      ),
    ),
  );
}
