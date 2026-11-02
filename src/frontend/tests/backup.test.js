/*
 * 2026-11-02 - voda-voca - 단어장 CSV 백업 직렬화 단위 테스트: 셀 이스케이프, 헤더, 줄바꿈, 파일 이름 (DOM·네트워크 없음)
 * 파일 위치: src/frontend/tests/backup.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { backupFileName, buildBackupCsv, buildWordbookCsv, csvCell, safeFileStem, wordbookFileName } from "../js/core/backup.js";
import { buildBulkPayload, parseDelimited, toCandidateRows, validateCandidateRows } from "../js/lib/csv.js";

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

test("개별 단어장 CSV: 헤더는 표제어,뜻,예문,예문 뜻 이고, 빈 값은 빈 칸이다", () => {
  const text = buildWordbookCsv([
    { term: "apple", meaning: "사과", example: "I eat an apple.", exampleMeaning: "나는 사과를 먹는다." },
    { term: "pear", meaning: "배, 과일", example: null, exampleMeaning: null },
  ]);
  assert.equal(
    text,
    ["표제어,뜻,예문,예문 뜻", "apple,사과,I eat an apple.,나는 사과를 먹는다.", 'pear,"배, 과일",,'].join("\r\n"),
  );
});

test("개별 단어장 CSV: 단어가 없으면 헤더만 있다", () => {
  assert.equal(buildWordbookCsv([]), "표제어,뜻,예문,예문 뜻");
});

test("파일 이름: 공백은 밑줄, 경로와 특수문자는 제거한다", () => {
  assert.equal(safeFileStem("초급 필수 영단어 200"), "초급_필수_영단어_200");
  assert.equal(safeFileStem(' a/b:c? 가 '), "abc_가");
  assert.equal(safeFileStem("///"), "단어장");
  assert.equal(wordbookFileName("초급 필수 영단어 200", Date.parse("2026-11-01T15:30:00Z")), "초급_필수_영단어_200_20261102.csv");
});

test("왕복: 개별 단어장 파일을 다시 가져오면 같은 단어와 예문 뜻이 나온다", () => {
  const words = [
    { term: "apple", meaning: "사과", example: "I eat an apple.", exampleMeaning: "나는 사과를 먹는다." },
    { term: "pear", meaning: "배, 과일", example: null, exampleMeaning: null },
    { term: "plum", meaning: "자두", example: "A plum, please.", exampleMeaning: null },
  ];
  const { headerSkipped, rows } = toCandidateRows(parseDelimited(buildWordbookCsv(words)));
  assert.equal(headerSkipped, true);
  const checked = validateCandidateRows(rows);
  assert.ok(checked.every((row) => row.errors.length === 0), JSON.stringify(checked.map((r) => r.errors)));
  const { items } = buildBulkPayload(checked);
  assert.deepEqual(items, [
    { term: "apple", meaning: "사과", example: "I eat an apple.", example_meaning: "나는 사과를 먹는다." },
    { term: "pear", meaning: "배, 과일", example: null },
    { term: "plum", meaning: "자두", example: "A plum, please." },
  ]);
});

test("기존 3열 파일은 네 번째 칸을 여전히 열 초과로 본다", () => {
  const { rows } = toCandidateRows(parseDelimited("apple,사과,예문,잘못된 칸\n"));
  assert.equal(rows[0].extraColumns, true);
  const [checked] = validateCandidateRows(rows);
  assert.match(checked.errors.join(" "), /열이 세 개/);
});

test("예문 뜻이 500자를 넘으면 행 오류가 된다", () => {
  const { rows } = toCandidateRows(parseDelimited(`표제어,뜻,예문,예문 뜻\napple,사과,An apple.,${"가".repeat(501)}\n`));
  const [checked] = validateCandidateRows(rows);
  assert.match(checked.errors.join(" "), /예문 뜻은 500자/);
});
