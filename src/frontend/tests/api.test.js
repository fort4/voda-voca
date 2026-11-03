/*
 * 2026-11-02 - voda-voca - API 클라이언트 단위 테스트: 쿼리·본문, 오류 정규화, 401/429, 시간 초과, 취소 (fetch 주입)
 * 파일 위치: src/frontend/tests/api.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  api,
  ApiError,
  buildQuery,
  cleanMessage,
  parseFieldErrors,
  parseRetryAfter,
  setUnauthorizedHandler,
  toApiError,
} from "../js/core/api.js";

/** @param {number} status @param {unknown} [body] @param {Record<string,string>} [headers] */
function jsonResponse(status, body, headers = {}) {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

test("buildQuery 는 null·undefined 를 건너뛰고 boolean 을 문자열로 쓴다", () => {
  assert.equal(buildQuery({ page: 2, size: 20, q: undefined, bookmarked: true, wordbook_id: null }), "?page=2&size=20&bookmarked=true");
  assert.equal(buildQuery({}), "");
  assert.equal(buildQuery({ q: "a b&c" }), "?q=a%20b%26c");
});

test("parseRetryAfter 는 정수 초만 받고 최소 1 로 맞춘다", () => {
  assert.equal(parseRetryAfter("37"), 37);
  assert.equal(parseRetryAfter("0"), 1);
  assert.equal(parseRetryAfter("abc"), null);
  assert.equal(parseRetryAfter(null), null);
});

test("parseFieldErrors 는 마지막 이름 있는 loc 요소를 필드로 쓴다", () => {
  const out = parseFieldErrors([
    { loc: ["body", "email"], msg: "Value error, 이메일 형식이 올바르지 않습니다." },
    { loc: ["body", "items", 2, "meaning"], msg: "뜻은 비어 있을 수 없습니다." },
    { loc: ["body"], msg: "Value error, 요청 안에 같은 표제어가 있습니다: apple" },
  ]);
  assert.deepEqual(out, [
    { field: "email", message: "이메일 형식이 올바르지 않습니다." },
    { field: "meaning", message: "뜻은 비어 있을 수 없습니다." },
    { field: null, message: "요청 안에 같은 표제어가 있습니다: apple" },
  ]);
  assert.deepEqual(parseFieldErrors("not an array"), []);
});

test("cleanMessage 는 접두사를 걷고 빈 메시지에 기본 문구를 쓴다", () => {
  assert.equal(cleanMessage("Value error, 길이 초과"), "길이 초과");
  assert.equal(cleanMessage(""), "입력값을 확인해 주세요.");
  assert.equal(cleanMessage(undefined), "입력값을 확인해 주세요.");
});

test("toApiError: 422 는 필드 목록과 첫 메시지를 담는다", () => {
  const err = toApiError(422, new Headers(), {
    detail: [{ loc: ["body", "password"], msg: "Value error, 8자 이상" }],
  });
  assert.equal(err.status, 422);
  assert.equal(err.detail, "8자 이상");
  assert.deepEqual(err.fields, [{ field: "password", message: "8자 이상" }]);
});

test("toApiError: 429 는 Retry-After 를 retryAfter 에 담는다", () => {
  const err = toApiError(429, new Headers({ "Retry-After": "42" }), { detail: "잠시 후 다시 시도해 주세요." });
  assert.equal(err.retryAfter, 42);
  assert.equal(err.detail, "잠시 후 다시 시도해 주세요.");
});

test("toApiError: 409 의 conflict_term 은 body 에 그대로 남는다", () => {
  const err = toApiError(409, new Headers(), { detail: "전체 등록을 취소했습니다.", conflict_term: "Apple" });
  assert.equal(err.detail, "전체 등록을 취소했습니다.");
  assert.equal(err.body.conflict_term, "Apple");
});

test("toApiError: 본문이 없으면 상태별 기본 문구를 쓴다", () => {
  assert.equal(toApiError(500, new Headers(), null).detail, "서버에 문제가 있습니다. 잠시 후 다시 시도해 주세요.");
  assert.equal(toApiError(404, new Headers(), null).detail, "찾을 수 없습니다.");
});

test("api: 204 는 null, JSON 성공은 본문을 반환한다", async () => {
  const none = await api("/auth/logout", { method: "POST", fetchImpl: async () => new Response(null, { status: 204 }) });
  assert.equal(none, null);
  const data = await api("/wordbooks", { fetchImpl: async () => jsonResponse(200, { items: [], total: 0 }) });
  assert.deepEqual(data, { items: [], total: 0 });
});

test("api: credentials include, 쿼리와 JSON 본문을 올바르게 보낸다", async () => {
  let seen;
  await api("/wordbooks", {
    method: "POST",
    query: { page: 1 },
    body: { name: "단어장" },
    fetchImpl: async (url, init) => {
      seen = { url, init };
      return jsonResponse(201, { id: 1 });
    },
  });
  assert.equal(seen.url, "/api/wordbooks?page=1");
  assert.equal(seen.init.credentials, "include");
  assert.equal(seen.init.method, "POST");
  assert.equal(seen.init.headers["Content-Type"], "application/json");
  assert.equal(seen.init.body, JSON.stringify({ name: "단어장" }));
});

test("api: 401 은 세션 만료 콜백을 부르고 ApiError 를 던진다", async () => {
  let calls = 0;
  setUnauthorizedHandler(() => (calls += 1));
  await assert.rejects(
    api("/wordbooks", { fetchImpl: async () => jsonResponse(401, { detail: "로그인이 필요합니다." }) }),
    (error) => error instanceof ApiError && error.status === 401 && error.detail === "로그인이 필요합니다.",
  );
  assert.equal(calls, 1);
  setUnauthorizedHandler(() => {});
});

test("api: skipAuthRedirect 면 401 에도 콜백을 부르지 않는다 (로그인 자체의 401)", async () => {
  let calls = 0;
  setUnauthorizedHandler(() => (calls += 1));
  await assert.rejects(
    api("/auth/login", {
      method: "POST",
      skipAuthRedirect: true,
      fetchImpl: async () => jsonResponse(401, { detail: "닉네임 또는 비밀번호가 올바르지 않습니다." }),
    }),
    ApiError,
  );
  assert.equal(calls, 0);
  setUnauthorizedHandler(() => {});
});

test("api: 네트워크 실패는 status 0 과 연결 안내로 바꾼다", async () => {
  await assert.rejects(
    api("/wordbooks", { fetchImpl: async () => { throw new TypeError("fetch failed"); } }),
    (error) => error instanceof ApiError && error.status === 0 && error.detail.includes("인터넷 연결"),
  );
});

test("api: 시간 초과는 status 0 과 시간 초과 안내로 바꾼다", async () => {
  const hangs = (_url, init) =>
    new Promise((_resolve, reject) => {
      init.signal.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
    });
  await assert.rejects(
    api("/wordbooks", { timeoutMs: 10, fetchImpl: hangs }),
    (error) => error instanceof ApiError && error.status === 0 && error.detail.includes("시간이 초과"),
  );
});

test("api: 호출자가 취소하면 AbortError 를 그대로 던진다 (오류 화면으로 바꾸지 않음)", async () => {
  const controller = new AbortController();
  const hangs = (_url, init) =>
    new Promise((_resolve, reject) => {
      init.signal.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
    });
  const pending = api("/wordbooks", { signal: controller.signal, timeoutMs: 5000, fetchImpl: hangs });
  controller.abort();
  await assert.rejects(pending, (error) => error.name === "AbortError");
});

test("toApiError: X-Error-Code 헤더를 code 로 싣는다 (문구가 바뀌어도 화면이 분기할 수 있다)", () => {
  const withCode = toApiError(400, new Headers({ "X-Error-Code": "QUIZ_EXPIRED" }), { detail: "퀴즈 제한 시간(30분)이 지났습니다." });
  assert.equal(withCode.code, "QUIZ_EXPIRED");
  assert.equal(withCode.status, 400);
  const without = toApiError(404, new Headers(), { detail: "없음" });
  assert.equal(without.code, null);
});
