// 브라우저 기본 window.confirm 대체 — 앱 톤에 맞는 커스텀 확인 모달.
// promise 기반이라 호출부는 `if (await confirm({...})) { ... }` 한 줄로 쓴다.
// 접근성: role="dialog"/aria-modal/aria-describedby, Esc 닫기, 열릴 때 확인 버튼 포커스,
// Tab 포커스 트랩, 배경(#root) inert, 닫으면 원래 포커스 복귀.
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";

export interface ConfirmOptions {
  title: string;
  body?: string;
  confirmText?: string;
  cancelText?: string;
  danger?: boolean; // true면 확인 버튼을 위험(빨강) 스타일로
}

type ConfirmFn = (opts: ConfirmOptions) => Promise<boolean>;

const Ctx = createContext<ConfirmFn | null>(null);

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [opts, setOpts] = useState<ConfirmOptions | null>(null);
  const modalRef = useRef<HTMLDivElement>(null);
  const confirmBtnRef = useRef<HTMLButtonElement>(null);
  const lastFocused = useRef<HTMLElement | null>(null);
  // 현재 대기 중인 promise의 resolve. 이중 오픈/언마운트에서도 반드시 한 번은 정리한다.
  const pending = useRef<((v: boolean) => void) | null>(null);

  const settle = useCallback((v: boolean) => {
    pending.current?.(v);
    pending.current = null;
  }, []);

  const confirm = useCallback<ConfirmFn>(
    (o) =>
      new Promise<boolean>((resolve) => {
        settle(false); // 이미 떠 있던 확인창이 있으면 '취소'로 정리(대기 promise 유실 방지)
        lastFocused.current = document.activeElement as HTMLElement | null;
        pending.current = resolve;
        setOpts(o);
      }),
    [settle],
  );

  const close = useCallback(
    (v: boolean) => {
      settle(v);
      setOpts(null);
    },
    [settle],
  );

  // 언마운트 시 대기 중 promise를 '취소'로 정리(awaiting 호출부가 영구 대기하지 않도록).
  useEffect(() => () => settle(false), [settle]);

  // 열릴 때: 배경 inert + 확인 버튼 포커스 + Esc 닫기. 닫힐 때(cleanup): inert 해제 후 포커스 복원.
  useEffect(() => {
    if (!opts) return;
    const root = document.getElementById("root");
    root?.setAttribute("inert", "");
    confirmBtnRef.current?.focus();
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        close(false);
      }
    }
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      root?.removeAttribute("inert"); // 포커스 복원 전에 해제(inert 요소는 focus 불가)
      const el = lastFocused.current;
      if (el && document.body.contains(el)) el.focus();
    };
  }, [opts, close]);

  // Tab 포커스 트랩: 모달 내부의 '활성' 포커스 요소들 사이에서만 순환(:disabled 제외).
  function trapTab(e: React.KeyboardEvent) {
    if (e.key !== "Tab") return;
    const nodes = modalRef.current?.querySelectorAll<HTMLElement>(
      'button:not(:disabled), [href], input:not(:disabled), textarea:not(:disabled), select:not(:disabled), [tabindex]:not([tabindex="-1"])',
    );
    if (!nodes || nodes.length === 0) return;
    const first = nodes[0];
    const last = nodes[nodes.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }

  return (
    <Ctx.Provider value={confirm}>
      {children}
      {opts &&
        createPortal(
          <div
            className="modal-overlay"
            onMouseDown={(e) => {
              // 오버레이(배경) 클릭 시 취소. 모달 내부 클릭은 무시.
              if (e.target === e.currentTarget) close(false);
            }}
          >
            <div
              className="modal"
              ref={modalRef}
              role="dialog"
              aria-modal="true"
              aria-labelledby="confirm-title"
              aria-describedby={opts.body ? "confirm-body" : undefined}
              onKeyDown={trapTab}
            >
              <h3 id="confirm-title" className="modal-title">
                {opts.title}
              </h3>
              {opts.body && (
                <p id="confirm-body" className="modal-body">
                  {opts.body}
                </p>
              )}
              <div className="modal-actions">
                <button className="ghost" onClick={() => close(false)}>
                  {opts.cancelText ?? "취소"}
                </button>
                <button
                  ref={confirmBtnRef}
                  className={opts.danger ? "danger" : "primary"}
                  onClick={() => close(true)}
                >
                  {opts.confirmText ?? "확인"}
                </button>
              </div>
            </div>
          </div>,
          document.body,
        )}
    </Ctx.Provider>
  );
}

export function useConfirm(): ConfirmFn {
  const c = useContext(Ctx);
  if (!c) throw new Error("useConfirm must be used within ConfirmProvider");
  return c;
}
