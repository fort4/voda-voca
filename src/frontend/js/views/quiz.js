/*
 * 2026-11-02 - voda-voca - 4지선다 퀴즈 화면: 출제 전 단어 수 가드, 30분 세션 카운트다운(서버 Date 보정), 일괄 채점 제출, 결과 sessionStorage 캐싱·복구 (REQ-014~016, REQ-019)
 * 파일 위치: src/frontend/js/views/quiz.js
 */

import { api, apiResponse, ApiError } from "../core/api.js";
import { button, clear, h, icon, notice, refreshIcons, skeleton } from "../core/dom.js";
import { alertBox } from "../core/form.js";
import { createQuizFlow } from "../core/quiz-flow.js";
import { deriveQuizItems } from "../core/quiz-state.js";
import { loadQuizResult, saveQuizResult } from "../core/result-cache.js";
import { computeClockOffset, formatClock, isWarning, remainingMs } from "../core/timer.js";
import { confirmDialog, toast } from "../core/toast.js";
import {
  canStartQuiz,
  parseStudySource,
  QUIZ_MIN_WORDS,
  sourceCountRequest,
  sourceQuizBody,
  sourceRouteQuery,
} from "../lib/study-source.js";

export const QUIZ_COUNT_CHOICES = [5, 10, 20];

/**
 * @param {HTMLElement} root
 * @param {{query: Record<string, string>, navigate: (path: string, query?: object) => void, replace: (path: string, query?: object) => void}} ctx
 * @returns {() => void}
 */
export function quizView(root, ctx) {
  const { query } = ctx;
  let stopTimerFn = null; // 진행 중인 세션의 타이머 정리 함수
  const body = h("div", { class: "space-y-4" });
  root.append(body);

  if (query.session !== undefined) {
    const id = Number(query.session);
    renderSavedResult(id, ctx);
  } else {
    const source = parseStudySource(query);
    if (!source) {
      body.append(
        notice({
          iconName: "book-open",
          title: "퀴즈를 시작할 단어장을 고르지 않았습니다.",
          action: button({ variant: "secondary", onClick: () => ctx.navigate("/wordbooks") }, "단어장으로"),
        }),
      );
    } else {
      renderSetup(source, ctx);
    }
  }
  return () => stopTimerFn?.();

  /**
   * 출제 전 화면: 원천 단어 수를 먼저 세고, 4개 미만이면 시작 버튼을 막는다 (400 을 기다리지 않는다).
   * @param {{kind: string, wordbookId?: number}} source
   * @param {typeof ctx} c
   */
  async function renderSetup(source, c) {
    clear(body);
    const count = { value: 0, loaded: false };
    let chosen = 10;
    const banner = alertBox();
    const startBtn = button({ full: true, disabled: true, onClick: () => start() }, "퀴즈 시작");
    const countInfo = h("p", { class: "text-sm text-zinc-600" }, "단어 수를 확인하는 중…");
    const radios = QUIZ_COUNT_CHOICES.map((n) =>
      h(
        "label",
        { class: "flex min-h-[44px] flex-1 cursor-pointer items-center justify-center rounded-xl border border-zinc-300 bg-white px-3 font-semibold has-[:checked]:border-indigo-600 has-[:checked]:bg-indigo-50" },
        h("input", { type: "radio", name: "quiz-count", value: String(n), class: "sr-only", checked: n === chosen, onchange: () => { chosen = n; updateInfo(); } }),
        `${n}문항`,
      ),
    );

    function updateInfo() {
      if (!count.loaded) return;
      const possible = Math.min(chosen, count.value);
      countInfo.textContent = canStartQuiz(count.value)
        ? `${possible}문항으로 출제합니다. (원천 단어 ${count.value}개)`
        : `${source.kind === "wordbook" ? "단어장" : "북마크"}에 단어가 ${count.value}개뿐입니다. 퀴즈는 ${QUIZ_MIN_WORDS}개 이상일 때 시작할 수 있습니다.`;
      startBtn.disabled = !canStartQuiz(count.value);
    }

    const title = source.kind === "wordbook" ? "단어장 퀴즈" : "북마크 퀴즈";
    body.append(
      h(
        "section",
        { class: "space-y-5" },
        h(
          "div",
          { class: "flex items-center gap-2" },
          button({ variant: "ghost", onClick: () => c.navigate(source.kind === "wordbook" ? `/wordbooks/${source.wordbookId}` : "/bookmarks") }, icon("arrow-left"), h("span", { class: "sr-only" }, "돌아가기")),
          h("h1", { class: "text-xl font-bold" }, title),
        ),
        h("div", { class: "space-y-2" }, h("p", { class: "text-sm font-medium text-zinc-700" }, "문항 수"), h("div", { class: "flex gap-2" }, radios)),
        countInfo,
        banner.el,
        startBtn,
      ),
    );

    try {
      const info = await api(sourceCountRequest(source).path, { query: sourceCountRequest(source).query });
      count.value = info.total;
      count.loaded = true;
      updateInfo();
    } catch (error) {
      countInfo.textContent = "";
      banner.show(error instanceof ApiError ? error.detail : "단어 수를 확인하지 못했습니다.");
    }

    async function start() {
      banner.hide();
      startBtn.disabled = true;
      try {
        const { data, headers } = await apiResponse("/study/quiz/sessions", {
          method: "POST",
          body: { ...sourceQuizBody(source), count: chosen },
        });
        runSession(data, headers, source, Date.now());
      } catch (error) {
        startBtn.disabled = false;
        banner.show(error instanceof ApiError ? error.detail : "퀴즈를 시작하지 못했습니다.");
      }
    }
  }

  /**
   * 출제된 세션을 푼다. 보기를 고르면 즉시 정오를 판정하고 해설을 보여 준다 (즉각 피드백).
   * 타이머는 서버 expires_at 기준 로컬 카운트다운이다. 마지막 문항 뒤에는 최종 결과 보기로 제출한다.
   * @param {{session_id: number, expires_at: string, questions: Array<{question_id: number, term: string, choices: string[], correct_index: number, example: string|null}>}} session
   * @param {Headers} headers 출제 응답 헤더 (Date 로 시계 차이 보정)
   * @param {{kind: string, wordbookId?: number}} source
   * @param {number} clientNow 응답을 받은 순간의 기기 시각
   */
  function runSession(session, headers, source, clientNow) {
    const offset = computeClockOffset(headers?.get?.("Date") ?? null, clientNow);
    const flow = createQuizFlow({ session });
    const view = { expired: false, submitting: false, timerId: null, ms: remainingMs(session.expires_at, Date.now(), offset) };
    const timerEl = h("span", { class: "font-mono text-base font-semibold tabular-nums", role: "timer" });
    const progressBar = h("div", { class: "h-2 rounded-full bg-indigo-600 transition-all duration-500", style: "width: 0%" });
    const progressText = h("p", { class: "text-sm text-zinc-500", "aria-live": "polite" });
    const banner = alertBox();
    const stage = h("div", { class: "space-y-4" });

    const tick = () => {
      view.ms = remainingMs(session.expires_at, Date.now(), offset);
      paintTimer();
      if (view.ms <= 0 && !view.expired) expire();
    };

    function paintTimer() {
      timerEl.textContent = formatClock(view.ms);
      timerEl.classList.toggle("text-red-600", isWarning(view.ms));
      timerEl.setAttribute("aria-label", `남은 시간 ${formatClock(view.ms)}`);
    }

    function paintProgress() {
      progressBar.style.width = `${flow.progressPercent()}%`;
      progressText.textContent = `${flow.answeredCount()} / ${flow.total} 답함`;
    }

    function expire() {
      view.expired = true;
      stopTimer();
      banner.show("시간이 지났습니다. 퀴즈를 다시 시작해 주세요.");
      render();
    }

    function stopTimer() {
      if (view.timerId !== null) clearInterval(view.timerId);
      view.timerId = null;
    }

    /** 보기 한 개. 판정 후에는 정답은 초록, 내가 고른 틀린 답은 빨강으로 보여 준다. */
    function choiceButton(question, i, feedback, locked) {
      const isSelected = feedback?.selectedIndex === i;
      const isAnswer = feedback !== null && i === feedback.correctIndex;
      const isWrongPick = isSelected && feedback !== null && !feedback.isCorrect;
      const tone = isAnswer
        ? "border-emerald-500 bg-emerald-50 text-emerald-900"
        : isWrongPick
          ? "border-red-500 bg-red-50 text-red-800"
          : "border-zinc-200 bg-white text-zinc-800 hover:border-indigo-300 hover:bg-indigo-50/40";
      const btn = h(
        "button",
        {
          type: "button",
          class: `press focus-ring flex min-h-[52px] w-full items-center gap-3 rounded-xl border px-4 py-3 text-left text-[15px] font-medium shadow-sm transition-colors disabled:cursor-default ${tone}`,
          disabled: locked,
          "aria-pressed": String(isSelected),
          onclick: () => {
            if (flow.choose(i)) render();
          },
        },
        h(
          "span",
          { class: `grid h-7 w-7 shrink-0 place-items-center rounded-lg font-mono text-sm ${isAnswer ? "bg-emerald-600 text-white" : isWrongPick ? "bg-red-600 text-white" : "bg-zinc-100 text-zinc-600"}` },
          `${i + 1}`,
        ),
        h("span", { class: "min-w-0 flex-1 break-words" }, question.choices[i]),
        isAnswer ? icon("check", "h-5 w-5 shrink-0 text-emerald-700") : isWrongPick ? icon("x", "h-5 w-5 shrink-0 text-red-700") : null,
      );
      if (isSelected) btn.classList.add("choice-selected");
      return btn;
    }

    /** 해설 카드: 정오, 정답 뜻, 예문, 다음 문항 또는 최종 결과 보기. */
    function feedbackCard(feedback) {
      const last = flow.isLast();
      return h(
        "section",
        { class: `rise-in space-y-3 rounded-2xl border p-5 ${feedback.isCorrect ? "border-emerald-200 bg-emerald-50/70" : "border-red-200 bg-red-50/70"}`, role: "status", "aria-live": "polite" },
        h(
          "p",
          { class: `flex items-center gap-2 text-base font-bold ${feedback.isCorrect ? "text-emerald-800" : "text-red-800"}` },
          icon(feedback.isCorrect ? "check-circle" : "x", "h-5 w-5"),
          feedback.isCorrect ? "정답입니다!" : "아쉬워요, 오답입니다.",
        ),
        h(
          "div",
          { class: "space-y-1 text-sm text-zinc-700" },
          h("p", {}, "정답 뜻: ", h("strong", { class: "text-zinc-900" }, feedback.correctMeaning)),
        ),
        h(
          "div",
          { class: "rounded-xl bg-white/80 p-4 ring-1 ring-zinc-200" },
          h("p", { class: "mb-1 text-xs font-semibold uppercase tracking-wider text-zinc-500" }, "예문 해설"),
          feedback.example
            ? h("p", { class: "break-words text-[15px] italic leading-relaxed text-zinc-800" }, feedback.example)
            : h("p", { class: "text-sm text-zinc-500" }, "이 단어에는 해설 예문이 없습니다."),
        ),
        button({ full: true, onClick: advance }, last ? "최종 결과 보기" : "다음 문항", icon(last ? "flag" : "chevron-right")),
      );
    }

    function render() {
      clear(stage);
      const question = flow.current();
      const feedback = flow.feedbackFor(question.question_id);
      const locked = view.expired || view.submitting || feedback !== null;
      stage.append(
        h("p", { class: "text-sm font-medium text-zinc-500" }, `${flow.index + 1} / ${flow.total}번 문항`),
        h("p", { class: "surface rise-in break-words p-6 text-center text-3xl font-bold tracking-tight text-zinc-900" }, question.term),
        h(
          "div",
          { class: "grid gap-2.5", role: "group", "aria-label": "뜻 고르기" },
          question.choices.map((_, i) => choiceButton(question, i, feedback, locked)),
        ),
        feedback && !view.expired ? feedbackCard(feedback) : null,
        h(
          "div",
          { class: "grid grid-cols-2 gap-2" },
          button({ variant: "secondary", disabled: flow.index === 0 || view.submitting, onClick: () => { flow.prev(); render(); } }, icon("chevron-left"), "이전"),
          feedback === null && !view.expired
            ? h("p", { class: "flex items-center justify-center text-center text-xs text-zinc-500" }, "보기를 고르면 바로 채점됩니다.")
            : null,
        ),
      );
      paintProgress();
      refreshIcons();
    }

    /** 해설의 다음 버튼. 마지막이면 최종 제출 (기록 저장 후 결과 화면). */
    function advance() {
      if (flow.isLast()) {
        finish();
        return;
      }
      if (flow.next()) render();
    }

    async function finish() {
      if (!flow.canFinish() || view.submitting || view.expired) return;
      view.submitting = true;
      stopTimer();
      render();
      try {
        const result = await api(`/study/quiz/sessions/${session.session_id}/submit`, { method: "POST", body: flow.toSubmitPayload() });
        const answers = flow.answerMap();
        const record = {
          sessionId: session.session_id,
          source: sourceRouteQuery(source),
          total: result.total,
          correct_count: result.correct_count,
          accuracy: result.accuracy,
          items: deriveQuizItems(session.questions, answers, result.wrong_items),
        };
        saveQuizResult(globalThis.sessionStorage, session.session_id, record);
        ctx.replace("/study/quiz", { session: String(session.session_id) });
      } catch (error) {
        view.submitting = false;
        if (error instanceof ApiError && error.status === 400 && /지났습니다/.test(error.detail)) {
          expire();
          return;
        }
        if (error instanceof ApiError && error.status === 409) {
          banner.show(error.detail.includes("삭제") ? "퀴즈에 포함된 단어가 삭제되어 제출할 수 없습니다. 퀴즈를 다시 시작해 주세요." : "이미 제출된 퀴즈입니다.");
        } else {
          banner.show(error instanceof ApiError ? error.detail : "제출하지 못했습니다.");
        }
        if (!view.expired) view.timerId = setInterval(tick, 1000);
        render();
      }
    }

    clear(body);
    body.append(
      h(
        "div",
        { class: "space-y-3" },
        h(
          "div",
          { class: "flex items-center gap-2" },
          button({ variant: "ghost", onClick: async () => { if (await confirmDialog({ title: "퀴즈를 그만둘까요?", text: "지금까지 고른 답은 저장되지 않습니다.", confirmText: "그만두기", danger: true })) ctx.navigate(`/study/quiz`, sourceRouteQuery(source)); } }, icon("x"), h("span", { class: "sr-only" }, "퀴즈 그만두기")),
          h("div", { class: "flex-1" }),
          timerEl,
        ),
        h("div", { class: "h-2 w-full overflow-hidden rounded-full bg-zinc-200", role: "progressbar", "aria-valuemin": "0", "aria-valuemax": "100" }, progressBar),
        progressText,
      ),
      banner.el,
      stage,
    );
    stopTimerFn = stopTimer;
    paintTimer();
    render();
    view.timerId = setInterval(tick, 1000);
  }

  /**
   * 제출이 끝난 퀴즈의 결과를 세션 캐시에서 보여 준다. 캐시가 없으면 이 탭에서는 복구할 수 없다는 안내.
   * @param {number} id
   * @param {typeof ctx} c
   */
  function renderSavedResult(id, c) {
    clear(body);
    const record = Number.isInteger(id) ? loadQuizResult(globalThis.sessionStorage, id) : null;
    if (!record) {
      body.append(
        notice({
          iconName: "history",
          title: "이 탭에서는 결과를 다시 볼 수 없습니다.",
          text: "결과는 제출한 탭에서만 남아 있습니다. 새 퀴즈를 시작해 주세요.",
          action: button({ variant: "secondary", onClick: () => c.navigate("/wordbooks") }, "단어장으로"),
        }),
      );
      return;
    }
    const perfect = record.total > 0 && record.correct_count === record.total;
    const wrong = record.items.filter((item) => !item.is_correct);
    body.append(
      h(
        "section",
        { class: "space-y-5" },
        h("h1", { class: "text-xl font-bold" }, "퀴즈 결과"),
        h(
          "div",
          { class: "p-6 text-center surface" },
          h("p", { class: "text-4xl font-bold" }, `${record.correct_count} / ${record.total}`),
          h("p", { class: "mt-1 text-lg text-zinc-700" }, `정답률 ${record.accuracy}%`),
          perfect ? h("p", { class: "mt-2 text-sm text-indigo-700" }, "모두 맞혔습니다.") : null,
        ),
        h("h2", { class: "text-lg font-semibold" }, `오답 노트 (${wrong.length})`),
        wrong.length
          ? h("ol", { class: "space-y-3" }, wrong.map((item) => wrongNote(item)))
          : h("p", { class: "text-sm text-zinc-600" }, "틀린 문항이 없습니다."),
        h("h2", { class: "text-lg font-semibold" }, "전체 문항"),
        h("ol", { class: "space-y-3" }, record.items.map((item, i) => questionResult(item, i))),
        h(
          "div",
          { class: "grid grid-cols-2 gap-2" },
          button({ variant: "secondary", onClick: () => c.navigate("/study/quiz", record.source) }, "다시 풀기"),
          button({ onClick: () => c.navigate("/history") }, "학습 이력 보기"),
        ),
      ),
    );
    refreshIcons();
  }

  /** @param {any} item */
  function wrongNote(item) {
    const marked = { done: false };
    const bookmarkBtn = button({ variant: "secondary", full: true, disabled: item.word_id == null, onClick: async () => {
      try {
        await api(`/bookmarks/${item.word_id}`, { method: "PUT" });
        marked.done = true;
        bookmarkBtn.disabled = true;
        bookmarkBtn.textContent = "";
        bookmarkBtn.append(icon("star"), "북마크함");
        refreshIcons();
        toast("북마크에 추가했습니다.");
      } catch (error) {
        toast(error.detail ?? "북마크를 저장하지 못했습니다.", "error");
      }
    } }, icon("star"), "북마크에 추가");
    return h(
      "li",
      { class: "space-y-2 rounded-xl bg-white p-4 ring-1 ring-red-200" },
      h("p", { class: "break-words text-lg font-semibold" }, item.term),
      h("p", { class: "text-sm text-red-700" }, `내 답: ${item.choices[item.selected_index]}`),
      h("p", { class: "text-sm text-green-700" }, `정답: ${item.choices[item.correct_index]}`),
      bookmarkBtn,
    );
  }

  /** @param {any} item @param {number} i */
  function questionResult(item, i) {
    return h(
      "li",
      { class: "p-4 surface" },
      h(
        "p",
        { class: "mb-2 flex items-center gap-2 font-semibold" },
        h("span", { class: item.is_correct ? "text-green-700" : "text-red-700" }, item.is_correct ? "정답" : "오답"),
        h("span", { class: "break-words" }, `${i + 1}. ${item.term}`),
      ),
      h(
        "ul",
        { class: "space-y-1 text-sm" },
        item.choices.map((choice, c) => {
          const isCorrect = c === item.correct_index;
          const isMyWrong = c === item.selected_index && !item.is_correct;
          const tag = isCorrect ? "정답" : isMyWrong ? "내 답" : "";
          return h(
            "li",
            { class: `flex items-center gap-2 rounded-lg px-2 py-1 ${isCorrect ? "bg-green-50 text-green-800" : isMyWrong ? "bg-red-50 text-red-800" : "text-zinc-600"}` },
            h("span", { class: "min-w-0 flex-1 break-words" }, choice),
            tag ? h("span", { class: "shrink-0 text-xs font-semibold" }, tag) : null,
          );
        }),
      ),
    );
  }
}
