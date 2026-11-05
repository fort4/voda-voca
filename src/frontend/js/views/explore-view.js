/*
 * 2026-11-05 - voda-voca - 탐색 화면: 표준 단어장 카탈로그 열람, 카테고리·레벨 필터, 단어 미리보기, 활성 단어장 변경
 * 파일 위치: src/frontend/js/views/explore-view.js
 */

import { api } from "../core/api.js";
import { button, clear, h, icon, refreshIcons } from "../core/dom.js";
import { categoryOptions, filterVocabularies, levelOptions, cardActionVariants, vocabularyCard } from "../core/explore-model.js";
import { toast } from "../core/toast.js";
import { mountLoader } from "./components/loader.js";
import { progressBar } from "./components/progress-bar.js";
import { openWordSheet } from "./components/word-sheet.js";

/**
 * @param {HTMLElement} root
 * @param {{navigate: (path: string, query?: Record<string, string>) => void}} ctx
 * @returns {() => void}
 */
export function exploreView(root, ctx) {
  return mountLoader(root, () => api("/vocabularies"), (catalog) => root.append(new ExplorePanel(catalog, ctx).element));
}

class ExplorePanel {
  constructor(catalog, ctx) {
    this.catalog = catalog;
    this.ctx = ctx;
    this.filter = { category: "all", level: "all" };
    this.busyId = null;
    this.chips = h("div", { class: "space-y-2" });
    this.cards = h("div", { class: "space-y-3" });
    this.element = h("div", { class: "stack pb-4" }, h("h1", { class: "text-title tracking-tight text-zinc-900" }, "단어장 탐색"), this.chips, this.cards);
    this.paint();
  }

  paint() {
    clear(this.chips);
    this.chips.append(
      this.chipRow("카테고리", categoryOptions(this.catalog), "category"),
      this.chipRow("레벨", levelOptions(this.catalog), "level"),
    );
    clear(this.cards);
    const shown = filterVocabularies(this.catalog, this.filter);
    if (shown.length === 0) this.cards.append(h("p", { class: "surface p-6 text-center text-sm text-zinc-600" }, "조건에 맞는 단어장이 없어요."));
    for (const vocabulary of shown) this.cards.append(this.card(vocabulary));
    refreshIcons();
  }

  chipRow(label, options, key) {
    return h(
      "div",
      { class: "flex items-center gap-2 overflow-x-auto pb-1", role: "group", "aria-label": `${label} 필터` },
      options.map((option) => {
        const on = String(this.filter[key]) === String(option.value);
        return h("button", { type: "button", "aria-pressed": String(on), class: "chip focus-ring", onclick: () => { this.filter = { ...this.filter, [key]: option.value }; this.paint(); } }, option.label);
      }),
    );
  }

  card(vocabulary) {
    const c = vocabularyCard(vocabulary);
    const actions = cardActionVariants(c);
    return h(
      "article",
      { class: "card rise-in space-y-3" },
      h("div", { class: "flex items-start justify-between gap-2" }, h("h2", { class: "min-w-0 text-base font-bold text-zinc-900" }, c.title), c.isActive ? h("span", { class: "shrink-0 rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-semibold text-indigo-600" }, "학습 중") : null),
      h("p", { class: "text-xs text-zinc-500" }, `${c.categoryLabel} · ${c.levelLabel} · ${c.wordCountText}`),
      c.description ? h("p", { class: "text-sm text-zinc-700" }, c.description) : null,
      progressBar(c.progressPercent, `${c.title} 진행률`),
      h("p", { class: "text-xs text-zinc-500" }, c.progressText),
      h(
        "div",
        { class: "grid grid-cols-2 gap-2" },
        button({ variant: actions.preview, onClick: () => openWordSheet(vocabulary) }, icon("eye", "h-4 w-4"), "미리보기"),
        c.isActive ? button({ variant: actions.main, onClick: () => this.ctx.navigate("/") }, icon("check", "h-4 w-4"), "홈에서 학습") : button({ variant: actions.main, disabled: this.busyId !== null, onClick: () => this.activate(vocabulary) }, "이 단어장으로 학습"),
      ),
    );
  }

  async activate(vocabulary) {
    this.busyId = vocabulary.id;
    this.paint();
    try {
      const updated = await api("/users/me/active-vocabulary", { method: "POST", body: { vocabulary_id: vocabulary.id } });
      this.catalog = this.catalog.map((v) => ({ ...v, user_progress: { ...v.user_progress, is_active: v.id === updated.id } }));
      toast(`'${updated.title}'로 학습해요`);
    } catch (error) {
      toast(error?.detail ?? "단어장을 바꾸지 못했어요.", "error");
    } finally {
      this.busyId = null;
      this.paint();
    }
  }
}
