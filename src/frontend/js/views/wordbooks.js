/*
 * 2026-11-02 - voda-voca - 단어장 대시보드: 목록(Loading/Empty/Error/Success), 생성·수정 모달, 삭제 확인 (REQ-004~007)
 * 파일 위치: src/frontend/js/views/wordbooks.js
 */

import { api, ApiError } from "../core/api.js";
import { button, clear, h, icon, notice, refreshIcons, skeleton } from "../core/dom.js";
import { field, alertBox } from "../core/form.js";
import { formatKst } from "../core/format.js";
import { confirmDialog, toast } from "../core/toast.js";
import { validateWordbookDescription, validateWordbookName } from "../core/validate.js";
import { downloadWordbook, fetchAllPages } from "../core/backup.js";
import { computeSummary, computeWeeklyActivity, computeWordbookProgress } from "../core/stats.js";
import { renderWeeklyChart } from "../core/weekly-chart.js";
import { sourceRouteQuery } from "../lib/study-source.js";

export const PAGE_SIZE = 20;

/** 기본 제공 단어장의 성격. 이름으로 판정하고, 나머지는 사용자가 만든 단어장이다. */
const LEVEL_BY_NAME = new Map([
  ["초급 필수 영단어 200", "beginner"],
  ["중급 핵심 영단어 200", "intermediate"],
  ["고급 심화 영단어 200", "advanced"],
  ["중급 필수 영단어 1,000", "intermediate"],
]);
const LEVEL_LABEL = { beginner: "초급", intermediate: "중급", advanced: "고급", user: "내 단어장" };

/**
 * 단어장 태그(성격)를 정한다.
 * @param {string} name
 * @returns {{key: "beginner"|"intermediate"|"advanced"|"user", label: string}}
 */
export function levelTagOf(name) {
  const key = /** @type {"beginner"|"intermediate"|"advanced"|"user"} */ (LEVEL_BY_NAME.get(name) ?? "user");
  return { key, label: LEVEL_LABEL[key] };
}

/**
 * 단어 수 배지 문구. 0개도 분명히 보여 준다.
 * @param {number} count
 * @returns {string}
 */
export function wordCountLabel(count) {
  const n = Number.isInteger(count) && count > 0 ? count : 0;
  return `${n.toLocaleString("ko-KR")}개 단어`;
}

/**
 * 목록 상태를 순수하게 계산한다. 화면 없이 테스트할 수 있도록 분리했다.
 * @param {{status: "loading"|"error"|"ok", items: unknown[], total: number}} s
 * @returns {"loading"|"error"|"empty"|"success"}
 */
export function listViewState(s) {
  if (s.status === "loading") return "loading";
  if (s.status === "error") return "error";
  return s.items.length === 0 ? "empty" : "success";
}

/**
 * 더 보기 버튼을 보여 줄지 판단한다.
 * @param {{items: unknown[], total: number}} s
 * @returns {boolean}
 */
export function hasMore(s) {
  return s.items.length < s.total;
}

/**
 * 요약 통계 카드 한 장.
 * @param {string} iconName
 * @param {string} label
 * @param {string} value
 * @param {string} hint
 */
function statCard(iconName, label, value, hint) {
  return h(
    "div",
    { class: "surface flex min-w-0 flex-col gap-1 p-3 sm:p-4" },
    h("span", { class: "inline-flex items-center gap-1.5 text-xs font-medium text-zinc-500" }, icon(iconName, "h-4 w-4"), label),
    h("span", { class: "truncate text-xl font-bold tabular-nums text-zinc-900 sm:text-2xl" }, value),
    hint ? h("span", { class: "truncate text-xs text-zinc-500" }, hint) : null,
  );
}

/**
 * @param {HTMLElement} root
 * @param {{navigate: (path: string, query?: object) => void}} ctx
 * @returns {() => void}
 */
export function wordbooksView(root, { navigate }) {
  const state = { status: "loading", items: [], total: 0, page: 0, error: "" };
  /** 대시보드 통계. 단어장 목록과 따로 받는다. */
  const dash = { status: "loading", summary: null, weekly: [], logs: [], error: "" };
  const dashEl = h("section", { class: "mb-4 space-y-3", "aria-label": "학습 요약" });
  const controller = new AbortController();
  const listEl = h("div", { class: "space-y-3", "aria-live": "polite" });
  const moreBtn = button({ variant: "secondary", full: true, onClick: () => load(false) }, "더 보기");
  const createBtn = button({ onClick: () => openForm(null) }, icon("plus", "h-5 w-5"), "새 단어장");
  const presetBtn = button({ variant: "secondary", onClick: addPreset }, icon("sparkles", "h-5 w-5"), "추천 1,000제 추가");

  root.append(
    h(
      "div",
      { class: "mb-4 flex items-center justify-between gap-3" },
      h("h1", { class: "text-xl font-bold" }, "내 단어장"),
      h("div", { class: "flex flex-wrap justify-end gap-2" }, presetBtn, createBtn),
    ),
    dashEl,
    listEl,
    h("div", { class: "mt-4" }, moreBtn),
  );

  /** @param {boolean} reset 처음부터 다시 받을지 여부 */
  async function load(reset) {
    if (reset) {
      state.items = [];
      state.total = 0;
      state.page = 0;
    }
    state.status = "loading";
    state.error = "";
    render();
    if (reset) loadDashboard();
    try {
      const nextPage = state.page + 1;
      const data = await api("/wordbooks", { query: { page: nextPage, size: PAGE_SIZE }, signal: controller.signal });
      state.items = state.items.concat(data.items);
      state.total = data.total;
      state.page = nextPage;
      state.status = "ok";
    } catch (error) {
      if (error.name === "AbortError") return;
      state.status = "error";
      state.error = error instanceof ApiError ? error.detail : "단어장을 불러오지 못했습니다.";
    }
    render();
  }

  /** 요약 카드와 주간 차트에 쓸 데이터를 받는다. 실패해도 단어장 목록은 그대로 보인다. */
  async function loadDashboard() {
    dash.status = "loading";
    renderDashboard();
    try {
      const [books, logs] = await Promise.all([
        fetchAllPages("/wordbooks", {}),
        api("/study/logs", { query: { limit: 100 }, signal: controller.signal }),
      ]);
      dash.logs = logs.items;
      dash.summary = computeSummary(books, logs.items);
      dash.weekly = computeWeeklyActivity(logs.items);
      dash.status = "ok";
    } catch (error) {
      if (error.name === "AbortError") return;
      dash.status = "error";
      dash.error = "통계를 불러오지 못했습니다.";
    }
    renderDashboard();
    render();
  }

  function renderDashboard() {
    clear(dashEl);
    if (dash.status === "error") {
      dashEl.append(h("p", { class: "text-sm text-zinc-500" }, dash.error));
      return;
    }
    const loaded = dash.status === "ok";
    const summary = dash.summary;
    dashEl.append(
      h(
        "div",
        { class: "grid grid-cols-3 gap-2 sm:gap-3" },
        statCard("book-open", "총 단어", loaded ? summary.totalWords.toLocaleString("ko-KR") : "…", loaded ? "모든 단어장" : ""),
        statCard(
          "target",
          "정답률",
          loaded && summary.accuracy !== null ? `${summary.accuracy}%` : "—",
          loaded && summary.answered > 0 ? `최근 ${summary.answered}문항` : "기록 없음",
        ),
        statCard("flame", "연속 학습", loaded ? `${summary.streak}일` : "…", loaded ? "오늘 기준" : ""),
      ),
    );
    if (loaded) {
      const weekTotal = dash.weekly.reduce((sum, day) => sum + day.count, 0);
      dashEl.append(
        h(
          "section",
          { class: "surface p-4" },
          h(
            "div",
            { class: "mb-2 flex items-center justify-between" },
            h("h2", { class: "text-sm font-semibold text-zinc-800" }, "최근 7일 학습"),
            h("span", { class: "text-xs text-zinc-500" }, `합계 ${weekTotal.toLocaleString("ko-KR")}개`),
          ),
          renderWeeklyChart(dash.weekly),
        ),
      );
    }
    refreshIcons();
  }

  function render() {
    clear(listEl);
    const view = listViewState(state);
    moreBtn.hidden = view !== "success" || !hasMore(state);
    if (view === "loading") {
      listEl.append(skeleton(3));
    } else if (view === "error") {
      listEl.append(
        notice({
          iconName: "cloud-off",
          title: "단어장을 불러오지 못했습니다.",
          text: state.error,
          action: button({ variant: "secondary", onClick: () => load(state.items.length === 0) }, "다시 시도"),
        }),
      );
    } else if (view === "empty") {
      listEl.append(
        notice({
          iconName: "book-open",
          title: "아직 단어장이 없습니다.",
          text: "첫 단어장을 만들어 단어를 모아 보세요.",
          action: button({ onClick: () => openForm(null) }, "첫 단어장 만들기"),
        }),
      );
    } else {
      for (const wordbook of state.items) listEl.append(card(wordbook));
    }
    refreshIcons();
  }

  /** @param {{id: number, name: string, description: string|null, updated_at: string, word_count: number}} wordbook */
  function card(wordbook) {
    const level = levelTagOf(wordbook.name);
    const progress = computeWordbookProgress(wordbook.id, dash.logs, wordbook.word_count);
    const fill = h("div", { class: "progress-fill" });
    fill.style.width = `${progress}%`;
    const track = h(
      "div",
      { class: "progress-track", role: "progressbar", "aria-label": `${wordbook.name} 학습 진행률`, "aria-valuemin": "0", "aria-valuemax": "100", "aria-valuenow": String(progress) },
      fill,
    );
    return h(
      "article",
      { class: "surface overflow-hidden", dataset: { wordbookId: String(wordbook.id) } },
      h(
        "div",
        { class: "flex items-stretch gap-2" },
        h(
          "button",
          {
            type: "button",
            class: "flex min-h-[44px] flex-1 flex-col items-start gap-1 rounded-l-xl p-4 text-left hover:bg-zinc-50",
            onclick: () => navigate(`/wordbooks/${wordbook.id}`),
          },
          h("span", { class: `level-tag level-tag--${level.key}` }, level.label),
          h("span", { class: "text-lg font-semibold text-zinc-900 break-words" }, wordbook.name),
          h("span", { class: "inline-flex items-center rounded-full bg-zinc-100 px-2.5 py-0.5 text-xs font-medium text-zinc-600" }, wordCountLabel(wordbook.word_count)),
          wordbook.description ? h("span", { class: "text-sm text-zinc-600 line-clamp-1" }, wordbook.description) : null,
          h("span", { class: "text-xs text-zinc-500" }, `수정 ${formatKst(wordbook.updated_at)}`),
        ),
        h(
          "div",
          { class: "flex flex-col justify-center gap-1 pr-2" },
          button({ variant: "ghost", onClick: () => openForm(wordbook) }, icon("pencil", "h-5 w-5"), h("span", { class: "sr-only" }, `${wordbook.name} 수정`)),
          button({ variant: "ghost", onClick: () => exportOne(wordbook) }, icon("download", "h-5 w-5"), h("span", { class: "sr-only" }, `${wordbook.name} CSV 내보내기`)),
          button({ variant: "ghost", onClick: () => remove(wordbook) }, icon("trash-2", "h-5 w-5 text-red-600"), h("span", { class: "sr-only" }, `${wordbook.name} 삭제`)),
        ),
      ),
      h(
        "div",
        { class: "flex items-center gap-2 px-4 pb-4" },
        h(
          "div",
          { class: "min-w-0 flex-1" },
          h(
            "div",
            { class: "mb-1 flex justify-between text-xs text-zinc-500" },
            h("span", {}, "학습 진행률"),
            h("span", { class: "tabular-nums" }, `${progress}%`),
          ),
          track,
        ),
        button(
          { variant: "ghost", "aria-label": `${wordbook.name} 플래시카드`, onClick: () => navigate("/study/flashcards", sourceRouteQuery({ kind: "wordbook", wordbookId: wordbook.id })) },
          icon("layers", "h-5 w-5"),
        ),
        button(
          { variant: "ghost", "aria-label": `${wordbook.name} 퀴즈`, onClick: () => navigate("/study/quiz", sourceRouteQuery({ kind: "wordbook", wordbookId: wordbook.id })) },
          icon("play", "h-5 w-5"),
        ),
      ),
    );
  }

  /**
   * 생성(wordbook=null) 또는 수정 모달. SweetAlert2 의 html 에 DOM 요소를 넘겨 값을 이스케이프 문제 없이 채운다.
   * @param {null | {id: number, name: string, description: string|null}} wordbook
   */
  async function openForm(wordbook) {
    if (!globalThis.Swal) return;
    const name = field({ id: "wb-name", label: "이름", autocomplete: "off", value: wordbook?.name ?? "", maxlength: 50 });
    const desc = field({ id: "wb-desc", label: "설명 (선택)", autocomplete: "off", value: wordbook?.description ?? "", maxlength: 200 });
    const banner = alertBox();
    const form = h("form", { class: "space-y-4 text-left", novalidate: true, onsubmit: (e) => e.preventDefault() }, name.wrap, desc.wrap, banner.el);

    const result = await globalThis.Swal.fire({
      title: wordbook ? "단어장 수정" : "새 단어장",
      html: form,
      showCancelButton: true,
      confirmButtonText: wordbook ? "저장" : "만들기",
      cancelButtonText: "취소",
      focusConfirm: false,
      preConfirm: () => {
        const nameError = validateWordbookName(name.input.value);
        const descError = validateWordbookDescription(desc.input.value);
        name.setError(nameError);
        desc.setError(descError);
        if (nameError || descError) {
          globalThis.Swal.showValidationMessage(nameError || descError);
          return false;
        }
        return { name: name.input.value.trim(), description: desc.input.value.trim() || null };
      },
    });
    if (!result.isConfirmed || !result.value) return;

    try {
      if (wordbook) {
        await api(`/wordbooks/${wordbook.id}`, { method: "PATCH", body: result.value });
        toast("단어장을 수정했습니다.");
      } else {
        await api("/wordbooks", { method: "POST", body: result.value });
        toast("단어장을 만들었습니다.");
      }
      await load(true);
    } catch (error) {
      toast(error.status === 409 ? "같은 이름의 단어장이 이미 있습니다." : error.detail, "error");
    }
  }

  /** 추천 1,000제 프리셋을 내 단어장으로 추가한다 (확인 후 POST, 1,000건이 한 번에 저장된다). */
  async function addPreset() {
    const ok = await confirmDialog({
      title: "추천 1,000제를 추가할까요?",
      text: "'중급 필수 영단어 1,000' 단어장과 단어 1,000개가 내 목록에 추가됩니다.",
      confirmText: "추가",
    });
    if (!ok) return;
    presetBtn.disabled = true;
    try {
      await api("/wordbooks/presets/intermediate-1000", { method: "POST" });
      toast("추천 단어장을 추가했습니다.");
      await load(true);
    } catch (error) {
      if (error.status === 409) toast("이미 추가된 추천 단어장입니다.", "info");
      else if (error.status === 503) toast("추천 단어장 데이터가 아직 준비되지 않았습니다.", "error");
      else toast(error.detail ?? "추가하지 못했습니다.", "error");
    } finally {
      presetBtn.disabled = false;
    }
  }

  /** @param {{id: number, name: string}} wordbook */
  async function remove(wordbook) {
    const ok = await confirmDialog({
      title: "단어장을 삭제할까요?",
      text: `'${wordbook.name}' 안의 단어, 북마크, 학습 기록이 모두 삭제됩니다. 되돌릴 수 없습니다.`,
      confirmText: "삭제",
      danger: true,
    });
    if (!ok) return;
    try {
      await api(`/wordbooks/${wordbook.id}`, { method: "DELETE" });
      toast("단어장을 삭제했습니다.");
      await load(true);
    } catch (error) {
      toast(error.detail, "error");
      if (error.status === 404) await load(true);
    }
  }

  /**
   * 단어장 하나를 CSV 로 내보낸다. 확인을 거친 뒤에만 받는다.
   * @param {{id: number, name: string, word_count: number}} wordbook
   */
  async function exportOne(wordbook) {
    const ok = await confirmDialog({
      title: "CSV 내보내기",
      text: `이 단어장('${wordbook.name}')의 단어 ${wordbook.word_count.toLocaleString("ko-KR")}개를 CSV 파일로 내보내시겠습니까?`,
      confirmText: "내보내기",
    });
    if (!ok) return;
    try {
      const count = await downloadWordbook(wordbook);
      toast(`'${wordbook.name}' 단어 ${count.toLocaleString("ko-KR")}개를 내보냈습니다.`);
    } catch (error) {
      toast(error.detail ?? "내보내지 못했습니다.", "error");
    }
  }

  load(true);
  return () => controller.abort();
}
