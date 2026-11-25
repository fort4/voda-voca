/*
 * 2026-11-26 - voda-voca - 관리자 화면 모델: 관리 가능 판정, 단어장·단어 입력 검증, 오류 문구, 삭제 안내, CSV 일괄 등록 (DOM 없는 순수 로직, REQ-160~162)
 * 파일 위치: src/frontend/js/core/admin-model.js
 */

import { CATEGORY_LABELS } from "./explore-model.js";

/** 서버 길이 한도(schemas/admin.py)와 같다. */
export const ADMIN_LIMITS = Object.freeze({ title: 100, description: 255, term: 100, meaning: 200, example: 500, example_meaning: 500 });

/** 새 단어장에서 고를 수 있는 분류. */
export const VOCABULARY_CATEGORIES = Object.freeze(
  ["ELEMENTARY", "SECONDARY", "CSAT", "EXAM", "BUSINESS", "ETC"].map((value) => Object.freeze({ value, label: CATEGORY_LABELS[value] })),
);

const FIELD_LABELS = Object.freeze({
  title: "제목",
  description: "설명",
  category: "분류",
  level: "레벨",
  term: "표제어",
  meaning: "뜻",
  example: "예문",
  example_meaning: "예문 뜻",
});

const REQUIRED_MESSAGES = Object.freeze({ title: "제목을 입력해 주세요.", term: "표제어를 입력해 주세요.", meaning: "뜻을 입력해 주세요." });

const FALLBACK_ERROR = "저장하지 못했어요. 다시 시도해 주세요.";

/**
 * 수정·삭제 버튼을 보일지. 서버도 같은 규칙으로 막는다 (표준 콘텐츠는 읽기 전용).
 * @param {{is_admin?: boolean}|null} user
 * @param {{source?: string}} item 단어장 또는 단어
 */
export function canEditContent(user, item) {
  return user?.is_admin === true && item?.source === "admin";
}

/**
 * 단어 시트를 여는 버튼의 이름과 아이콘. 관리자에게는 시트가 단어를 관리하는 곳이라 이름으로 알린다.
 * @param {{is_admin?: boolean}|null} user
 */
export function wordSheetEntry(user) {
  return user?.is_admin === true ? { label: "단어 관리", icon: "list-checks" } : { label: "미리보기", icon: "eye" };
}

/** 필수·길이 검사를 하고 공백을 지운 값(비면 null)을 돌려준다. */
function checkTexts(values, names, required) {
  const errors = {};
  const cleaned = {};
  for (const name of names) {
    const text = String(values[name] ?? "").trim();
    if (!text && required.includes(name)) errors[name] = REQUIRED_MESSAGES[name];
    else if (text.length > ADMIN_LIMITS[name]) errors[name] = `${FIELD_LABELS[name]}: ${ADMIN_LIMITS[name]}자 이하여야 합니다.`;
    cleaned[name] = text || null;
  }
  return { errors, cleaned };
}

/** @param {Record<string, string>} values @returns {{errors: Record<string, string>, body: object}} */
export function wordForm(values) {
  const { errors, cleaned } = checkTexts(values, ["term", "meaning", "example", "example_meaning"], ["term", "meaning"]);
  if (!cleaned.example) cleaned.example_meaning = null; // 예문이 없으면 예문 뜻도 두지 않는다
  return { errors, body: cleaned };
}

/** @param {Record<string, string>} values @param {{creating: boolean}} options 수정은 제목과 설명만 바꾼다 */
export function vocabularyForm(values, { creating }) {
  const { errors, cleaned } = checkTexts(values, ["title", "description"], ["title"]);
  const body = creating ? { ...cleaned, category: values.category, level: Number(values.level) } : cleaned;
  return { errors, body };
}

/** @param {{detail?: string, status?: number, fields?: Array<{field: string|null, message: string}>}} error */
export function adminFailureMessage(error) {
  if (error.status === 422 && error.fields?.length) {
    const { field, message } = error.fields[0];
    return FIELD_LABELS[field] ? `${FIELD_LABELS[field]}: ${message}` : message;
  }
  return error.detail ?? FALLBACK_ERROR;
}

/** @param {{term: string}} word */
export function deleteWordPrompt(word) {
  return {
    title: `'${word.term}' 단어를 삭제할까요?`,
    text: "모든 사용자의 이 단어 학습 이력, 진도, 북마크도 함께 지워지고 통계 값이 달라질 수 있어요. 되돌릴 수 없습니다.",
  };
}

/** @param {{title: string, total_words: number}} vocabulary */
export function deleteVocabularyPrompt(vocabulary) {
  return {
    title: `'${vocabulary.title}' 단어장을 삭제할까요?`,
    text: `${vocabulary.total_words}단어와 모든 사용자의 학습 이력, 진도, 북마크, 진행 중인 학습이 함께 지워져요. 되돌릴 수 없습니다.`,
  };
}

/** CSV 일괄 등록의 상한과 본문 형식. 서버(services/csv_import.py)와 같다. */
export const CSV_IMPORT = Object.freeze({ maxBytes: 512 * 1024, maxRows: 500, contentType: "text/csv" });

/**
 * 보내기 전에 알 수 있는 파일 문제. 내용(인코딩, 열, 행)은 서버가 검사한다.
 * @param {{name: string, size: number}|undefined|null} file
 * @returns {string|null} 문제가 없으면 null
 */
export function csvFileError(file) {
  if (!file) return "CSV 파일을 골라 주세요.";
  if (!file.name.toLowerCase().endsWith(".csv")) return "CSV 파일(.csv)만 올릴 수 있어요. 엑셀에서는 'CSV UTF-8'로 저장해 주세요.";
  if (file.size > CSV_IMPORT.maxBytes) return `파일은 ${CSV_IMPORT.maxBytes / 1024}KB 이하여야 합니다.`;
  return null;
}

/** @param {{created: number, skipped: number}} result */
export function importResultText({ created, skipped }) {
  const done = created > 0 ? `${created}단어를 등록했어요.` : "새로 등록한 단어가 없어요.";
  return skipped > 0 ? `${done} 이미 있는 표제어 ${skipped}건은 건너뛰었어요.` : done;
}

/**
 * @param {{detail?: string, body?: {errors?: Array<{row: number, message: string}>}|null}} error
 * @returns {{message: string, rows: string[]}} 안내 문구와 오류 행 목록
 */
export function importFailure(error) {
  const rows = Array.isArray(error.body?.errors) ? error.body.errors.map((e) => `${e.row}행: ${e.message}`) : [];
  return { message: error.detail ?? FALLBACK_ERROR, rows };
}
