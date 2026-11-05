/*
 * 2026-11-05 - voda-voca - 통계 화면: 누적 정답률·연속 학습일, 주간 활동 차트, 표준 단어장별 진행률
 * 파일 위치: src/frontend/js/views/stats-view.js
 */

import { api } from "../core/api.js";
import { button, h, icon, notice } from "../core/dom.js";
import { statsPageModel } from "../core/stats-page-model.js";
import { renderWeeklyChart } from "../core/weekly-chart.js";
import { progressBar } from "./components/progress-bar.js";
import { mountLoader } from "./components/loader.js";

/** 단어장 제목은 있으면 좋은 정보라 카탈로그 실패는 무시한다. */
async function loadStats() {
  const [stats, catalog] = await Promise.all([api("/study/stats"), api("/vocabularies").catch(() => null)]);
  return statsPageModel(stats, catalog);
}

/**
 * @param {HTMLElement} root
 * @param {{navigate: (path: string, query?: Record<string, string>) => void}} ctx
 * @returns {() => void}
 */
export function statsView(root, ctx) {
  return mountLoader(root, loadStats, (m) => root.append(renderStats(m, ctx)));
}

function card(label, value, hint) {
  return h("div", { class: "card" }, h("p", { class: "text-xs font-medium text-zinc-500" }, label), h("p", { class: "mt-1 text-2xl font-extrabold tracking-tight text-zinc-900" }, value), hint ? h("p", { class: "text-xs text-zinc-500" }, hint) : null);
}

function renderStats(m, ctx) {
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
      card("누적 정답률", m.accuracy.value, m.accuracy.hint),
      card("연속 학습일", m.streak?.value ?? "0일", m.streak?.hint ?? "오늘 학습하면 시작돼요"),
      card("전체 단어", m.totalWords, "제공 단어장 합계"),
      card("복습할 오답", `${m.wrongWordCount}개`, "마지막 결과가 오답"),
    ),
    h("section", { class: "card space-y-2" }, h("div", { class: "flex items-baseline justify-between" }, h("h2", { class: "text-base font-bold text-zinc-900" }, "최근 7일"), h("span", { class: "text-sm text-zinc-500" }, `${m.weekTotal}개`)), renderWeeklyChart(m.weekly)),
    h(
      "section",
      { class: "card space-y-4" },
      h("h2", { class: "text-base font-bold text-zinc-900" }, "단어장별 진행률"),
      m.vocabulariesActiveFirst.map((v) =>
        h("div", { class: "space-y-1.5" }, h("div", { class: "flex items-center justify-between gap-2" }, h("p", { class: "min-w-0 truncate text-sm font-semibold text-zinc-800" }, v.isActive ? [h("span", { class: "mr-1.5 text-indigo-600" }, "학습 중"), v.title] : v.title), h("span", { class: "text-sm text-zinc-500" }, `${v.percent}%`)), progressBar(v.percent, `${v.title} 진행률`), h("p", { class: "text-xs text-zinc-500" }, v.text)),
      ),
    ),
  );
}
