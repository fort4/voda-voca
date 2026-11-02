/*
 * 2026-11-02 - voda-voca - 학습 이력 화면: 최근 50건 정답률 요약, 한국 날짜별 타임라인, 정답·오답 태그 (REQ-016)
 * 파일 위치: src/frontend/js/views/history.js
 */

import { api, ApiError } from "../core/api.js";
import { button, clear, h, icon, notice, refreshIcons, skeleton } from "../core/dom.js";
import { kstTime } from "../core/format.js";
import { groupByKstDate, summarizeLogs } from "../lib/study-stats.js";

export const HISTORY_LIMIT = 50;

/**
 * @param {HTMLElement} root
 * @param {{navigate: (path: string, query?: object) => void}} ctx
 * @returns {() => void}
 */
export function historyView(root, { navigate }) {
  const controller = new AbortController();
  const body = h("div", { class: "space-y-5" });
  root.append(body);

  async function load() {
    clear(body);
    body.append(skeleton(3));
    try {
      const data = await api("/study/logs", { query: { limit: HISTORY_LIMIT }, signal: controller.signal });
      render(data.items);
    } catch (error) {
      if (error.name === "AbortError") return;
      clear(body);
      body.append(
        notice({
          iconName: "cloud-off",
          title: "학습 이력을 불러오지 못했습니다.",
          text: error instanceof ApiError ? error.detail : "",
          action: button({ variant: "secondary", onClick: load }, "다시 시도"),
        }),
      );
    }
  }

  /** @param {Array<{word_id: number, term: string, is_correct: boolean, created_at: string}>} items */
  function render(items) {
    clear(body);
    if (items.length === 0) {
      body.append(
        notice({
          iconName: "history",
          title: "아직 학습 기록이 없습니다.",
          text: "퀴즈를 풀면 여기에 정답과 오답이 쌓입니다.",
          action: button({ onClick: () => navigate("/wordbooks") }, "단어장으로"),
        }),
      );
      return;
    }
    const summary = summarizeLogs(items);
    body.append(
      h(
        "section",
        { class: "rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200" },
        h("h1", { class: "text-xl font-bold" }, "학습 이력"),
        h("p", { class: "mt-2 text-3xl font-bold" }, `${summary.accuracy}%`),
        h("p", { class: "text-sm text-slate-600" }, `최근 ${summary.total}건 중 정답 ${summary.correct}개, 오답 ${summary.wrong}개`),
        h("p", { class: "mt-1 text-xs text-slate-500" }, `최근 ${HISTORY_LIMIT}건 기준입니다.`),
      ),
      ...groupByKstDate(items).map((group) =>
        h(
          "section",
          { class: "space-y-2" },
          h("h2", { class: "sticky top-14 bg-slate-50 py-1 text-sm font-semibold text-slate-600" }, group.date),
          h(
            "ol",
            { class: "space-y-2" },
            group.items.map((log) =>
              h(
                "li",
                { class: "flex items-center gap-3 rounded-xl bg-white px-4 py-3 ring-1 ring-slate-200" },
                h("span", { class: "w-12 shrink-0 font-mono text-sm text-slate-500" }, kstTime(log.created_at)),
                h("span", { class: "min-w-0 flex-1 break-words font-medium" }, log.term),
                log.is_correct
                  ? h("span", { class: "flex shrink-0 items-center gap-1 rounded-full bg-green-50 px-2 py-0.5 text-xs font-semibold text-green-800" }, icon("check", "h-3.5 w-3.5"), "정답")
                  : h("span", { class: "flex shrink-0 items-center gap-1 rounded-full bg-red-50 px-2 py-0.5 text-xs font-semibold text-red-800" }, icon("x", "h-3.5 w-3.5"), "오답"),
              ),
            ),
          ),
        ),
      ),
    );
    refreshIcons();
  }

  load();
  return () => controller.abort();
}
