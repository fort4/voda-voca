/*
 * 2026-11-02 - voda-voca - 공통 API 클라이언트: 세션 쿠키 전송, 오류 본문 정규화, 401/429 처리, 시간 초과 (REQ-001, REQ-121)
 * 파일 위치: src/frontend/js/core/api.js
 */

/** @typedef {{field: string|null, message: string}} FieldError */

export const API_BASE = "/api";
export const DEFAULT_TIMEOUT_MS = 15000;

/** 401 을 받았을 때 호출되는 콜백. app.js 가 등록한다 (세션 만료 처리). */
let unauthorizedHandler = () => {};

/** @param {() => void} handler */
export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = handler;
}

export class ApiError extends Error {
  /**
   * @param {{status: number, detail: string, fields?: FieldError[], retryAfter?: number|null, body?: unknown}} info
   */
  constructor({ status, detail, fields = [], retryAfter = null, body = null }) {
    super(detail);
    this.name = "ApiError";
    /** HTTP 상태 코드. 네트워크 오류·시간 초과는 0 */
    this.status = status;
    this.detail = detail;
    /** 입력 검증 오류(422)의 필드별 메시지 */
    this.fields = fields;
    /** 429 에서 Retry-After 헤더를 정수 초로 바꾼 값 */
    this.retryAfter = retryAfter;
    this.body = body;
  }
}

/**
 * 쿼리 객체를 쿼리 문자열로 바꾼다. undefined, null 값은 제외하고 boolean 은 true/false 문자열로 쓴다.
 * @param {Record<string, unknown>} [query]
 * @returns {string} 앞에 ? 가 붙거나 빈 문자열
 */
export function buildQuery(query = {}) {
  const parts = [];
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null) continue;
    parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`);
  }
  return parts.length ? `?${parts.join("&")}` : "";
}

/**
 * Retry-After 헤더 값을 정수 초로 바꾼다. 숫자가 아니면 null.
 * @param {string|null} value
 * @returns {number|null}
 */
export function parseRetryAfter(value) {
  if (value === null || value === undefined) return null;
  const trimmed = String(value).trim();
  if (!/^\d+$/.test(trimmed)) return null;
  return Math.max(1, Number.parseInt(trimmed, 10));
}

/**
 * FastAPI 422 의 detail 배열을 필드 오류 목록으로 바꾼다.
 * loc 는 ["body", "email"] 같은 형태이며, 마지막 문자열 요소를 필드 이름으로 쓴다.
 * 모델 수준 오류(loc 가 ["body"])는 field 가 null 이다.
 * @param {unknown} detail
 * @returns {FieldError[]}
 */
export function parseFieldErrors(detail) {
  if (!Array.isArray(detail)) return [];
  return detail.map((item) => {
    const loc = Array.isArray(item?.loc) ? item.loc : [];
    const named = loc.filter((part) => typeof part === "string" && part !== "body");
    const field = named.length ? named[named.length - 1] : null;
    return { field, message: cleanMessage(item?.msg) };
  });
}

/**
 * Pydantic 이 붙이는 "Value error, " 접두사를 걷어내고 공백을 정리한다.
 * @param {unknown} msg
 * @returns {string}
 */
export function cleanMessage(msg) {
  const text = typeof msg === "string" ? msg : "";
  return text.replace(/^Value error,\s*/, "").trim() || "입력값을 확인해 주세요.";
}

/**
 * 실패 응답을 ApiError 로 바꾼다. 순수 함수이므로 테스트에서 직접 호출한다.
 * @param {number} status
 * @param {{get(name: string): string|null}} headers
 * @param {unknown} body JSON 으로 파싱한 본문 (없으면 null)
 * @returns {ApiError}
 */
export function toApiError(status, headers, body) {
  const retryAfter = status === 429 ? parseRetryAfter(headers.get("Retry-After")) : null;
  if (status === 422) {
    const fields = parseFieldErrors(body?.detail);
    const detail = fields[0]?.message ?? "입력값을 확인해 주세요.";
    return new ApiError({ status, detail, fields, body });
  }
  const detail =
    typeof body?.detail === "string" && body.detail
      ? body.detail
      : defaultMessage(status);
  // 일괄 등록 409 의 conflict_term 등 추가 필드는 body 로 그대로 넘긴다.
  return new ApiError({ status, detail, retryAfter, body });
}

/** @param {number} status @returns {string} */
export function defaultMessage(status) {
  if (status === 0) return "인터넷 연결을 확인해 주세요.";
  if (status >= 500) return "서버에 문제가 있습니다. 잠시 후 다시 시도해 주세요.";
  if (status === 404) return "찾을 수 없습니다.";
  if (status === 429) return "요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.";
  return "요청을 처리하지 못했습니다.";
}

/**
 * 공통 API 호출. 성공하면 본문(JSON)만, 헤더가 필요하면 apiResponse 를 쓴다.
 * @param {string} path
 * @param {ApiOptions} [options]
 * @returns {Promise<any>}
 */
export async function api(path, options = {}) {
  const { data } = await apiResponse(path, options);
  return data;
}

/**
 * @typedef {{method?: string, query?: Record<string, unknown>, body?: unknown, signal?: AbortSignal, timeoutMs?: number, skipAuthRedirect?: boolean, fetchImpl?: typeof fetch}} ApiOptions
 */

/**
 * 공통 API 호출 (헤더 포함). 서버 Date 헤더로 시계 차이를 구할 때 쓴다 (세션 타이머).
 * - credentials: 'include' 로 쿠키를 보낸다.
 * - 204 는 data 가 null 이다.
 * - 401 은 unauthorizedHandler 를 호출한 뒤 ApiError 를 던진다 (skipAuthRedirect 가 없을 때만).
 * - 호출자가 signal 로 취소하면 AbortError 를 그대로 던진다. 시간 초과는 ApiError(status 0) 이다.
 *
 * @param {string} path /api 뒤의 경로 (예: "/wordbooks")
 * @param {ApiOptions} [options]
 * @returns {Promise<{data: any, headers: Headers, status: number}>}
 */
export async function apiResponse(path, options = {}) {
  const {
    method = "GET",
    query,
    body,
    signal,
    timeoutMs = DEFAULT_TIMEOUT_MS,
    skipAuthRedirect = false,
    fetchImpl = globalThis.fetch,
  } = options;

  const url = `${API_BASE}${path}${buildQuery(query)}`;
  const headers = { Accept: "application/json" };
  const init = { method, headers, credentials: "include" };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }

  const timeout = new AbortController();
  const timer = setTimeout(() => timeout.abort(new Error("timeout")), timeoutMs);
  init.signal = mergeSignals(signal, timeout.signal);

  let response;
  try {
    response = await fetchImpl(url, init);
  } catch (error) {
    if (signal?.aborted) throw error; // 호출자가 취소한 경우는 그대로 전달
    if (timeout.signal.aborted) {
      throw new ApiError({ status: 0, detail: "응답 시간이 초과되었습니다. 다시 시도해 주세요." });
    }
    throw new ApiError({ status: 0, detail: defaultMessage(0) });
  } finally {
    clearTimeout(timer);
  }

  if (response.status === 204) return { data: null, headers: response.headers, status: 204 };

  const isJson = (response.headers.get("Content-Type") || "").includes("application/json");
  const payload = isJson ? await safeJson(response) : null;

  if (response.ok) return { data: payload, headers: response.headers, status: response.status };

  const error = toApiError(response.status, response.headers, payload);
  if (response.status === 401 && !skipAuthRedirect) unauthorizedHandler();
  throw error;
}

/** @param {Response} response */
async function safeJson(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

/**
 * 호출자 취소와 시간 초과 신호를 하나로 합친다. AbortSignal.any 가 없으면 직접 연결한다.
 * @param {AbortSignal|undefined} a
 * @param {AbortSignal} b
 * @returns {AbortSignal}
 */
export function mergeSignals(a, b) {
  if (!a) return b;
  if (typeof AbortSignal.any === "function") return AbortSignal.any([a, b]);
  const controller = new AbortController();
  const forward = (source) => () => controller.abort(source.reason);
  if (a.aborted) controller.abort(a.reason);
  if (b.aborted) controller.abort(b.reason);
  a.addEventListener("abort", forward(a), { once: true });
  b.addEventListener("abort", forward(b), { once: true });
  return controller.signal;
}
