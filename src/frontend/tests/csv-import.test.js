/*
 * 2026-11-26 - voda-voca - CSV 일괄 등록 화면 검사: 원문 본문 전송, 파일 확인, 결과·오류 문구, 화면 배선 (REQ-171)
 * 파일 위치: src/frontend/tests/csv-import.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { CSV_IMPORT, csvFileError, importFailure, importResultText } from "../js/core/content-model.js";
import { api, toApiError } from "../js/core/api.js";

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), "utf8");

test("api: contentType 을 주면 본문을 JSON 으로 바꾸지 않고 그대로 보낸다", async () => {
  const body = new TextEncoder().encode("term,meaning\n").buffer;
  let sent;
  const fetchImpl = async (url, init) => {
    sent = { url, init };
    return new Response(JSON.stringify({ created: 1, skipped: 0 }), { status: 200, headers: { "Content-Type": "application/json" } });
  };

  const data = await api("/vocabularies/3/words/import", { method: "POST", body, contentType: "text/csv", fetchImpl });

  assert.equal(sent.init.body, body);
  assert.equal(sent.init.headers["Content-Type"], "text/csv");
  assert.equal(sent.init.credentials, "include");
  assert.deepEqual(data, { created: 1, skipped: 0 });
});

test("상한은 서버(services/csv_import.py)와 같다", () => {
  const server = read("../backend/services/csv_import.py");
  assert.equal(CSV_IMPORT.maxBytes, 1024 * 1024);
  assert.equal(CSV_IMPORT.maxRows, 3000);
  assert.match(server, /MAX_FILE_BYTES = 1024 \* 1024/);
  assert.match(server, new RegExp(`MAX_ROWS = ${CSV_IMPORT.maxRows}\\b`));
  assert.equal(CSV_IMPORT.contentType, "text/csv");
});

test("csvFileError: 고르지 않음, 다른 형식, 크기 초과를 보내기 전에 알린다", () => {
  assert.match(csvFileError(undefined), /골라/);
  assert.match(csvFileError({ name: "words.xlsx", size: 10 }), /CSV UTF-8/);
  assert.match(csvFileError({ name: "words.csv", size: CSV_IMPORT.maxBytes + 1 }), /1024KB/);
  assert.equal(csvFileError({ name: "WORDS.CSV", size: CSV_IMPORT.maxBytes }), null);
});

test("importResultText: 등록 건수와 건너뛴 건수를 보인다", () => {
  assert.equal(importResultText({ created: 498, skipped: 2 }), "498단어를 등록했어요. 이미 있는 표제어 2건은 건너뛰었어요.");
  assert.equal(importResultText({ created: 3, skipped: 0 }), "3단어를 등록했어요.");
  assert.equal(importResultText({ created: 0, skipped: 5 }), "새로 등록한 단어가 없어요. 이미 있는 표제어 5건은 건너뛰었어요.");
});

test("importFailure: 파일 오류는 행 번호 목록을 함께 보인다", () => {
  const error = toApiError(400, new Headers({ "X-Error-Code": "CSV_INVALID" }), {
    detail: "오류가 있는 행이 1개라 파일 전체를 등록하지 않았습니다.",
    errors: [{ row: 3, message: "뜻이 비어 있습니다." }],
  });

  assert.deepEqual(importFailure(error), {
    message: "오류가 있는 행이 1개라 파일 전체를 등록하지 않았습니다.",
    rows: ["3행: 뜻이 비어 있습니다."],
  });
});

test("importFailure: 행 목록이 없는 오류는 안내 문구만 보인다", () => {
  const error = toApiError(413, new Headers(), { detail: "파일은 512KB 이하여야 합니다." });

  assert.deepEqual(importFailure(error), { message: "파일은 512KB 이하여야 합니다.", rows: [] });
});

test("단어 시트: 'CSV 등록' 뒤 목록과 단어 수를 새로 고친다", () => {
  const sheet = read("js/views/components/word-sheet.js");
  assert.match(sheet, /openImportForm\([\s\S]{0,80}&& afterChange\(\)/);
});

test("등록 모달: CSV 만 고르고, 오류는 모달을 연 채 글자로만 보인다", () => {
  const forms = read("js/views/components/content-forms.js");
  const modal = forms.slice(forms.indexOf("function openImportForm"), forms.indexOf("function confirmAndDelete"));
  assert.match(modal, /type:\s*"file"/);
  assert.match(modal, /영단어,뜻/, "과제 제공 파일의 열 이름을 안내한다");
  assert.match(modal, /accept:\s*"\.csv,text\/csv"/);
  assert.match(modal, /\/words\/import/);
  assert.match(modal, /arrayBuffer\(\)/);
  assert.match(modal, /preConfirm/);
  assert.match(modal, /showLoaderOnConfirm:\s*true/);
  assert.match(modal, /role:\s*"alert"/);
  // 서버 오류 문구에는 파일 내용(열 이름)이 섞이므로 HTML 로 해석하는 showValidationMessage 를 쓰지 않는다
  assert.doesNotMatch(modal, /showValidationMessage|innerHTML/);
});
