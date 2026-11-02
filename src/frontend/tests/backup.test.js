/*
 * 2026-11-02 - voda-voca - 단어장 CSV 백업 직렬화 단위 테스트: 셀 이스케이프, 헤더, 줄바꿈, 파일 이름 (DOM·네트워크 없음)
 * 파일 위치: src/frontend/tests/backup.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { backupFileName, buildBackupCsv, csvCell } from "../js/core/backup.js";

test("CSV 셀: 쉼표, 따옴표, 줄바꿈이 있으면 큰따옴표로 감싸고 따옴표는 두 번 쓴다", () => {
  assert.equal(csvCell("apple"), "apple");
  assert.equal(csvCell("사과, 배"), '"사과, 배"');
  assert.equal(csvCell('say "hi"'), '"say ""hi"""');
  assert.equal(csvCell("line1\nline2"), '"line1\nline2"');
});

test("CSV 셀: null 과 undefined 는 빈 칸이다", () => {
  assert.equal(csvCell(null), "");
  assert.equal(csvCell(undefined), "");
});

test("백업 CSV: 헤더 한 줄과 행, CRLF 줄바꿈, 예문 뜻 칸이 빈 값이면 빈 칸", () => {
  const text = buildBackupCsv([
    { wordbook: "초급 필수 영단어 200", term: "apple", meaning: "사과", example: "I eat an apple.", exampleMeaning: "나는 사과를 먹는다." },
    { wordbook: "내 단어장", term: "pear", meaning: "배, 과일", example: null, exampleMeaning: null },
  ]);
  assert.equal(
    text,
    [
      "단어장,표제어,뜻,예문,예문 뜻",
      "초급 필수 영단어 200,apple,사과,I eat an apple.,나는 사과를 먹는다.",
      '내 단어장,pear,"배, 과일",,',
    ].join("\r\n"),
  );
});

test("백업 CSV: 단어가 없으면 헤더만 있다", () => {
  assert.equal(buildBackupCsv([]), "단어장,표제어,뜻,예문,예문 뜻");
});

test("백업 파일 이름은 한국 날짜 기준이다", () => {
  assert.equal(backupFileName(Date.parse("2026-11-01T15:30:00Z")), "보다보카-단어장-20261102.csv");
});
