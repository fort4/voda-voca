/*
 * 2026-11-26 - voda-voca - 학습 순위 화면: 공개한 사용자의 순위와 내 지표를 지표별로 본다. 조회만 한다 (REQ-172, VOCA-FR-051~053)
 * 파일 위치: src/frontend/js/views/ranking-view.js
 */

import { api } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { RANKING_METRICS, rankingModel } from "../core/ranking-model.js";
import { cardHeading } from "./components/card-heading.js";
import { mountLoader } from "./components/loader.js";
import { statsSwitch } from "./components/stats-switch.js";

/**
 * @param {HTMLElement} root
 * @param {{navigate: (path: string) => void}} ctx
 * @returns {() => void}
 */
export function rankingView(root, ctx) {
  let metric = RANKING_METRICS[0].id;
  let dispose = () => {};
  const body = h("div");

  const choices = RANKING_METRICS.map((m) =>
    h("button", { type: "button", class: "segment press focus-ring", "aria-pressed": String(m.id === metric), onclick: () => select(m.id) }, m.label),
  );

  /** 지표를 바꾸면 이전 요청의 응답은 버리고 다시 읽는다. */
  function show() {
    dispose();
    dispose = mountLoader(
      body,
      async () => rankingModel(await api("/ranking", { query: { metric } })),
      (model) => body.append(renderRanking(model, ctx)),
    );
  }

  /** @param {string} next */
  function select(next) {
    if (next === metric) return;
    metric = next;
    choices.forEach((el, i) => el.setAttribute("aria-pressed", String(RANKING_METRICS[i].id === metric)));
    show();
  }

  root.append(
    h("h1", { class: "text-title mb-3 tracking-tight text-zinc-900" }, "학습 순위"),
    statsSwitch("ranking"),
    h("div", { class: "stack pb-4" }, h("div", { class: "segmented grid-cols-3", role: "group", "aria-label": "순위 지표" }, choices), body),
  );
  show();
  return () => dispose();
}

function renderMe(me, ctx) {
  return h(
    "section",
    { class: "card tone-accent space-y-2", "aria-label": "내 순위" },
    cardHeading({ iconName: "user", title: me.title }),
    h("p", { class: "text-sm text-zinc-700" }, me.detail),
    me.hint ? h("p", { class: "text-xs text-zinc-500" }, me.hint) : null,
    button({ variant: "secondary", full: true, onClick: () => ctx.navigate("/mypage") }, "마이페이지에서 공개 설정"),
  );
}

function renderRow(row) {
  return h(
    "li",
    { class: row.isMe ? "ranking-row ranking-row--me" : "ranking-row" },
    h("span", { class: row.rank <= 3 ? "rank-badge rank-badge--lead" : "rank-badge" }, String(row.rank)),
    h(
      "div",
      { class: "min-w-0 flex-1" },
      h(
        "div",
        { class: "flex items-baseline justify-between gap-2" },
        h(
          "p",
          { class: "flex min-w-0 items-baseline gap-1.5" },
          h("span", { class: "truncate text-sm font-semibold text-zinc-800" }, row.nickname),
          row.isMe ? h("span", { class: "shrink-0 text-xs font-bold text-indigo-600" }, "나") : null,
        ),
        h("p", { class: "shrink-0 text-base font-extrabold text-zinc-900" }, row.valueText),
      ),
      h("p", { class: "text-xs text-zinc-500" }, row.otherText),
    ),
  );
}

function renderRanking(model, ctx) {
  return h(
    "div",
    { class: "stack" },
    renderMe(model.me, ctx),
    h(
      "section",
      { class: "card tone-accent space-y-3" },
      cardHeading({ iconName: "trophy", title: "학습 순위", aside: h("span", { class: "shrink-0 text-sm text-zinc-500" }, model.totalText) }),
      h("p", { class: "text-xs text-zinc-500" }, model.description),
      model.isEmpty
        ? h("p", { class: "py-4 text-center text-sm text-zinc-600" }, "아직 순위를 공개한 사용자가 없어요.")
        : h("ol", { class: "space-y-2" }, model.rows.map(renderRow)),
      model.limitText ? h("p", { class: "text-center text-xs text-zinc-500" }, model.limitText) : null,
    ),
  );
}
