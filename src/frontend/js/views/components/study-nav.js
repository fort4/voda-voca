/*
 * 2026-11-05 - voda-voca - 학습 세션 진입 도우미: 모드·출제 풀을 쿼리로 실어 세션 화면으로 이동한다
 * 파일 위치: src/frontend/js/views/components/study-nav.js
 */

import { startPath } from "../../core/home-model.js";

/**
 * @param {(path: string, query?: Record<string, string>) => void} navigate 라우터의 navigate (경로와 쿼리를 따로 받는다)
 * @param {string} mode
 * @param {"all"|"bookmarks"|"wrong"|"due"} [source]
 * @param {{direction: string, format: string}} [options] 퀴즈 방향·형식 (생략하면 영→한 4지선다)
 */
export function openSession(navigate, mode, source = "all", options = undefined) {
  const [path, query] = startPath(mode, source, options).split("?");
  navigate(path, Object.fromEntries(new URLSearchParams(query)));
}
