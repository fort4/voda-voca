/*
 * 2026-11-02 - voda-voca - 단어장 카드 더보기(미트볼) 메뉴 항목 단위 테스트: 항목 순서, 아이콘과 글자, 삭제만 위험 표시
 * 파일 위치: src/frontend/tests/wordbook-menu.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { wordbookMenuItems } from "../js/views/wordbooks.js";

test("더보기 메뉴: 수정, CSV 내보내기, 삭제 순서이고 각 항목은 아이콘과 글자를 가진다", () => {
  const items = wordbookMenuItems();
  assert.deepEqual(
    items.map((item) => [item.key, item.label, item.icon]),
    [
      ["edit", "수정", "pencil"],
      ["export", "CSV 내보내기", "download"],
      ["delete", "삭제", "trash-2"],
    ],
  );
});

test("더보기 메뉴: 삭제 항목만 위험 표시를 받는다", () => {
  const items = wordbookMenuItems();
  assert.deepEqual(
    items.map((item) => Boolean(item.danger)),
    [false, false, true],
  );
});
