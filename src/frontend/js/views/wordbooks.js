/*
 * 2026-11-02 - voda-voca - 단어장 대시보드: 목록(Loading/Empty/Error/Success), 생성·수정 모달, 삭제 확인 (REQ-004~007)
 * 파일 위치: src/frontend/js/views/wordbooks.js
 */

import { api, ApiError } from "../core/api.js";
import { button, clear, h, icon, notice, skeleton } from "../core/dom.js";
import { field, alertBox } from "../core/form.js";
import { formatKst } from "../core/format.js";
import { confirmDialog, toast } from "../core/toast.js";
import { validateWordbookDescription, validateWordbookName } from "../core/validate.js";

export const PAGE_SIZE = 20;

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
 * @param {HTMLElement} root
 * @param {{navigate: (path: string, query?: object) => void}} ctx
 * @returns {() => void}
 */
export function wordbooksView(root, { navigate }) {
  const state = { status: "loading", items: [], total: 0, page: 0, error: "" };
  const controller = new AbortController();
  const listEl = h("div", { class: "space-y-3", "aria-live": "polite" });
  const moreBtn = button({ variant: "secondary", full: true, onClick: () => load(false) }, "더 보기");
  const createBtn = button({ onClick: () => openForm(null) }, icon("plus", "h-5 w-5"), "새 단어장");

  root.append(
    h(
      "div",
      { class: "mb-4 flex items-center justify-between gap-3" },
      h("h1", { class: "text-xl font-bold" }, "내 단어장"),
      createBtn,
    ),
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
  }

  /** @param {{id: number, name: string, description: string|null, updated_at: string}} wordbook */
  function card(wordbook) {
    return h(
      "article",
      { class: "flex items-stretch gap-2 rounded-xl bg-white shadow-sm ring-1 ring-slate-200", dataset: { wordbookId: String(wordbook.id) } },
      h(
        "button",
        {
          type: "button",
          class: "flex min-h-[44px] flex-1 flex-col items-start gap-1 rounded-l-xl p-4 text-left hover:bg-slate-50",
          onclick: () => navigate(`/wordbooks/${wordbook.id}`),
        },
        h("span", { class: "text-lg font-semibold text-slate-900 break-words" }, wordbook.name),
        wordbook.description ? h("span", { class: "text-sm text-slate-600 line-clamp-1" }, wordbook.description) : null,
        h("span", { class: "text-xs text-slate-500" }, `수정 ${formatKst(wordbook.updated_at)}`),
      ),
      h(
        "div",
        { class: "flex flex-col justify-center gap-1 pr-2" },
        button({ variant: "ghost", onClick: () => openForm(wordbook), }, icon("pencil", "h-5 w-5"), h("span", { class: "sr-only" }, `${wordbook.name} 수정`)),
        button({ variant: "ghost", onClick: () => remove(wordbook) }, icon("trash-2", "h-5 w-5 text-red-600"), h("span", { class: "sr-only" }, `${wordbook.name} 삭제`)),
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

  load(true);
  return () => controller.abort();
}

/**
 * 단어 목록 화면은 2단계에서 구현한다. 지금은 경로가 깨지지 않도록 안내만 보여 준다.
 * @param {HTMLElement} root
 * @param {{navigate: (path: string) => void}} ctx
 */
export function wordbookPlaceholderView(root, { navigate }) {
  root.append(
    notice({
      iconName: "hammer",
      title: "단어 목록은 다음 단계에서 제공됩니다.",
      action: button({ variant: "secondary", onClick: () => navigate("/wordbooks") }, icon("arrow-left"), "단어장으로"),
    }),
  );
}
