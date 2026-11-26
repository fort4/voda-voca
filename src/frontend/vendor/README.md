<!-- 2026-11-24 - voda-voca - 자체 호스팅한 외부 자원의 출처·버전·라이선스 기록 (Architecture A4 해소) -->
<!-- 파일 위치: src/frontend/vendor/README.md -->

# vendor/ — 자체 호스팅 외부 자원

화면에 쓰는 외부 라이브러리·폰트를 CDN 에서 받지 않고 이 폴더에서 같은 출처로 제공한다.
**파일을 직접 수정하지 않는다.** 버전을 올릴 때는 새 버전을 내려받아 폴더·파일명의 버전 표기와
`index.html`, `tests/self-hosted.test.js` 를 함께 고친다.

| 자원 | 버전 | 경로 | 원 출처 | 라이선스 |
| :--- | :--- | :--- | :--- | :--- |
| Tailwind CSS (Play CDN 스크립트) | 3.4.17 | `tailwindcss-3.4.17.js` | `https://cdn.tailwindcss.com` (2026-11-24 기준 3.4.17 로 연결) | MIT |
| SweetAlert2 | 11.10.5 | `sweetalert2-11.10.5/` | jsDelivr `npm/sweetalert2@11.10.5/dist` | MIT |
| Lucide (UMD) | 0.460.0 | `lucide-0.460.0/` | unpkg `lucide@0.460.0/dist/umd` | ISC |
| Chart.js (UMD) | 4.6.2 | `chart.js-4.6.2/` | npm `chart.js@4.6.2` 의 `dist/chart.umd.js` (2026-11-26, 배포본 sha512 대조) | MIT (`LICENSE.md`) |
| Pretendard Variable (동적 서브셋, woff2 92조각) | 1.3.9 | `fonts/pretendard-1.3.9/` | jsDelivr `gh/orioncactus/pretendard@v1.3.9` | SIL OFL 1.1 (`LICENSE.txt`) |
| Paperlogy Bold | 1.0 | `fonts/Paperlogy-7Bold.woff2` | jsDelivr `gh/projectnoonnu/2408-3@1.0` | SIL OFL 1.1 (`fonts/Paperlogy-LICENSE.txt`) |

## 메모

- Paperlogy 라이선스 확인(2026-11-26, 이슈 #36): ① 글꼴 파일에 내장된 `name` 테이블의 라이선스 항목이 "SIL Open Font License, Version 1.1", 저작권 표시가 `Copyright © 2024 PT&` 다. ② 제작자 페이지(<https://freesentation.blog/paperlogyfont>)는 OFL 에 따라 글꼴 단독 판매와 라이선스 변경을 뺀 상업적 이용·수정·재배포가 가능하다고 밝힌다. ③ 이 저장소의 파일은 원 출처의 `v1.0` 배포본과 sha256 이 같다(`390de733…d7cf`). 내장 설명의 "파워포인트 전용 글꼴"은 소개 문구이며 라이선스 항목에는 용도 제한이 없다.
- Pretendard CSS 는 원본의 `../../../packages/.../woff2-dynamic-subset/` 경로를 `woff2/` 로만 바꿨다. 브라우저는 화면에 쓰인 글자가 속한 조각만 내려받는다 (92개 합계 약 3.1MB, 한 화면에 보통 몇 개).
- Tailwind Play CDN 스크립트는 브라우저에서 스타일을 계산한다. 공식적으로 운영 비권장이므로, 운영 성능이 문제가 되면 standalone CLI 로 정적 CSS 를 생성하는 방식을 별도 결정으로 검토한다.
