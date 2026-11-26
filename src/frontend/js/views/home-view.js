/*
 * 2026-11-05 - voda-voca - 홈 화면: 활성 단어장과 일차 진도, 오늘 목표·남은 문항, 학습 시작(퀴즈/플래시카드) (목표·시작 문구는 학습 설정을 따름, REQ-147)
 * 파일 위치: src/frontend/js/views/home-view.js
 */

import { api } from "../core/api.js";
import { button, clear, h, icon, refreshIcons } from "../core/dom.js";
import { homeModel, loadMode, loadQuizOptions, saveMode, saveQuizOptions } from "../core/home-model.js";
import { startLabel } from "../core/settings-model.js";
import { settingsStore } from "../core/settings-store.js";
import { getUser } from "../core/state.js";
import { progressBar } from "./components/progress-bar.js";
import { mountLoader } from "./components/loader.js";
import { renderModeToggle } from "./components/mode-toggle.js";
import { renderQuizOptions } from "./components/quiz-options.js";
import { openSession } from "./components/study-nav.js";

/** 통계·설정은 없어도 홈이 동작해야 하므로 실패하면 null 로 둔다 (설정은 기본값 10 으로 폴백). */
async function loadHome() {
  const [catalog, stats] = await Promise.all([
    api("/vocabularies"),
    api("/study/stats").catch(() => null),
    settingsStore.load(getUser()?.id ?? 0).catch(() => null),
  ]);
  return { active: catalog.find((v) => v.user_progress.is_active) ?? null, stats };
}

/**
 * @param {HTMLElement} root
 * @param {{navigate: (path: string, query?: Record<string, string>) => void}} ctx
 * @returns {() => void}
 */
export function homeView(root, ctx) {
  const storage = globalThis.localStorage;
  let mode = loadMode(storage);
  let quizOptions = loadQuizOptions(storage);
  let unsubscribe = () => {};
  const stop = mountLoader(root, loadHome, (data) => {
    /** 설정이나 모드가 바뀌면 다시 그린다 (헤더의 설정 모달에서 바뀐 값도 여기로 온다). */
    function repaint() {
      clear(root);
      root.append(renderHome({ ...data, settings: settingsStore.get() }, ctx, { mode, setMode, quizOptions: () => quizOptions, setQuizOptions }));
      refreshIcons();
    }

    function setQuizOptions(next) {
      quizOptions = next;
      saveQuizOptions(storage, next); // 화면은 다시 그리지 않는다 (세그먼트가 스스로 갱신한다)
    }

    function setMode(next) {
      mode = next;
      saveMode(storage, next);
      repaint();
    }

    unsubscribe();
    unsubscribe = settingsStore.subscribe(repaint);
    repaint();
  });
  return () => {
    stop();
    unsubscribe();
  };
}

function renderHome(data, ctx, { mode, setMode, quizOptions, setQuizOptions }) {
  const m = homeModel(data);
  return h(
    "div",
    { class: "stack pb-4" },
    h(
      "section",
      { class: "card rise-in space-y-3" },
      h(
        "div",
        { class: "flex items-center justify-between gap-2" },
        h("p", { class: "text-sm font-medium text-zinc-500" }, "학습 중인 단어장"),
        m.studyDay ? h("span", { class: "shrink-0 rounded-full bg-indigo-50 px-2.5 py-1 text-sm font-semibold text-indigo-600" }, m.studyDay.label) : null,
      ),
      m.hasActive
        ? [
            h("h1", { class: "text-heading tracking-tight text-zinc-900" }, m.vocabularyTitle),
            progressBar(m.progressPercent, "단어장 진행률"),
            h("p", { class: "text-sm text-zinc-600" }, `${m.progressText} · ${m.memorizedText}`),
            m.studyDay ? h("p", { class: "text-sm text-zinc-600" }, m.studyDay.detail) : null,
          ]
        : [h("h1", { class: "text-heading tracking-tight text-zinc-900" }, "단어장을 골라 주세요"), h("p", { class: "text-sm text-zinc-600" }, m.emptyHint)],
      button({ variant: "ghost", onClick: () => ctx.navigate("/explore") }, icon("search", "h-4 w-4"), m.hasActive ? "단어장 바꾸기" : "단어장 고르기"),
    ),
    goalCard(m),
    h(
      "section",
      { class: "space-y-3" },
      renderModeToggle({ value: mode, onChange: setMode }),
      // 방향·형식은 퀴즈에만 적용한다 (플래시카드에서는 숨긴다)
      mode === "quiz" ? renderQuizOptions({ value: quizOptions(), onChange: setQuizOptions }) : null,
      button({ variant: "primary", full: true, disabled: !m.canStart, size: "lg", onClick: () => openSession(ctx.navigate, mode, "all", quizOptions()) }, icon("play", "h-5 w-5"), startLabel(settingsStore.get(), mode)),
    ),
  );
}

function goalCard(m) {
  const body =
    m.todayCount === null
      ? h("p", { class: "text-sm text-zinc-600" }, "오늘 기록을 불러오지 못했어요.")
      : [
          h("p", { class: "text-2xl font-extrabold tracking-tight text-zinc-900" }, m.goalReached ? "오늘 목표를 채웠어요 🎉" : `${m.remaining}문항 남았어요`),
          progressBar(m.goalPercent, "오늘 목표"),
          h("p", { class: "text-sm text-zinc-600" }, `오늘 ${m.todayCount}개 학습 · 목표 ${m.dailyGoal}개`),
        ];
  return h(
    "section",
    { class: "card rise-in space-y-3" },
    h("div", { class: "flex items-center justify-between" }, h("p", { class: "text-sm font-medium text-zinc-500" }, "오늘의 목표"), m.streakText ? h("span", { class: "text-sm font-semibold text-indigo-600" }, `🔥 ${m.streakText}`) : null),
    body,
  );
}
