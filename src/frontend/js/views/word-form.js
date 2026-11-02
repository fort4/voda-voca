/*
 * 2026-11-02 - voda-voca - 단어 등록·수정·삭제 모달: 변경 필드만 PATCH, 409 는 표제어 칸에 표시, 삭제는 CASCADE 안내 후 확인 (REQ-008~011)
 * 파일 위치: src/frontend/js/views/word-form.js
 */

import { api, ApiError } from "../core/api.js";
import { h } from "../core/dom.js";
import { field } from "../core/form.js";
import { confirmDialog, toast } from "../core/toast.js";
import { validateWordExample, validateWordMeaning, validateWordTerm } from "../core/validate.js";

/**
 * @param {{wordbookId: number, word?: null | {id: number, term: string, meaning: string, example: string|null}, onChanged?: (kind: "created"|"updated"|"deleted") => void}} opts
 * @returns {Promise<void>}
 */
export async function openWordForm({ wordbookId, word = null, onChanged = () => {} }) {
  if (!globalThis.Swal) return;
  const term = field({ id: "w-term", label: "표제어", autocomplete: "off", maxlength: 100, value: word?.term ?? "" });
  const meaning = field({ id: "w-meaning", label: "뜻", autocomplete: "off", maxlength: 200, value: word?.meaning ?? "" });
  const example = field({ id: "w-example", label: "예문 (선택)", autocomplete: "off", maxlength: 500, value: word?.example ?? "" });
  const form = h("form", { class: "space-y-4 text-left", novalidate: true, onsubmit: (e) => e.preventDefault() }, term.wrap, meaning.wrap, example.wrap);

  const result = await globalThis.Swal.fire({
    title: word ? "단어 수정" : "단어 추가",
    html: form,
    showCancelButton: true,
    showDenyButton: Boolean(word),
    denyButtonText: "삭제",
    denyButtonColor: "#dc2626",
    confirmButtonText: word ? "저장" : "추가",
    cancelButtonText: "취소",
    focusConfirm: false,
    preConfirm: async () => {
      const values = {
        term: term.input.value.trim(),
        meaning: meaning.input.value.trim(),
        example: example.input.value.trim() || null,
      };
      const errors = {
        term: validateWordTerm(values.term),
        meaning: validateWordMeaning(values.meaning),
        example: validateWordExample(values.example ?? ""),
      };
      term.setError(errors.term);
      meaning.setError(errors.meaning);
      example.setError(errors.example);
      const first = errors.term || errors.meaning || errors.example;
      if (first) {
        globalThis.Swal.showValidationMessage(first);
        return false;
      }
      try {
        if (word) {
          const changed = diffWord(word, values);
          if (Object.keys(changed).length === 0) return "unchanged";
          await api(`/wordbooks/${wordbookId}/words/${word.id}`, { method: "PATCH", body: changed });
          return "updated";
        }
        await api(`/wordbooks/${wordbookId}/words`, { method: "POST", body: values });
        return "created";
      } catch (error) {
        if (error instanceof ApiError && error.status === 409) {
          term.setError(error.detail);
        }
        globalThis.Swal.showValidationMessage(error instanceof ApiError ? error.detail : "저장하지 못했습니다.");
        return false;
      }
    },
  });

  if (result.isDenied && word) {
    await removeWord(wordbookId, word, onChanged);
    return;
  }
  if (!result.isConfirmed || !result.value) return;
  if (result.value === "unchanged") return;
  toast(result.value === "created" ? "단어를 추가했습니다." : "단어를 수정했습니다.");
  onChanged(result.value);
}

/**
 * 원래 값과 비교해 바뀐 필드만 골라낸다. 예문은 null 로 지울 수 있다.
 * @param {{term: string, meaning: string, example: string|null}} original
 * @param {{term: string, meaning: string, example: string|null}} next
 * @returns {Partial<{term: string, meaning: string, example: string|null}>}
 */
export function diffWord(original, next) {
  const changed = {};
  if (next.term !== original.term) changed.term = next.term;
  if (next.meaning !== original.meaning) changed.meaning = next.meaning;
  if ((next.example ?? null) !== (original.example ?? null)) changed.example = next.example ?? null;
  return changed;
}

/**
 * 삭제 확인 후 단어를 지운다. 북마크와 학습 이력도 함께 지워진다는 점을 확인 문구에 적는다 (REQ-011).
 * @param {number} wordbookId
 * @param {{id: number, term: string}} word
 * @param {(kind: "deleted") => void} onChanged
 */
async function removeWord(wordbookId, word, onChanged) {
  const ok = await confirmDialog({
    title: `'${word.term}' 단어를 삭제할까요?`,
    text: "이 단어의 북마크와 학습 기록도 함께 삭제됩니다. 되돌릴 수 없습니다.",
    confirmText: "삭제",
    danger: true,
  });
  if (!ok) return;
  try {
    await api(`/wordbooks/${wordbookId}/words/${word.id}`, { method: "DELETE" });
    toast("단어를 삭제했습니다.");
    onChanged("deleted");
  } catch (error) {
    toast(error.detail ?? "삭제하지 못했습니다.", "error");
    if (error.status === 404) onChanged("deleted");
  }
}
