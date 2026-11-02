/*
 * 2026-11-02 - voda-voca - 알림·확인 UI 래퍼: SweetAlert2 토스트와 확인 모달 (REQ-022). 브라우저 alert/confirm 은 쓰지 않는다.
 * 파일 위치: src/frontend/js/core/toast.js
 */

/**
 * 하단 토스트. 자동으로 사라진다.
 * @param {string} title
 * @param {"success"|"error"|"info"|"warning"} [icon]
 */
export function toast(title, icon = "success") {
  if (!globalThis.Swal) return;
  globalThis.Swal.fire({
    toast: true,
    position: "bottom",
    showConfirmButton: false,
    timer: 2800,
    icon,
    title,
  });
}

/**
 * 확인 모달. 삭제처럼 되돌리기 어려운 행동에 쓴다.
 * @param {{title: string, text?: string, confirmText?: string, danger?: boolean}} opts
 * @returns {Promise<boolean>}
 */
export async function confirmDialog({ title, text = "", confirmText = "확인", danger = false }) {
  if (!globalThis.Swal) return false;
  const result = await globalThis.Swal.fire({
    title,
    text,
    icon: danger ? "warning" : "question",
    showCancelButton: true,
    confirmButtonText: confirmText,
    cancelButtonText: "취소",
    confirmButtonColor: danger ? "#dc2626" : "#2563eb",
    reverseButtons: true,
    allowOutsideClick: !danger,
  });
  return result.isConfirmed === true;
}
