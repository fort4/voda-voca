/*
 * 2026-11-03 - voda-voca - 퀴즈 결과 화면: 서버의 세션 상세로 요약·오답 노트·전체 문항을 그린다. 일부만 푼 결과와 풀지 않은 문항도 구분한다 (이슈 #8)
 * 파일 위치: src/frontend/js/views/quiz-result.js
 */

import { api, ApiError } from "../core/api.js";
import { button, clear, h, icon, notice, refreshIcons, skeleton } from "../core/dom.js";
import { describeResult, retryGuidance } from "../core/quiz-result.js";
import { toast } from "../core/toast.js";
import { routeQueryFromSession } from "../lib/study-source.js";

/**
 * 퀴즈 결과를 서버에서 받아 보여 준다. 새로고침하거나 다른 탭·기기에서 열어도 같은 결과가 나온다.
 * 일부만 풀고 끝낸 퀴즈는 푼 문항 기준으로 요약하고, 풀지 않은 문항은 "풀지 않음"으로 표시한다.
 * @param {HTMLElement} body 결과를 그릴 영역
 * @param {number} id
 * @param {{navigate: (path: string, query?: object) => void}} c
 */
export async function renderQuizResult(body, id, c) {
  clear(body);
  if (!Number.isInteger(id) || id <= 0) {
    body.append(resultNotice("결과를 찾을 수 없습니다.", "", c));
    return;
  }
  body.append(skeleton(2));
  let data;
  try {
    data = await api(`/study/quiz/sessions/${id}`);
  } catch (error) {
    clear(body);
    body.append(
      error instanceof ApiError && error.status === 404
        ? resultNotice("결과를 찾을 수 없습니다.", "다른 계정의 퀴즈이거나 삭제된 퀴즈입니다.", c)
        : notice({
            iconName: "cloud-off",
            title: "결과를 불러오지 못했습니다.",
            text: error instanceof ApiError ? error.detail : "",
            action: button({ variant: "secondary", onClick: () => renderQuizResult(body, id, c) }, "다시 시도"),
          }),
    );
    refreshIcons();
    return;
  }
  clear(body);
  const view = describeResult(data);
  const guidance = retryGuidance(data);
  const wrong = data.items.filter((item) => item.is_correct === false);
  body.append(
    h(
      "section",
      { class: "space-y-5" },
      h("h1", { class: "text-xl font-bold" }, "퀴즈 결과"),
      h(
        "div",
        { class: "p-6 text-center surface" },
        h("p", { class: "text-4xl font-bold" }, view.score),
        h("p", { class: "mt-1 text-lg text-zinc-700" }, view.accuracyLabel),
        view.perfect ? h("p", { class: "mt-2 text-sm text-indigo-700" }, "모두 맞혔습니다.") : null,
        view.note ? h("p", { class: "mt-2 text-sm text-zinc-600" }, view.note) : null,
        guidance ? h("p", { class: "mt-1 text-xs text-zinc-500" }, guidance) : null,
      ),
      h("h2", { class: "text-lg font-semibold" }, `오답 노트 (${wrong.length})`),
      wrong.length
        ? h("ol", { class: "space-y-3" }, wrong.map((item) => wrongNote(item)))
        : h("p", { class: "text-sm text-zinc-600" }, "틀린 문항이 없습니다."),
      h("h2", { class: "text-lg font-semibold" }, "전체 문항"),
      h("ol", { class: "space-y-3" }, data.items.map((item, i) => questionResult(item, i))),
      h(
        "div",
        { class: "grid grid-cols-2 gap-2" },
        button({ variant: "secondary", onClick: () => c.navigate("/study/quiz", routeQueryFromSession(data)) }, "다시 풀기"),
        button({ onClick: () => c.navigate("/history") }, "학습 이력 보기"),
      ),
    ),
  );
  refreshIcons();
}

/** @param {string} title @param {string} text @param {{navigate: (path: string) => void}} c */
function resultNotice(title, text, c) {
  return notice({
    iconName: "history",
    title,
    text,
    action: button({ variant: "secondary", onClick: () => c.navigate("/wordbooks") }, "단어장으로"),
  });
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
      item.is_correct === null
        ? h("span", { class: "text-zinc-500" }, "풀지 않음")
        : h("span", { class: item.is_correct ? "text-green-700" : "text-red-700" }, item.is_correct ? "정답" : "오답"),
      h("span", { class: "break-words" }, `${i + 1}. ${item.term}`),
    ),
    h(
      "ul",
      { class: "space-y-1 text-sm" },
      item.choices.map((choice, c) => {
        const isCorrect = c === item.correct_index;
        const isMyWrong = c === item.selected_index && item.is_correct === false;
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
