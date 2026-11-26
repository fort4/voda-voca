/*
 * 2026-11-26 - voda-voca - 메인 소개(Landing) 화면: 비로그인 기본 진입 페이지(#/). 한눈에 읽히는 심플한 히어로, 핵심 기능 3가지, 제공 단어장 요약
 * 파일 위치: src/frontend/js/views/landing-view.js
 */

import { brandLogo, button, h, icon } from "../core/dom.js";
import { cardHeading, iconBadge } from "./components/card-heading.js";

/** 기본 제공 단어장 태그 (간결한 한 줄 요약용) */
export const LANDING_VOCABULARIES = Object.freeze([
  { category: "초등", title: "초급 필수", words: "200단어" },
  { category: "중고등", title: "중급 핵심", words: "200단어" },
  { category: "수능", title: "고급 심화", words: "200단어" },
  { category: "시험", title: "시험 대비 핵심", words: "200단어" },
  { category: "비즈니스", title: "실무 비즈니스", words: "200단어" },
]);

/** 핵심 기능 3가지 (짧고 직관적인 한 줄 설명) */
export const LANDING_FEATURES = Object.freeze([
  {
    iconName: "zap",
    tone: "tone-accent",
    title: "퀴즈 & 플래시카드 집중 학습",
    description: "4지선다·OX 퀴즈와 3D 플래시카드, 영어 발음 듣기(TTS)로 빠르게 외웁니다.",
  },
  {
    iconName: "calendar-clock",
    tone: "tone-activity",
    title: "간격 반복(SRS) & 오답 복습함",
    description: "잊어버릴 때쯤 오늘 복습할 단어를 알려 주고, 틀린 단어만 모아 복습합니다.",
  },
  {
    iconName: "folder-plus",
    tone: "tone-words",
    title: "나만의 단어장 & 학습 통계",
    description: "직접 단어를 추가하거나 CSV로 등록하고, 정답률 추이와 순위를 확인합니다.",
  },
]);

/**
 * 비로그인 사용자에게 보여 주는 심플한 메인 소개 화면.
 * @param {HTMLElement} root
 * @param {{navigate: (path: string) => void}} ctx
 */
export function landingView(root, ctx) {
  root.append(
    h(
      "div",
      { class: "stack pb-4" },
      renderHero(ctx),
      renderFeatures(),
      renderVocabularies(),
    ),
  );
}

function renderHero(ctx) {
  return h(
    "section",
    { class: "card tone-accent rise-in space-y-5 py-7 text-center" },
    h(
      "div",
      { class: "space-y-2.5" },
      brandLogo("lg"),
      h("h1", { class: "text-title tracking-tight text-zinc-900" }, "보다 쉽고 빠르게 외우는 보다보카"),
      h(
        "p",
        { class: "mx-auto max-w-sm text-sm text-zinc-600" },
        "표준 1,000단어부터 나만의 단어장까지, 한 화면에 한 문제씩 집중해서 학습하세요.",
      ),
    ),
    h(
      "div",
      { class: "mx-auto flex max-w-xs flex-col gap-2 sm:max-w-md sm:flex-row" },
      button({ variant: "primary", size: "lg", full: true, onClick: () => ctx.navigate("/signup") }, "무료로 시작하기"),
      button({ variant: "secondary", size: "lg", full: true, onClick: () => ctx.navigate("/login") }, "로그인"),
    ),
  );
}

function renderFeatures() {
  return h(
    "section",
    { class: "card tone-accent rise-in space-y-3.5" },
    cardHeading({ iconName: "sparkles", title: "주요 기능" }),
    h(
      "div",
      { class: "space-y-3" },
      LANDING_FEATURES.map((feat) =>
        h(
          "div",
          { class: `flex items-start gap-3 ${feat.tone}` },
          iconBadge(feat.iconName),
          h(
            "div",
            { class: "min-w-0 flex-1" },
            h("h3", { class: "text-sm font-bold text-zinc-900" }, feat.title),
            h("p", { class: "text-xs text-zinc-600" }, feat.description),
          ),
        ),
      ),
    ),
  );
}

function renderVocabularies() {
  return h(
    "section",
    { class: "card tone-words rise-in space-y-3" },
    cardHeading({
      iconName: "book-open",
      title: "제공 단어장",
      aside: h("span", { class: "text-xs font-semibold text-zinc-500" }, "기본 1,000단어 + 개인 단어장"),
    }),
    h(
      "div",
      { class: "flex flex-wrap gap-2" },
      ...LANDING_VOCABULARIES.map((v) =>
        h(
          "span",
          { class: "word-item inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-zinc-800" },
          v.title,
          h("span", { class: "text-zinc-500" }, v.words),
        ),
      ),
      h(
        "span",
        { class: "inline-flex items-center gap-1 rounded-xl bg-indigo-50 px-3 py-1.5 text-xs font-semibold text-indigo-600" },
        icon("plus", "h-3.5 w-3.5"),
        "나만의 단어장 (CSV 등록)",
      ),
    ),
  );
}
