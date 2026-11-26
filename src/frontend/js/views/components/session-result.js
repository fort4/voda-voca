/*
 * 2026-11-05 - voda-voca - 세션 완료 화면: 요약 문구, 통계 칸, 틀린 단어 목록, 다음 행동 버튼
 * 파일 위치: src/frontend/js/views/components/session-result.js
 */

import { button, h, icon } from "../../core/dom.js";
import { completeCopy } from "../../core/session-view-model.js";
import { iconBadge } from "./card-heading.js";

/** 지표 이름별 아이콘과 의미 색 */
const STAT_STYLES = {
  "정답률": ["target", "tone-accent"],
  "맞힌 문제": ["check", "tone-ok"],
  "최대 콤보": ["flame", "tone-activity"],
  "새로 숙련": ["sparkles", "tone-words"],
};

function statCell({ label, value }) {
  const [iconName, tone] = STAT_STYLES[label] ?? ["circle", "tone-accent"];
  return h("div", { class: `stat-cell ${tone}` }, iconBadge(iconName), h("div", { class: "stat-value" }, value), h("div", { class: "stat-label" }, label));
}

/**
 * @param {{summary: object, onRestart: () => void, onHome: () => void}} opts
 * @returns {HTMLElement}
 */
export function renderSessionResult({ summary, onRestart, onHome }) {
  const copy = completeCopy(summary);
  return h(
    "section",
    { class: "session-card rise-in" },
    h("div", { class: "trophy-badge" }, icon("trophy", "h-7 w-7")),
    h("h2", { class: "text-2xl font-extrabold tracking-tight" }, copy.title),
    h("p", { class: "session-context" }, copy.subtitle),
    summary.answered
      ? h(
          "div",
          { class: "stat-grid" },
          copy.stats.map(statCell),
        )
      : null,
    copy.showWrongList
      ? h(
          "div",
          { class: "wrong-list tone-wrong" },
          h("p", { class: "text-sm font-semibold" }, "다시 볼 단어"),
          summary.wrongItems.map((item) => h("div", { class: "wrong-row" }, h("strong", {}, item.term), h("span", {}, item.meaning))),
        )
      : null,
    h(
      "div",
      { class: "flex w-full flex-col gap-2 pt-2" },
      button({ variant: "primary", full: true, onClick: onRestart }, "한 번 더 하기"),
      button({ variant: "secondary", full: true, onClick: onHome }, "홈으로"),
    ),
  );
}
