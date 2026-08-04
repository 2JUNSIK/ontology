// 우하단 토스트 알림. 생성/반영/삭제 같은 일시적 성공·실패 피드백에 사용한다.
// 자동 소멸 + 수동 닫기, aria-live="polite"로 스크린리더에 알림. 언마운트 시 타이머 정리.
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";

type ToastKind = "success" | "error" | "info";

interface ToastItem {
  id: number;
  kind: ToastKind;
  msg: string;
}

interface ToastApi {
  success: (msg: string) => void;
  error: (msg: string) => void;
  info: (msg: string) => void;
}

const Ctx = createContext<ToastApi | null>(null);
// kind별 자동 소멸(ms). 실패/무동작(info)은 놓치기 쉬워 더 오래 띄운다.
const DURATION: Record<ToastKind, number> = { success: 3800, info: 5200, error: 6500 };

const ICON: Record<ToastKind, string> = { success: "✓", error: "⚠", info: "ⓘ" };

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const idRef = useRef(0);
  const timers = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());

  const remove = useCallback((id: number) => {
    setItems((prev) => prev.filter((t) => t.id !== id));
    const tm = timers.current.get(id);
    if (tm) {
      clearTimeout(tm);
      timers.current.delete(id);
    }
  }, []);

  const push = useCallback(
    (kind: ToastKind, msg: string) => {
      const id = ++idRef.current;
      setItems((prev) => [...prev, { id, kind, msg }]);
      const tm = setTimeout(() => remove(id), DURATION[kind]);
      timers.current.set(id, tm);
    },
    [remove],
  );

  // 언마운트 시 남은 타이머 전부 정리(메모리 누수·죽은 setState 방지).
  useEffect(() => {
    const map = timers.current;
    return () => {
      map.forEach((tm) => clearTimeout(tm));
      map.clear();
    };
  }, []);

  const api = useMemo<ToastApi>(
    () => ({
      success: (m) => push("success", m),
      error: (m) => push("error", m),
      info: (m) => push("info", m),
    }),
    [push],
  );

  return (
    <Ctx.Provider value={api}>
      {children}
      {createPortal(
        // 래퍼에는 aria-live를 두지 않고(중첩 live 방지), 각 토스트가 kind에 맞는 role을 갖는다.
        // error는 role="alert"(assertive)로 사용자 흐름을 끊고 알리고, 나머지는 role="status"(polite).
        <div className="toast-wrap">
          {items.map((t) => (
            <div
              key={t.id}
              className={`toast toast-${t.kind}`}
              role={t.kind === "error" ? "alert" : "status"}
            >
              <span className="toast-icon" aria-hidden>
                {ICON[t.kind]}
              </span>
              <span className="toast-msg">{t.msg}</span>
              <button className="toast-close" aria-label="알림 닫기" onClick={() => remove(t.id)}>
                ✕
              </button>
            </div>
          ))}
        </div>,
        document.body,
      )}
    </Ctx.Provider>
  );
}

export function useToast(): ToastApi {
  const c = useContext(Ctx);
  if (!c) throw new Error("useToast must be used within ToastProvider");
  return c;
}
