/*
 * 2026-11-26 - voda-voca - 개인 단어장 화면 배선 검사: 탐색의 단어장 관리, 시트의 단어 관리, 입력 모달, 관리자 잔재 없음 (#39, #41)
 * 파일 위치: src/frontend/tests/content-ui.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
const explore = read("js/views/explore-view.js");
const sheet = read("js/views/components/word-sheet.js");

test("탐색: 누구나 '새 단어장'을 만들고, 내 단어장 카드에만 수정·삭제를 둔다", () => {
  assert.match(explore, /"새 단어장"/);
  assert.match(explore, /canEditContent\(vocabulary\) \? this\.ownerActions\(vocabulary\) : null/);
  assert.match(explore, /openVocabularyForm\(/);
  assert.match(explore, /confirmDeleteVocabulary\(/);
  assert.match(explore, /normalizeFilter\(/, "삭제 뒤 필터를 정리한다");
  assert.match(explore, /c\.metaText/);
  assert.match(explore, /!c\.canStudy/, "빈 단어장은 학습으로 고르지 못한다");
});

test("단어 시트: 내 단어장에서만 '단어 추가'·'CSV 등록'과 수정·삭제(44px, 이름표)를 보인다", () => {
  assert.match(sheet, /const editable = canEditContent\(vocabulary\)/);
  assert.match(sheet, /editable[\s\S]{0,300}"단어 추가"/);
  assert.match(sheet, /"CSV 등록"/);
  assert.match(sheet, /editable \? ownerActions\(word\) : null/);
  assert.match(sheet, /openWordForm\(/);
  assert.match(sheet, /confirmDeleteWord\(/);
  assert.match(sheet, /"aria-label":\s*`\$\{word\.term\} 수정`/);
  assert.match(sheet, /"aria-label":\s*`\$\{word\.term\} 삭제`/);
  assert.match(sheet, /btn-icon/);
  assert.match(sheet, /pager\.reload\(\)/);
  assert.match(sheet, /onWordsChanged/, "탐색 화면의 단어 수를 새로 고친다");
});

test("단어 시트: 위에 모달이 열려 있으면 Esc 로 시트를 닫지 않는다", () => {
  assert.match(sheet, /\.swal2-popup:not\(\.swal2-toast\)/);
});

test("입력 모달: 내 단어장 API 를 부르고, 실패하면 모달을 연 채 이유를 보인다", () => {
  const src = read("js/views/components/content-forms.js");
  for (const path of ['"/vocabularies"', "`/vocabularies/${vocabulary.id}`", "`/words/${word.word_id}`"]) assert.ok(src.includes(path), path);
  for (const method of ['"POST"', '"PATCH"', '"PUT"', '"DELETE"']) assert.ok(src.includes(method), method);
  assert.match(src, /preConfirm/);
  assert.match(src, /showValidationMessage\(/);
  assert.match(src, /showLoaderOnConfirm:\s*true/);
  assert.match(src, /confirmDialog\(\{[^}]*danger:\s*true/s, "삭제는 확인을 받는다");
  assert.doesNotMatch(src, /innerHTML/);
});

test("탐색 카드의 버튼과 시트의 이름이 같은 진입 이름을 쓴다", () => {
  assert.match(explore, /wordSheetEntry\(vocabulary\)/);
  assert.match(explore, /openWordSheet\([\s\S]{0,120}icon\(entry\.icon[\s\S]{0,40}entry\.label/);
  assert.match(sheet, /"aria-label":\s*`\$\{vocabulary\.title\} \$\{wordSheetEntry\(vocabulary\)\.label\}`/);
});

test("화면 코드에 관리자 개념이 남아 있지 않다 (#41)", () => {
  const files = ["js", "js/core", "js/views", "js/views/components"].flatMap((dir) =>
    readdirSync(new URL(`../${dir}`, import.meta.url)).filter((n) => n.endsWith(".js")).map((n) => `${dir}/${n}`),
  );
  assert.ok(files.length > 30);
  // "테마 관리자", "비밀번호 관리자"는 다른 뜻이라 권한을 가리키는 말만 찾는다
  assert.deepEqual(files.filter((f) => /admin|관리자(만|에게|는| 계정| 단어| 등록| 화면)/i.test(read(f))), []);
});
