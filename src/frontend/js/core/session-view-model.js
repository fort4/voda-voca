/*
 * 2026-11-05 - voda-voca - 세션 화면 뷰모델: 선지 상태, 피드백 문구, 키 매핑, 오류 안내, 완료 문구 (DOM 없는 순수 로직)
 * 파일 위치: src/frontend/js/core/session-view-model.js
 */

import { ACTION, PHASE, currentItem } from "./session-runner.js";

/** 화면에서만 쓰는 행동. 상태 머신에는 보내지 않고 session 뷰가 직접 처리한다. */
export const VIEW_ACTION = Object.freeze({
  FLIP: "FLIP",
  REQUEST_ABORT: "REQUEST_ABORT",
  GO_HOME: "GO_HOME",
  GO_EXPLORE: "GO_EXPLORE",
});

/**
 * 선지 버튼별 시각 상태.
 * idle(아직), selected(고르고 서버 응답을 기다리는 중), correct(정답), wrong(내가 고른 오답), dim(해설 중 나머지)
 * @param {object} state
 * @returns {Array<"idle"|"selected"|"correct"|"wrong"|"dim">}
 */
export function choiceStates(state) {
  const item = currentItem(state);
  if (!item || state.mode !== "quiz" || !Array.isArray(item.options)) return [];
  const { feedback, pending } = state;

  if (state.phase === PHASE.FEEDBACK_SHOWING && feedback) {
    return item.options.map((_, index) => {
      if (index === feedback.correct_index) return "correct";
      if (!feedback.is_correct && index === feedback.selected_index) return "wrong";
      return "dim";
    });
  }
  const chosen = pending?.body?.choice_index;
  return item.options.map((_, index) => (index === chosen ? "selected" : "idle"));
}

/** @param {object} state @returns {boolean} 지금 보는 문항이 마지막인가 */
function isLast(state) {
  return state.serverFinished || state.index + 1 >= state.items.length;
}

/**
 * 해설 시트의 톤, 제목, 버튼, 배지.
 * @param {object} state
 * @returns {{tone: "correct"|"wrong", title: string, buttonLabel: string, badge: string|null, streakText: string|null}|null}
 */
export function feedbackTone(state) {
  if (state.phase !== PHASE.FEEDBACK_SHOWING || !state.feedback) return null;
  const { feedback } = state;
  const correct = feedback.is_correct === true;
  const flashcard = state.mode === "flashcard";
  const title = flashcard
    ? correct ? "👍 알고 있어요" : "🤔 한 번 더 볼게요"
    : correct ? "🎉 정답입니다!" : "😅 아쉬워요!";
  return {
    tone: correct ? "correct" : "wrong",
    title,
    buttonLabel: isLast(state) ? "결과 보기" : correct ? "다음 문항" : "확인",
    badge: feedback.justMemorized ? "숙련 단어가 됐어요" : null,
    streakText: correct && state.streak >= 2 ? `${state.streak}문제 연속 정답!` : null,
  };
}

/**
 * 키 입력을 행동으로 바꾼다. 상태 머신 액션이거나 VIEW_ACTION 이며, 해당 없으면 null.
 * 입력 칸·모달 가드는 호출하는 쪽(shortcutsBlocked)이 맡는다.
 * @param {string} key
 * @param {object} state
 * @param {{flipped?: boolean}} [view]
 * @returns {object|null}
 */
export function sessionKeyAction(key, state, { flipped = false } = {}) {
  if (key === "Escape") {
    return state.phase === PHASE.QUESTION_ACTIVE || state.phase === PHASE.FEEDBACK_SHOWING
      ? { type: VIEW_ACTION.REQUEST_ABORT }
      : null;
  }
  if (state.phase === PHASE.FEEDBACK_SHOWING) {
    return key === "Enter" || key === " " ? { type: ACTION.NEXT } : null;
  }
  if (state.phase !== PHASE.QUESTION_ACTIVE || state.pending || state.error) return null;

  if (state.mode === "quiz") {
    return /^[1-4]$/.test(key) ? { type: ACTION.SUBMIT_ANSWER, choiceIndex: Number(key) - 1 } : null;
  }
  if (!flipped) return key === " " || key === "Enter" ? { type: VIEW_ACTION.FLIP } : null;
  if (key === "ArrowRight") return { type: ACTION.EVALUATE_FLASHCARD, known: true };
  if (key === "ArrowLeft") return { type: ACTION.EVALUATE_FLASHCARD, known: false };
  return null;
}

const HOME = { label: "홈으로", action: { type: VIEW_ACTION.GO_HOME } };
const RESTART = { label: "다시 시작", action: { type: ACTION.START } };

const ERROR_COPY = Object.freeze({
  network: {
    iconName: "wifi-off",
    title: "연결이 불안정해요",
    text: "이 문항의 답은 아직 기록되지 않았어요. 연결을 확인하고 다시 시도해 주세요.",
    actions: [{ label: "다시 시도", action: { type: ACTION.RETRY } }],
  },
  server: {
    iconName: "server-off",
    title: "서버가 바빠요",
    text: "잠시 후 다시 시도해 주세요. 같은 답을 다시 보내도 중복 기록되지 않아요.",
    actions: [{ label: "다시 시도", action: { type: ACTION.RETRY } }],
  },
  expired: {
    iconName: "timer-off",
    title: "세션이 만료되었어요",
    text: "마지막 답 이후 30분이 지났어요. 푼 문항은 이미 저장되어 있어요.",
    actions: [{ label: "새로 시작", action: { type: ACTION.START } }, HOME],
  },
  no_words: {
    iconName: "party-popper",
    title: "학습할 단어가 없어요",
    text: "이 단어장의 단어를 모두 익혔어요. 숙련한 단어를 포함해서 복습해 볼까요?",
    actions: [
      { label: "숙련 단어 포함해서 시작", action: { type: ACTION.START, includeMemorized: true } },
      { label: "다른 단어장 고르기", action: { type: VIEW_ACTION.GO_EXPLORE } },
    ],
  },
  no_vocabulary: {
    iconName: "book-x",
    title: "학습할 단어장이 없어요",
    text: "단어장 탐색에서 학습할 단어장을 골라 주세요.",
    actions: [{ label: "단어장 고르기", action: { type: VIEW_ACTION.GO_EXPLORE } }, HOME],
  },
  locked: {
    iconName: "lock",
    title: "이 문항은 건너뛸게요",
    text: "이미 다른 답이 기록된 문항이에요.",
    actions: [{ label: "다음 문항", action: { type: ACTION.SKIP_QUESTION } }],
  },
  word_missing: {
    iconName: "file-x",
    title: "이 문항은 건너뛸게요",
    text: "단어장이 갱신되어 이 단어를 더 이상 쓸 수 없어요.",
    actions: [{ label: "다음 문항", action: { type: ACTION.SKIP_QUESTION } }],
  },
  invalid: {
    iconName: "triangle-alert",
    title: "문제가 생겼어요",
    text: "답을 처리하지 못했어요. 새로 시작해 주세요.",
    actions: [RESTART, HOME],
  },
  unauthorized: {
    iconName: "log-in",
    title: "다시 로그인해 주세요",
    text: "로그인이 만료되었어요.",
    actions: [HOME],
  },
  unknown: {
    iconName: "triangle-alert",
    title: "문제가 생겼어요",
    text: "잠시 후 다시 시도해 주세요.",
    actions: [RESTART, HOME],
  },
});

/**
 * 오류 종류별 안내 문구와 행동 버튼.
 * @param {string} kind
 */
export function errorCopy(kind) {
  return ERROR_COPY[kind] ?? ERROR_COPY.unknown;
}

/**
 * 완료 화면 문구와 요약 줄.
 * @param {ReturnType<import("./session-runner.js").summaryOf>} summary
 */
export function completeCopy(summary) {
  const stats = [
    { label: "정답률", value: `${summary.accuracy}%` },
    { label: "맞힌 문제", value: `${summary.correct}/${summary.answered}` },
    { label: "최고 연속", value: `${summary.bestStreak}개` },
  ];
  if (summary.memorizedTerms.length) stats.push({ label: "새로 숙련", value: `${summary.memorizedTerms.length}개` });

  let title;
  let subtitle;
  if (summary.answered === 0) {
    title = "푼 문항이 없어요";
    subtitle = "다음에 다시 도전해 봐요.";
  } else if (summary.aborted) {
    title = "학습을 마쳤어요";
    subtitle = `${summary.answered}문항을 풀었어요. 푼 만큼은 기록되었어요.`;
  } else {
    title = summary.accuracy === 100 ? "완벽해요!" : summary.accuracy >= 60 ? "잘했어요!" : "다음엔 더 잘할 수 있어요";
    subtitle = `${summary.total}문항 중 ${summary.correct}문항을 맞혔어요.`;
  }
  return { title, subtitle, stats, showWrongList: summary.wrongItems.length > 0 };
}
