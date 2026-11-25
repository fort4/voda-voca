/*
 * 2026-11-26 - voda-voca - 관리자 화면 배선 검사: 탐색의 단어장 관리, 미리보기 시트의 단어 관리, 입력 모달 (REQ-160, REQ-161)
 * 파일 위치: src/frontend/tests/admin-ui.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { wordSheetEntry } from "../js/core/admin-model.js";

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
const explore = read("js/views/explore-view.js");
const sheet = read("js/views/components/word-sheet.js");

test("탐색: 관리자에게만 '새 단어장'을 보이고, 관리자 단어장 카드에만 수정·삭제를 둔다", () => {
  assert.match(explore, /is_admin[\s\S]{0,300}"새 단어장"/);
  assert.match(explore, /canEditContent\(/);
  assert.match(explore, /openVocabularyForm\(/);
  assert.match(explore, /confirmDeleteVocabulary\(/);
  assert.match(explore, /normalizeFilter\(/, "삭제 뒤 필터를 정리한다");
});

test("미리보기 시트: 관리자에게 '단어 추가', 관리자 단어에만 수정·삭제(44px, 이름표)를 둔다", () => {
  assert.match(sheet, /is_admin[\s\S]{0,300}"단어 추가"/);
  assert.match(sheet, /canEditContent\(/);
  assert.match(sheet, /openWordForm\(/);
  assert.match(sheet, /confirmDeleteWord\(/);
  assert.match(sheet, /"aria-label":\s*`\$\{word\.term\} 수정`/);
  assert.match(sheet, /"aria-label":\s*`\$\{word\.term\} 삭제`/);
  assert.match(sheet, /btn-icon/);
  assert.match(sheet, /pager\.reload\(\)/);
  assert.match(sheet, /onWordsChanged/, "탐색 화면의 단어 수를 새로 고친다");
});

test("미리보기 시트: 위에 모달이 열려 있으면 Esc 로 시트를 닫지 않는다", () => {
  assert.match(sheet, /\.swal2-popup:not\(\.swal2-toast\)/);
});

test("입력 모달: 서버 관리 API 를 부르고, 실패하면 모달을 연 채 이유를 보인다", () => {
  const src = read("js/views/components/admin-forms.js");
  for (const path of ["/admin/vocabularies", "/words", "/admin/words/"]) assert.ok(src.includes(path), path);
  for (const method of ['"POST"', '"PATCH"', '"PUT"', '"DELETE"']) assert.ok(src.includes(method), method);
  assert.match(src, /preConfirm/);
  assert.match(src, /showValidationMessage\(/);
  assert.match(src, /showLoaderOnConfirm:\s*true/);
  assert.match(src, /confirmDialog\(\{[^}]*danger:\s*true/s, "삭제는 확인을 받는다");
  assert.doesNotMatch(src, /innerHTML/);
});

test("단어 시트 진입: 관리자에게는 '단어 관리', 그 밖에는 '미리보기'다", () => {
  assert.deepEqual(wordSheetEntry({ is_admin: true }), { label: "단어 관리", icon: "list-checks" });
  assert.deepEqual(wordSheetEntry({ is_admin: false }), { label: "미리보기", icon: "eye" });
  assert.deepEqual(wordSheetEntry(null), { label: "미리보기", icon: "eye" });
});

test("탐색 카드의 버튼과 시트의 이름이 같은 진입 이름을 쓴다", () => {
  assert.match(explore, /wordSheetEntry\(this\.user\)/);
  assert.match(explore, /openWordSheet\([\s\S]{0,120}icon\(entry\.icon[\s\S]{0,40}entry\.label/);
  assert.match(sheet, /"aria-label":\s*`\$\{vocabulary\.title\} \$\{wordSheetEntry\(user\)\.label\}`/);
});
