/*
 * 2026-11-05 - voda-voca - 학습 세션 상태 머신: 세션 생명주기, 문항 큐, 퀴즈/플래시카드 답, 연속 정답·숙련, 멱등 재시도, 만료 (DOM 없는 순수 로직)
 * 파일 위치: src/frontend/js/core/session-runner.js
 */

/**
 * reduce(state, action) → { state, effects } 형태의 순수 함수다. 상태를 바꾸지 않고 새 상태를 돌려주며,
 * 서버 호출 같은 부수효과는 effects 로 "설명"만 한다. 실제 호출은 session-driver.js 가 맡는다.
 *
 * 생명주기 (실선은 정상 흐름, ERROR/EXPIRED 는 예외 상태):
 *
 *   IDLE ──START──> LOADING ──SESSION_LOADED──> QUESTION_ACTIVE ──ANSWER_RECEIVED──> FEEDBACK_SHOWING
 *                      │                             ▲  │  │                              │
 *                      │                             │  │  └─ 만료 ─> EXPIRED             │ NEXT
 *                      │                             │  └─ 검증·인증 실패 ─> ERROR         │
 *                      └─ 실패 ─> ERROR              └──────────── NEXT ──────────────────┤
 *                                                                                           └─ 마지막 문항 ─> SESSION_COMPLETE
 *
 * 설계 규칙
 * - 서버가 채점한다. 답을 보내면 응답이 올 때까지 pending 으로 두고, 그동안의 추가 입력(더블 탭)은 무시한다.
 * - 네트워크·서버 오류는 같은 본문으로 RETRY 한다. 서버가 같은 답의 재전송을 멱등으로 처리하므로 안전하다.
 * - 한 번 고른 답은 바꿀 수 없다 (서버도 409 로 잠근다).
 * - 늦게 도착한 세션 생성 응답은 requestId 로 걸러낸다.
 */

export const PHASE = Object.freeze({
  IDLE: "IDLE",
  LOADING: "LOADING",
  QUESTION_ACTIVE: "QUESTION_ACTIVE",
  FEEDBACK_SHOWING: "FEEDBACK_SHOWING",
  SESSION_COMPLETE: "SESSION_COMPLETE",
  EXPIRED: "EXPIRED",
  ERROR: "ERROR",
});

export const ACTION = Object.freeze({
  START: "START",
  SESSION_LOADED: "SESSION_LOADED",
  SESSION_LOAD_FAILED: "SESSION_LOAD_FAILED",
  SUBMIT_ANSWER: "SUBMIT_ANSWER",
  EVALUATE_FLASHCARD: "EVALUATE_FLASHCARD",
  ANSWER_RECEIVED: "ANSWER_RECEIVED",
  ANSWER_FAILED: "ANSWER_FAILED",
  RETRY: "RETRY",
  SKIP_QUESTION: "SKIP_QUESTION",
  NEXT: "NEXT",
  ABORT: "ABORT",
  RESET: "RESET",
});

export const EFFECT = Object.freeze({
  CREATE_SESSION: "CREATE_SESSION",
  SEND_ANSWER: "SEND_ANSWER",
});

/** 허용되는 상태 전이. 테스트가 시나리오에서 관찰한 전이가 이 표 안에 있는지 검사한다. */
export const TRANSITIONS = Object.freeze({
  IDLE: ["LOADING"],
  LOADING: ["QUESTION_ACTIVE", "SESSION_COMPLETE", "ERROR", "IDLE"],
  QUESTION_ACTIVE: ["FEEDBACK_SHOWING", "SESSION_COMPLETE", "EXPIRED", "ERROR", "IDLE"],
  FEEDBACK_SHOWING: ["QUESTION_ACTIVE", "SESSION_COMPLETE", "IDLE"],
  SESSION_COMPLETE: ["LOADING", "IDLE"],
  EXPIRED: ["LOADING", "IDLE"],
  ERROR: ["LOADING", "SESSION_COMPLETE", "IDLE"],
});

/** 연속 정답이 이 횟수에 닿는 순간이 '방금 숙련'이다 (서버의 숙련 규칙과 같다). */
export const MEMORIZE_STREAK = 3;
export const DEFAULT_COUNT = 15;
const CHOICE_COUNT = 4;

/** 서버의 X-Error-Code → 화면이 다루는 오류 종류 */
const CODE_KIND = Object.freeze({
  QUIZ_EXPIRED: "expired",
  QUIZ_ALREADY_SUBMITTED: "already_submitted",
  QUIZ_ANSWER_LOCKED: "locked",
  QUIZ_WORD_MISSING: "word_missing",
  QUIZ_ANSWER_INVALID: "invalid",
  NO_WORDS_TO_STUDY: "no_words",
  NO_VOCABULARY: "no_vocabulary",
});

/**
 * API 오류를 화면이 다루는 종류로 나눈다.
 * 네트워크 단절·시간 초과(status 0), 요청 과다·서버 오류는 다시 시도할 수 있는 종류다.
 * @param {{status?: number, code?: string|null}|null|undefined} error
 * @returns {string}
 */
export function classifyApiError(error) {
  if (!error) return "unknown";
  if (error.status === 0) return "network";
  if (error.code && CODE_KIND[error.code]) return CODE_KIND[error.code];
  if (error.status === 401) return "unauthorized";
  if (error.status === 429 || (typeof error.status === "number" && error.status >= 500)) return "server";
  return "unknown";
}

/** @returns {object} 시작 전 상태 */
export function initialState() {
  return {
    phase: PHASE.IDLE,
    requestId: 0,
    mode: "quiz",
    source: "all", // 출제 풀: all(활성 단어장) | bookmarks | wrong
    sessionId: null,
    vocabularyTitle: "",
    composition: null,
    expiresAt: null,
    items: [],
    index: 0,
    pending: null, // { questionId, body } 답을 보내고 응답을 기다리는 중 (또는 재시도 대기)
    feedback: null, // 방금 받은 채점 결과 + word_id + justMemorized
    error: null, // { kind, message, retryable?, skippable? }
    serverFinished: false,
    answered: 0,
    correct: 0,
    wrong: 0,
    skipped: 0,
    streak: 0, // 이번 세션의 연속 정답
    bestStreak: 0,
    memorizedTerms: [],
    results: [], // 푼 순서대로 { questionId, word_id, term, meaning, isCorrect }
    aborted: false,
  };
}

const unchanged = (state) => ({ state, effects: [] });

/** @param {object} state @returns {object|null} 지금 보여 줄 문항 */
export function currentItem(state) {
  return state.items[state.index] ?? null;
}

/** @param {object} state @returns {{current: number, total: number, ratio: number}} */
export function progressOf(state) {
  const total = state.items.length;
  const current = total ? Math.min(state.index + 1, total) : 0;
  return { current, total, ratio: total ? current / total : 0 };
}

/**
 * 결과 화면용 요약. 중단한 세션은 푼 만큼만 담긴다.
 * @param {object} state
 */
export function summaryOf(state) {
  const total = state.items.length;
  return {
    total,
    answered: state.answered,
    correct: state.correct,
    wrong: state.wrong,
    skipped: state.skipped,
    unanswered: Math.max(0, total - state.answered - state.skipped),
    accuracy: state.answered ? Math.round((state.correct / state.answered) * 1000) / 10 : 0,
    bestStreak: state.bestStreak,
    memorizedTerms: [...state.memorizedTerms],
    wrongItems: state.results
      .filter((result) => !result.isCorrect)
      .map(({ word_id, term, meaning }) => ({ word_id, term, meaning })),
    aborted: state.aborted,
  };
}

/** 다음 문항으로, 마지막이면 완료로 보낸다. */
function advance(state) {
  const base = { ...state, feedback: null, pending: null, error: null };
  if (state.index + 1 >= state.items.length) return { ...base, phase: PHASE.SESSION_COMPLETE };
  return { ...base, phase: PHASE.QUESTION_ACTIVE, index: state.index + 1 };
}

/** 답을 보낼 수 있는 상태인가: 문항이 활성이고, 응답 대기·오류가 없다. */
function canAnswer(state) {
  return state.phase === PHASE.QUESTION_ACTIVE && !state.pending && !state.error && currentItem(state) !== null;
}

function sendAnswer(state, body) {
  const questionId = body.question_id;
  return {
    state: { ...state, pending: { questionId, body } },
    effects: [{ type: EFFECT.SEND_ANSWER, sessionId: state.sessionId, body }],
  };
}

const SOURCES = new Set(["all", "bookmarks", "wrong"]);
const START_FROM = new Set([PHASE.IDLE, PHASE.SESSION_COMPLETE, PHASE.EXPIRED, PHASE.ERROR]);

/**
 * @param {object} state
 * @param {{type: string, [key: string]: any}|null} action
 * @returns {{state: object, effects: Array<object>}}
 */
export function reduce(state, action) {
  if (!action || typeof action.type !== "string") return unchanged(state);

  switch (action.type) {
    case ACTION.START: {
      if (!START_FROM.has(state.phase)) return unchanged(state);
      const mode = action.mode === "flashcard" ? "flashcard" : "quiz";
      const source = SOURCES.has(action.source) ? action.source : SOURCES.has(state.source) ? state.source : "all"; // 다시 시작은 직전 풀을 잇는다
      const requestId = state.requestId + 1;
      return {
        state: { ...initialState(), phase: PHASE.LOADING, requestId, mode, source },
        effects: [
          {
            type: EFFECT.CREATE_SESSION,
            requestId,
            body: { mode, count: action.count ?? DEFAULT_COUNT, include_memorized: action.includeMemorized === true, source },
          },
        ],
      };
    }

    case ACTION.SESSION_LOADED: {
      if (state.phase !== PHASE.LOADING || action.requestId !== state.requestId) return unchanged(state);
      const session = action.session;
      const items = Array.isArray(session?.items) ? session.items : [];
      return {
        state: {
          ...state,
          phase: items.length ? PHASE.QUESTION_ACTIVE : PHASE.SESSION_COMPLETE,
          mode: session.mode === "flashcard" ? "flashcard" : "quiz",
          sessionId: session.session_id,
          vocabularyTitle: session.vocabulary_title ?? "",
          composition: session.composition ?? null,
          expiresAt: session.expires_at ?? null,
          items,
          index: 0,
        },
        effects: [],
      };
    }

    case ACTION.SESSION_LOAD_FAILED: {
      if (state.phase !== PHASE.LOADING || action.requestId !== state.requestId) return unchanged(state);
      return {
        state: {
          ...state,
          phase: PHASE.ERROR,
          error: { kind: classifyApiError(action.error), message: action.error?.detail ?? "세션을 시작하지 못했습니다." },
        },
        effects: [],
      };
    }

    case ACTION.SUBMIT_ANSWER: {
      if (state.mode !== "quiz" || !canAnswer(state)) return unchanged(state);
      const item = currentItem(state);
      const choice = action.choiceIndex;
      const optionCount = Math.min(CHOICE_COUNT, item.options?.length ?? CHOICE_COUNT);
      if (!Number.isInteger(choice) || choice < 0 || choice >= optionCount) return unchanged(state);
      return sendAnswer(state, { question_id: item.question_id, choice_index: choice });
    }

    case ACTION.EVALUATE_FLASHCARD: {
      if (state.mode !== "flashcard" || !canAnswer(state) || typeof action.known !== "boolean") return unchanged(state);
      return sendAnswer(state, { question_id: currentItem(state).question_id, known: action.known });
    }

    case ACTION.ANSWER_RECEIVED: {
      const { pending } = state;
      const result = action.result;
      if (state.phase !== PHASE.QUESTION_ACTIVE || !pending || result?.question_id !== pending.questionId) {
        return unchanged(state);
      }
      const item = currentItem(state);
      const isCorrect = result.is_correct === true;
      const streak = isCorrect ? state.streak + 1 : 0;
      const justMemorized =
        isCorrect && result.progress?.is_memorized === true && result.progress.consecutive_correct_count === MEMORIZE_STREAK;
      return {
        state: {
          ...state,
          phase: PHASE.FEEDBACK_SHOWING,
          pending: null,
          error: null,
          feedback: { ...result, word_id: item.word_id, justMemorized },
          serverFinished: result.is_finished === true,
          expiresAt: result.expires_at ?? state.expiresAt,
          answered: state.answered + 1,
          correct: state.correct + (isCorrect ? 1 : 0),
          wrong: state.wrong + (isCorrect ? 0 : 1),
          streak,
          bestStreak: Math.max(state.bestStreak, streak),
          memorizedTerms: justMemorized ? [...state.memorizedTerms, result.term] : state.memorizedTerms,
          results: [
            ...state.results,
            { questionId: result.question_id, word_id: item.word_id, term: result.term, meaning: result.meaning, isCorrect },
          ],
        },
        effects: [],
      };
    }

    case ACTION.ANSWER_FAILED: {
      if (state.phase !== PHASE.QUESTION_ACTIVE || !state.pending) return unchanged(state);
      const kind = classifyApiError(action.error);
      const message = action.error?.detail ?? "답을 기록하지 못했습니다.";
      switch (kind) {
        case "network":
        case "server":
          return { state: { ...state, error: { kind, message, retryable: true } }, effects: [] };
        case "expired":
          return { state: { ...state, phase: PHASE.EXPIRED, pending: null, error: { kind, message } }, effects: [] };
        case "already_submitted":
          return { state: { ...state, phase: PHASE.SESSION_COMPLETE, pending: null, error: null }, effects: [] };
        case "locked":
        case "word_missing":
          return { state: { ...state, pending: null, error: { kind, message, skippable: true } }, effects: [] };
        default:
          return { state: { ...state, phase: PHASE.ERROR, pending: null, error: { kind, message } }, effects: [] };
      }
    }

    case ACTION.RETRY: {
      if (state.phase !== PHASE.QUESTION_ACTIVE || !state.pending || !state.error?.retryable) return unchanged(state);
      return {
        state: { ...state, error: null },
        effects: [{ type: EFFECT.SEND_ANSWER, sessionId: state.sessionId, body: state.pending.body }],
      };
    }

    case ACTION.SKIP_QUESTION: {
      if (state.phase !== PHASE.QUESTION_ACTIVE || !state.error?.skippable) return unchanged(state);
      return { state: advance({ ...state, skipped: state.skipped + 1, streak: 0 }), effects: [] };
    }

    case ACTION.NEXT: {
      if (state.phase !== PHASE.FEEDBACK_SHOWING) return unchanged(state);
      if (state.serverFinished) return { state: { ...advance(state), phase: PHASE.SESSION_COMPLETE }, effects: [] };
      return { state: advance(state), effects: [] };
    }

    case ACTION.ABORT: {
      switch (state.phase) {
        case PHASE.LOADING:
          return { state: { ...initialState(), requestId: state.requestId + 1 }, effects: [] };
        case PHASE.QUESTION_ACTIVE:
        case PHASE.FEEDBACK_SHOWING:
          return { state: { ...state, phase: PHASE.SESSION_COMPLETE, pending: null, error: null, aborted: true }, effects: [] };
        case PHASE.ERROR:
          return state.items.length
            ? { state: { ...state, phase: PHASE.SESSION_COMPLETE, pending: null, error: null, aborted: true }, effects: [] }
            : { state: { ...initialState(), requestId: state.requestId + 1 }, effects: [] };
        default:
          return unchanged(state);
      }
    }

    case ACTION.RESET:
      return { state: { ...initialState(), requestId: state.requestId + 1 }, effects: [] };

    default:
      return unchanged(state);
  }
}
