/*
 * 2026-11-02 - voda-voca - 단어장 CSV 백업: 전체 단어장과 단어를 페이지로 받아 하나의 CSV 로 내려받는다 (직렬화는 순수 함수로 분리)
 * 파일 위치: src/frontend/js/core/backup.js
 * 전체 백업(단어장 열 포함)과 개별 단어장 내보내기(가져오기 규격과 같은 4열)를 모두 다룬다.
 */

import { api } from "./api.js";
import { kstDayKeyOf } from "./stats.js";

export const BACKUP_HEADER = ["단어장", "표제어", "뜻", "예문", "예문 뜻"];
/** 개별 단어장 파일 헤더. 일괄 등록(가져오기)에서 그대로 다시 읽을 수 있다. */
export const WORDBOOK_HEADER = ["표제어", "뜻", "예문", "예문 뜻"];
const PAGE_SIZE = 100; // 서버의 목록 최대 페이지 크기

/**
 * CSV 셀 하나를 이스케이프한다. 쉼표, 따옴표, 줄바꿈이 있으면 큰따옴표로 감싼다.
 * @param {unknown} value
 * @returns {string}
 */
export function csvCell(value) {
  const text = value === null || value === undefined ? "" : String(value);
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

/**
 * 백업 CSV 본문을 만든다. 첫 줄은 헤더, 줄바꿈은 CRLF 다.
 * @param {Array<{wordbook: string, term: string, meaning: string, example: string|null, exampleMeaning: string|null}>} rows
 * @returns {string}
 */
export function buildBackupCsv(rows) {
  const lines = [BACKUP_HEADER.map(csvCell).join(",")];
  for (const row of rows) {
    lines.push([row.wordbook, row.term, row.meaning, row.example, row.exampleMeaning].map(csvCell).join(","));
  }
  return lines.join("\r\n");
}

/**
 * 개별 단어장 CSV 본문. 첫 줄은 표제어,뜻,예문,예문 뜻 헤더다.
 * @param {Array<{term: string, meaning: string, example: string|null, exampleMeaning: string|null}>} words
 * @returns {string}
 */
export function buildWordbookCsv(words) {
  const lines = [WORDBOOK_HEADER.map(csvCell).join(",")];
  for (const word of words) {
    lines.push([word.term, word.meaning, word.example, word.exampleMeaning].map(csvCell).join(","));
  }
  return lines.join("\r\n");
}

/**
 * 파일 이름 안전하게 만들기: 공백은 밑줄, 경로와 특수문자는 제거한다. 한글은 그대로 둔다.
 * @param {string} name
 * @returns {string}
 */
export function safeFileStem(name) {
  const cleaned = name.trim().replace(/[\\/:*?"<>|\u0000-\u001f]/g, "").replace(/\s+/g, "_");
  return cleaned || "단어장";
}

/**
 * 개별 단어장 파일 이름: [단어장_이름]_YYYYMMDD.csv
 * @param {string} wordbookName
 * @param {number} [now=Date.now()]
 * @returns {string}
 */
export function wordbookFileName(wordbookName, now = Date.now()) {
  return `${safeFileStem(wordbookName)}_${kstDayKeyOf(now).replaceAll("-", "")}.csv`;
}

/**
 * 파일 이름: 보다보카-단어장-YYYYMMDD.csv (한국 날짜 기준).
 * @param {number} [now=Date.now()]
 * @returns {string}
 */
export function backupFileName(now = Date.now()) {
  return `보다보카-단어장-${kstDayKeyOf(now).replaceAll("-", "")}.csv`;
}

/**
 * 한 목록 API 를 끝까지 받는다 (total 을 채울 때까지 페이지를 넘긴다).
 * @param {string} path
 * @param {Record<string, unknown>} [query]
 * @returns {Promise<Array<any>>}
 */
export async function fetchAllPages(path, query = {}) {
  const items = [];
  for (let page = 1; ; page += 1) {
    const data = await api(path, { query: { ...query, page, size: PAGE_SIZE } });
    items.push(...data.items);
    if (data.items.length === 0 || items.length >= data.total) return items;
  }
}

/**
 * 내 모든 단어장의 단어를 백업 행으로 모은다.
 * @returns {Promise<Array<{wordbook: string, term: string, meaning: string, example: string|null, exampleMeaning: string|null}>>}
 */
export async function collectBackupRows() {
  const wordbooks = await fetchAllPages("/wordbooks");
  const rows = [];
  for (const book of wordbooks) {
    const words = await fetchAllPages(`/wordbooks/${book.id}/words`);
    for (const word of words) {
      rows.push({
        wordbook: book.name,
        term: word.term,
        meaning: word.meaning,
        example: word.example ?? null,
        exampleMeaning: word.example_meaning ?? null,
      });
    }
  }
  return rows;
}

/**
 * CSV 본문을 BOM 과 함께 내려받는다. 엑셀에서 한글이 깨지지 않도록 BOM 을 붙인다.
 * @param {string} fileName
 * @param {string} body
 */
export function downloadCsv(fileName, body) {
  const blob = new Blob(["\uFEFF", body], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/**
 * 단어장 한 개의 단어를 모두 받아 행으로 만든다.
 * @param {number} wordbookId
 * @returns {Promise<Array<{term: string, meaning: string, example: string|null, exampleMeaning: string|null}>>}
 */
export async function collectWordbookWords(wordbookId) {
  const words = await fetchAllPages(`/wordbooks/${wordbookId}/words`);
  return words.map((word) => ({
    term: word.term,
    meaning: word.meaning,
    example: word.example ?? null,
    exampleMeaning: word.example_meaning ?? null,
  }));
}

/**
 * 개별 단어장을 CSV 로 내려받는다.
 * @param {{id: number, name: string}} wordbook
 * @returns {Promise<number>} 내려받은 단어 수
 */
export async function downloadWordbook(wordbook) {
  const words = await collectWordbookWords(wordbook.id);
  downloadCsv(wordbookFileName(wordbook.name), buildWordbookCsv(words));
  return words.length;
}

/**
 * 백업 CSV 를 내려받는다 (모든 단어장의 합본).
 * @returns {Promise<number>} 내려받은 단어 수
 */
export async function downloadBackup() {
  const rows = await collectBackupRows();
  downloadCsv(backupFileName(), buildBackupCsv(rows));
  return rows.length;
}
