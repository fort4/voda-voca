/*
 * 2026-11-02 - voda-voca - 단어 일괄 등록 모달: CSV·TSV 파일 또는 직접 입력, 미리보기, 오류 행 필터, POST /bulk, 409 conflict_term 강조, 422 loc 인덱스 매핑 (UI 설계서 §3.8, REQ-008)
 * 파일 위치: src/frontend/js/views/bulk-import.js
 */

import { api, ApiError } from "../core/api.js";
import { button, clear, h, icon, refreshIcons } from "../core/dom.js";
import { alertBox, INPUT_CLASS } from "../core/form.js";
import { toast } from "../core/toast.js";
import {
  BULK_MAX_ITEMS,
  buildBulkPayload,
  CsvParseError,
  detectDelimiter,
  exceedsBulkLimit,
  parseDelimited,
  toCandidateRows,
  validateCandidateRows,
} from "../lib/csv.js";

export const MAX_FILE_BYTES = 256 * 1024;
const REPLACEMENT_CHAR = "�";

/**
 * 입력 텍스트를 미리보기 행으로 바꾼다. 순수 함수이므로 화면 없이 테스트한다.
 * @param {string} text
 * @param {string} [fileName]
 * @returns {{rows: ReturnType<typeof validateCandidateRows>, headerSkipped: boolean, parseError: string}}
 */
export function parseBulkInput(text, fileName = "") {
  if (!text.trim()) return { rows: [], headerSkipped: false, parseError: "" };
  if (text.includes(REPLACEMENT_CHAR)) {
    return { rows: [], headerSkipped: false, parseError: "UTF-8로 저장한 뒤 다시 선택해 주세요." };
  }
  try {
    const records = parseDelimited(text, detectDelimiter(text, fileName));
    const { headerSkipped, rows } = toCandidateRows(records);
    return { rows: validateCandidateRows(rows), headerSkipped, parseError: "" };
  } catch (error) {
    if (error instanceof CsvParseError) {
      return { rows: [], headerSkipped: false, parseError: `${error.lineNo}행: ${error.message}` };
    }
    throw error;
  }
}

/**
 * 422 응답에서 항목별 오류를 꺼낸다. loc 가 ["body", "items", i, ...] 이면 i 번째 전송 항목의 오류다.
 * 요청 전체 오류(loc 가 ["body"])는 index 가 null 이다.
 * @param {unknown} body
 * @returns {Array<{index: number|null, message: string}>}
 */
export function itemErrorsFromBody(body) {
  const detail = /** @type {any} */ (body)?.detail;
  if (!Array.isArray(detail)) return [];
  return detail.map((item) => {
    const loc = Array.isArray(item?.loc) ? item.loc : [];
    const index = loc[0] === "body" && loc[1] === "items" && Number.isInteger(loc[2]) ? loc[2] : null;
    const msg = typeof item?.msg === "string" ? item.msg.replace(/^Value error,\s*/, "") : "입력값을 확인해 주세요.";
    return { index, message: msg };
  });
}

/**
 * 409 conflict_term 과 같은 표제어를 가진 첫 행의 인덱스. 서버가 요청 표기 그대로 보내므로 정확히 비교한다.
 * @param {Array<{term: string}>} rows
 * @param {string|null|undefined} conflictTerm
 * @returns {number} 없으면 -1
 */
export function findConflictRow(rows, conflictTerm) {
  if (!conflictTerm) return -1;
  return rows.findIndex((row) => row.term === conflictTerm);
}

/**
 * @param {{wordbookId: number, onDone?: () => void}} opts
 */
export function openBulkImport({ wordbookId, onDone = () => {} }) {
  if (!globalThis.Swal) return;
  const state = { rows: [], headerSkipped: false, parseError: "", onlyErrors: false, submitting: false, fileName: "", highlight: null };

  const fileInput = h("input", {
    type: "file",
    accept: ".csv,.tsv,.txt,text/csv,text/tab-separated-values,text/plain",
    class: "block w-full text-sm text-zinc-700 file:mr-3 file:min-h-[44px] file:rounded-xl file:border-0 file:bg-zinc-100 file:px-4 file:font-semibold",
    "aria-label": "CSV 또는 TSV 파일 선택",
    onchange: onFile,
  });
  const textarea = /** @type {HTMLTextAreaElement} */ (
    h("textarea", {
      rows: "6",
      class: `${INPUT_CLASS} font-mono`,
      "aria-label": "직접 입력 (표제어,뜻,예문)",
      placeholder: "apple,사과,An apple a day.\nbanana,바나나",
      oninput: () => {
        state.fileName = "";
        reparse();
      },
    })
  );
  const summary = h("p", { class: "text-sm text-zinc-600", "aria-live": "polite" });
  const banner = alertBox();
  const onlyErrorsBox = h("input", {
    type: "checkbox",
    class: "h-5 w-5",
    onchange: (e) => {
      state.onlyErrors = /** @type {HTMLInputElement} */ (e.target).checked;
      render();
    },
  });
  const list = h("ol", { class: "max-h-[50vh] space-y-2 overflow-y-auto pr-1" });
  const submitBtn = button({ full: true, onClick: submit }, "등록");
  submitBtn.disabled = true;

  const body = h(
    "div",
    { class: "space-y-4 text-left" },
    h("div", { class: "space-y-2" }, h("p", { class: "text-sm font-medium text-zinc-700" }, "파일에서 가져오기 (.csv, .tsv, .txt)"), fileInput),
    h("div", { class: "space-y-2" }, h("p", { class: "text-sm font-medium text-zinc-700" }, "직접 입력"), textarea),
    h("p", { class: "text-xs text-zinc-500" }, "한 줄에 한 단어입니다. 표제어,뜻 또는 표제어,뜻,예문 형식이며 탭으로 구분해도 됩니다. 한 번에 최대 100건입니다."),
    banner.el,
    summary,
    h("label", { class: "flex min-h-[44px] items-center gap-2 text-sm text-zinc-700" }, onlyErrorsBox, "오류 행만 보기"),
    list,
    submitBtn,
  );

  globalThis.Swal.fire({
    title: "단어 일괄 등록",
    html: body,
    showConfirmButton: false,
    showCloseButton: true,
    width: "min(96vw, 42rem)",
    allowOutsideClick: () => !state.submitting,
    allowEscapeKey: () => !state.submitting,
    didOpen: () => refreshIcons(),
  });
  render();

  /** @param {Event} event */
  async function onFile(event) {
    const file = /** @type {HTMLInputElement} */ (event.target).files?.[0];
    if (!file) return;
    if (file.size > MAX_FILE_BYTES) {
      banner.show("파일이 256KB를 넘습니다. 파일을 나눠 주세요.");
      return;
    }
    banner.hide();
    state.fileName = file.name;
    textarea.value = await file.text();
    reparse();
  }

  /** 입력 내용을 다시 파싱하고 화면을 갱신한다. 이전 강조는 지운다. */
  function reparse() {
    state.highlight = null;
    const parsed = parseBulkInput(textarea.value, state.fileName);
    state.rows = parsed.rows;
    state.headerSkipped = parsed.headerSkipped;
    state.parseError = parsed.parseError;
    render();
  }

  function validRows() {
    return state.rows.filter((row) => row.errors.length === 0);
  }

  function canSubmit() {
    return state.rows.length > 0 && !state.parseError && state.rows.every((r) => r.errors.length === 0) && !exceedsBulkLimit(state.rows.length) && !state.submitting;
  }

  function render() {
    const errorCount = state.rows.filter((row) => row.errors.length > 0).length;
    summary.textContent = state.rows.length
      ? `${state.rows.length}건을 읽었습니다. 오류 ${errorCount}건.${state.headerSkipped ? " 첫 줄은 헤더로 보고 건너뛰었습니다." : ""}`
      : "파일을 고르거나 내용을 붙여넣으면 여기에 미리 보입니다.";
    if (state.parseError) banner.show(state.parseError);
    else if (exceedsBulkLimit(state.rows.length)) banner.show(`한 번에 ${BULK_MAX_ITEMS}건까지 등록할 수 있습니다. 파일을 나눠 선택해 주세요. 나눠 등록하면 묶음마다 따로 저장되므로 전체가 한꺼번에 저장되지는 않습니다.`);
    else if (!state.highlight) banner.hide();
    submitBtn.disabled = !canSubmit();
    submitBtn.textContent = state.rows.length ? `${state.rows.length}건 등록` : "등록";

    clear(list);
    state.rows.forEach((row, index) => {
      if (state.onlyErrors && row.errors.length === 0) return;
      const conflicted = state.highlight?.index === index;
      list.append(
        h(
          "li",
          {
            class: `p-3 rounded-xl ${row.errors.length || conflicted ? "border border-red-300 bg-red-50" : "surface"}`,
            dataset: { rowIndex: String(index) },
            "aria-invalid": String(row.errors.length > 0 || conflicted),
          },
          h("p", { class: "text-xs text-zinc-500" }, `${row.lineNo}행`),
          h("p", { class: "break-words font-semibold text-zinc-900" }, row.term || "(표제어 없음)"),
          h("p", { class: "break-words text-sm text-zinc-700" }, row.meaning || "(뜻 없음)"),
          row.example ? h("p", { class: "break-words text-sm text-zinc-500" }, row.example) : null,
          row.errors.length || conflicted
            ? h(
                "p",
                { class: "mt-1 flex items-start gap-1 text-sm text-red-700" },
                icon("alert-triangle", "h-4 w-4 mt-0.5 shrink-0"),
                h("span", {}, conflicted ? state.highlight.message : row.errors.join(" ")),
              )
            : null,
        ),
      );
    });
    refreshIcons();
  }

  async function submit() {
    const payload = buildBulkPayload(state.rows);
    const rowsSent = validRows();
    state.submitting = true;
    state.highlight = null;
    submitBtn.disabled = true;
    submitBtn.setAttribute("aria-busy", "true");
    render();
    try {
      await api(`/wordbooks/${wordbookId}/words/bulk`, { method: "POST", body: payload });
      toast(`${payload.items.length}개 단어를 등록했습니다.`);
      globalThis.Swal.close();
      onDone();
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        const term = error.body?.conflict_term ?? null;
        const index = findConflictRow(state.rows, term);
        const message = term
          ? `'${term}'은(는) 이미 이 단어장에 있습니다. 아무 단어도 저장되지 않았습니다.`
          : "기존 단어와 겹치는 표제어가 있습니다. 아무 단어도 저장되지 않았습니다.";
        state.highlight = index >= 0 ? { index, message } : null;
        banner.show(message);
      } else if (error instanceof ApiError && error.status === 422) {
        const itemErrors = itemErrorsFromBody(error.body);
        const requestWide = itemErrors.filter((e) => e.index === null);
        if (requestWide.length) banner.show(requestWide[0].message);
        const first = itemErrors.find((e) => e.index !== null);
        if (first) {
          const rowIndex = state.rows.indexOf(rowsSent[first.index]);
          if (rowIndex >= 0) state.highlight = { index: rowIndex, message: first.message };
        }
        if (!requestWide.length && !first) banner.show(error.detail);
      } else if (error instanceof ApiError && error.status === 404) {
        banner.show("단어장을 찾을 수 없습니다.");
      } else if (error instanceof ApiError && error.status === 401) {
        globalThis.Swal.close();
      } else {
        banner.show(error.detail ?? "등록하지 못했습니다.");
      }
    } finally {
      state.submitting = false;
      submitBtn.removeAttribute("aria-busy");
      render();
    }
  }
}
