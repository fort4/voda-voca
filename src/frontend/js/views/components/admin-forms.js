/*
 * 2026-11-26 - voda-voca - 관리자 입력 모달: 단어장·단어 추가와 수정, 삭제 확인 (SweetAlert2, REQ-160, REQ-161)
 * 파일 위치: src/frontend/js/views/components/admin-forms.js
 */

import {
  ADMIN_LIMITS,
  VOCABULARY_CATEGORIES,
  adminFailureMessage,
  deleteVocabularyPrompt,
  deleteWordPrompt,
  vocabularyForm,
  wordForm,
} from "../../core/admin-model.js";
import { api } from "../../core/api.js";
import { h } from "../../core/dom.js";
import { INPUT_CLASS, field } from "../../core/form.js";
import { confirmDialog, toast } from "../../core/toast.js";

const LEVELS = [1, 2, 3, 4, 5];

/** 모달 안의 글자 입력. 값 길이는 서버 한도에서 막는다. */
function textInput(name, label, value = "") {
  return field({ id: `admin-${name}`, label, value: value ?? "", maxlength: ADMIN_LIMITS[name], autocomplete: "off" });
}

function selectInput(name, label, options) {
  const id = `admin-${name}`;
  const input = h("select", { id, class: INPUT_CLASS }, options.map(([value, text]) => h("option", { value }, text)));
  return { wrap: h("div", { class: "space-y-1" }, h("label", { for: id, class: "block text-sm font-medium text-zinc-700" }, label), input), input };
}

/**
 * 입력 모달. 저장에 실패하면 모달을 연 채 이유를 보인다.
 * @param {{title: string, fields: Record<string, {wrap: HTMLElement, input: HTMLInputElement|HTMLSelectElement, setError?: (m: string|null) => void}>,
 *          check: (values: Record<string, string>) => {errors: Record<string, string>, body: object},
 *          send: (body: object) => Promise<any>}} options
 * @returns {Promise<any|null>} 저장한 서버 응답. 취소하면 null
 */
async function openForm({ title, fields, check, send }) {
  const Swal = globalThis.Swal;
  if (!Swal) return null;
  const result = await Swal.fire({
    title,
    html: h("div", { class: "space-y-3 text-left" }, Object.values(fields).map((f) => f.wrap)),
    showCancelButton: true,
    confirmButtonText: "저장",
    cancelButtonText: "취소",
    reverseButtons: true,
    showLoaderOnConfirm: true,
    allowOutsideClick: false, // 입력 중에 바깥을 눌러 내용이 사라지지 않게 한다
    preConfirm: async () => {
      Swal.resetValidationMessage();
      const values = Object.fromEntries(Object.entries(fields).map(([name, f]) => [name, f.input.value]));
      const { errors, body } = check(values);
      for (const [name, f] of Object.entries(fields)) f.setError?.(errors[name] ?? null);
      if (Object.keys(errors).length > 0) return false;
      try {
        return await send(body);
      } catch (error) {
        Swal.showValidationMessage(adminFailureMessage(error));
        return false;
      }
    },
  });
  return result.isConfirmed ? result.value : null;
}

/**
 * 새 단어장 또는 관리자 단어장 수정.
 * @param {{id: number, title: string, description: string|null}} [vocabulary] 있으면 수정
 */
export async function openVocabularyForm(vocabulary) {
  const creating = !vocabulary;
  const fields = {
    title: textInput("title", "제목", vocabulary?.title),
    description: textInput("description", "설명 (선택)", vocabulary?.description),
  };
  if (creating) {
    fields.category = selectInput("category", "분류", VOCABULARY_CATEGORIES.map((c) => [c.value, c.label]));
    fields.category.input.value = "ETC";
    fields.level = selectInput("level", "레벨", LEVELS.map((level) => [String(level), `Lv.${level}`]));
  }
  const saved = await openForm({
    title: creating ? "새 단어장" : "단어장 수정",
    fields,
    check: (values) => vocabularyForm(values, { creating }),
    send: (body) =>
      creating
        ? api("/admin/vocabularies", { method: "POST", body })
        : api(`/admin/vocabularies/${vocabulary.id}`, { method: "PATCH", body }),
  });
  if (saved) toast(creating ? "단어장을 만들었어요" : "단어장을 고쳤어요");
  return saved;
}

/**
 * 단어 추가 또는 관리자 단어 수정.
 * @param {{vocabularyId: number, word?: {word_id: number, term: string, meaning: string, example: string|null, example_meaning: string|null}}} options
 */
export async function openWordForm({ vocabularyId, word }) {
  const saved = await openForm({
    title: word ? "단어 수정" : "단어 추가",
    fields: {
      term: textInput("term", "표제어", word?.term),
      meaning: textInput("meaning", "뜻", word?.meaning),
      example: textInput("example", "예문 (선택)", word?.example),
      example_meaning: textInput("example_meaning", "예문 뜻 (선택)", word?.example_meaning),
    },
    check: wordForm,
    send: (body) =>
      word
        ? api(`/admin/words/${word.word_id}`, { method: "PUT", body })
        : api(`/admin/vocabularies/${vocabularyId}/words`, { method: "POST", body }),
  });
  if (saved) toast(word ? "단어를 고쳤어요" : `'${saved.term}' 단어를 추가했어요`);
  return saved;
}

/** 확인을 받고 지운다. @returns {Promise<boolean>} 지웠는지 */
async function confirmAndDelete(prompt, path) {
  const ok = await confirmDialog({ ...prompt, confirmText: "삭제", danger: true });
  if (!ok) return false;
  try {
    await api(path, { method: "DELETE" });
  } catch (error) {
    toast(adminFailureMessage(error), "error");
    return false;
  }
  toast("삭제했어요");
  return true;
}

/** @param {{word_id: number, term: string}} word */
export function confirmDeleteWord(word) {
  return confirmAndDelete(deleteWordPrompt(word), `/admin/words/${word.word_id}`);
}

/** @param {{id: number, title: string, total_words: number}} vocabulary */
export function confirmDeleteVocabulary(vocabulary) {
  return confirmAndDelete(deleteVocabularyPrompt(vocabulary), `/admin/vocabularies/${vocabulary.id}`);
}
