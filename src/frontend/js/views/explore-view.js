/*
 * 2026-11-05 - voda-voca - 탐색 화면: 단어장 카탈로그 열람, 카테고리·레벨 필터, 단어 미리보기, 활성 단어장 변경, 내 단어장 추가·수정·삭제
 * 파일 위치: src/frontend/js/views/explore-view.js
 */

import { api } from "../core/api.js";
import { canEditContent, wordSheetEntry } from "../core/content-model.js";
import { button, clear, h, icon, refreshIcons } from "../core/dom.js";
import { categoryOptions, filterVocabularies, levelOptions, cardActionVariants, normalizeFilter, vocabularyCard } from "../core/explore-model.js";
import { toast } from "../core/toast.js";
import { confirmDeleteVocabulary, openVocabularyForm } from "./components/content-forms.js";
import { mountLoader } from "./components/loader.js";
import { iconBadge } from "./components/card-heading.js";
import { progressRow } from "./components/progress-bar.js";
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
    const title = h("h1", { class: "text-title tracking-tight text-zinc-900" }, "단어장 탐색");
    const add = button({ variant: "secondary", onClick: () => this.editVocabulary() }, icon("plus", "h-4 w-4"), "새 단어장");
    this.element = h("div", { class: "stack pb-4" }, h("div", { class: "flex items-center justify-between gap-2" }, title, add), this.chips, this.cards);
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
    const entry = wordSheetEntry(vocabulary);
    return h(
      "article",
      { class: `card vocab-card rise-in tone-accent space-y-3${c.isActive ? " vocab-card--active" : ""}` },
      h(
        "div",
        { class: "flex items-start gap-3" },
        iconBadge("book-open"),
        h("div", { class: "min-w-0 flex-1" }, h("h2", { class: "text-base font-bold text-zinc-900" }, c.title), h("p", { class: "text-xs text-zinc-500" }, c.metaText)),
        c.isActive ? h("span", { class: "shrink-0 rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-semibold text-indigo-600" }, "학습 중") : null,
      ),
      c.description ? h("p", { class: "text-sm text-zinc-700" }, c.description) : null,
      progressRow(c.progressPercent, `${c.title} 진행률`),
      h("p", { class: "text-xs text-zinc-500" }, c.progressText),
      h(
        "div",
        { class: "vocab-actions" },
        button({ variant: actions.preview, onClick: () => openWordSheet(vocabulary, { onWordsChanged: () => this.refresh() }) }, icon(entry.icon, "h-4 w-4"), entry.label),
        c.isActive ? button({ variant: actions.main, onClick: () => this.ctx.navigate("/") }, icon("check", "h-4 w-4"), "홈에서 학습") : button({ variant: actions.main, disabled: this.busyId !== null || !c.canStudy, onClick: () => this.activate(vocabulary) }, c.canStudy ? "이 단어장으로 학습" : "단어를 추가해 주세요"),
      ),
      canEditContent(vocabulary) ? this.ownerActions(vocabulary) : null,
    );
  }

  /** 내 단어장에만 붙는 수정·삭제 줄. */
  ownerActions(vocabulary) {
    return h(
      "div",
      { class: "grid grid-cols-2 gap-2", role: "group", "aria-label": `${vocabulary.title} 관리` },
      button({ variant: "ghost", onClick: () => this.editVocabulary(vocabulary) }, icon("pencil", "h-4 w-4"), "수정"),
      button({ variant: "danger-soft", onClick: () => this.removeVocabulary(vocabulary) }, icon("trash-2", "h-4 w-4"), "삭제"),
    );
  }

  async editVocabulary(vocabulary) {
    if (await openVocabularyForm(vocabulary)) await this.refresh();
  }

  async removeVocabulary(vocabulary) {
    if (await confirmDeleteVocabulary(vocabulary)) await this.refresh();
  }

  /** 단어장·단어를 바꾼 뒤 목록과 단어 수를 다시 받는다. */
  async refresh() {
    try {
      this.catalog = await api("/vocabularies");
      this.filter = normalizeFilter(this.catalog, this.filter);
    } catch (error) {
      toast(error?.detail ?? "목록을 새로 불러오지 못했어요.", "error");
    }
    this.paint();
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
