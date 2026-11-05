/*
 * 2026-11-03 - voda-voca - 학습 이력 화면: 누적 정답률 요약(서버 통계), 한국 날짜별 최근 기록 타임라인, 정답·오답 태그, 오답 복습 시작 (REQ-016, 이슈 #3)
 * 파일 위치: src/frontend/js/views/history.js
 */

import { api, ApiError } from "../core/api.js";
import { button, clear, h, icon, notice, refreshIcons, skeleton } from "../core/dom.js";
import { kstTime } from "../core/format.js";
import { HISTORY_TIMELINE_LIMIT, historySummary, wrongReviewState } from "../core/stats-view.js";
import { groupByKstDate } from "../lib/study-stats.js";

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
      // 요약과 오답 단어 수는 전체 이력을 서버가 집계한 값이고, 타임라인은 최근 기록만 보여 준다.
      const [logs, stats] = await Promise.all([
        api("/study/logs", { query: { limit: HISTORY_TIMELINE_LIMIT }, signal: controller.signal }),
        api("/study/stats", { signal: controller.signal }),
      ]);
      render(logs.items, stats);
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

  /**
   * @param {Array<{word_id: number, term: string, is_correct: boolean, created_at: string}>} items
   * @param {{answered: number, correct: number, accuracy: number|null, wrong_word_count: number}} stats
   */
  function render(items, stats) {
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
    const summary = historySummary(stats);
    body.append(
      h(
        "section",
        { class: "p-5 surface" },
        h("h1", { class: "text-xl font-bold" }, "학습 이력"),
        h("p", { class: "mt-2 text-3xl font-bold" }, summary.headline),
        h("p", { class: "text-sm text-zinc-600" }, summary.detail),
        h("p", { class: "mt-1 text-xs text-zinc-500" }, summary.footnote),
        wrongReviewAction(stats.wrong_word_count),
      ),
      ...groupByKstDate(items).map((group) =>
        h(
          "section",
          { class: "space-y-2" },
          h("h2", { class: "sticky top-14 bg-zinc-50 py-1 text-sm font-semibold text-zinc-600" }, group.date),
          h(
            "ol",
            { class: "space-y-2" },
            group.items.map((log) =>
              h(
                "li",
                { class: "flex items-center gap-3 px-4 py-3 surface" },
                h("span", { class: "w-12 shrink-0 font-mono text-sm text-zinc-500" }, kstTime(log.created_at)),
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

  /**
   * 오답 복습 시작 버튼. 단어별 마지막 결과가 오답인 단어가 4개 미만이면 비활성화하고 현재 개수를 안내한다.
   * 퀴즈 출제도 같은 규칙을 쓰므로 여기 보이는 개수가 곧 출제 대상이다.
   * @param {number} wrongWordCount
   */
  function wrongReviewAction(wrongWordCount) {
    const { ready, message } = wrongReviewState(wrongWordCount);
    return h(
      "div",
      { class: "mt-4 space-y-2" },
      button(
        { full: true, disabled: !ready, onClick: () => navigate("/study/quiz", { wrong: "1" }) },
        icon("target"),
        "오답 복습 퀴즈 시작",
      ),
      h(
        "p",
        { class: "text-center text-xs text-zinc-500" },
        message,
      ),
    );
  }

  load();
  return () => controller.abort();
}
