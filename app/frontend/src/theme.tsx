// 라이트/다크 테마 컨텍스트. data-theme 속성으로 CSS 토큰을 전환하고 localStorage에 저장한다.
// GraphView처럼 캔버스에 색을 직접 칠하는 컴포넌트도 useTheme으로 현재 테마를 읽어 색을 맞춘다.
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type Theme = "light" | "dark";

interface ThemeCtx {
  theme: Theme;
  toggle: () => void;
}

const Ctx = createContext<ThemeCtx | null>(null);
const STORAGE_KEY = "kg-theme";

// 초기 테마: 저장값 → 없으면 OS 선호(prefers-color-scheme) → 기본 light.
function initialTheme(): Theme {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    /* localStorage 접근 불가(프라이빗 모드 등) — 무시 */
  }
  if (typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches) {
    return "dark";
  }
  return "light";
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(initialTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    // 모바일 브라우저 상단 크롬 색도 실제 토글에 맞춰 갱신(다크에서 흰 주소창 방지).
    let meta = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]');
    if (!meta) {
      meta = document.createElement("meta");
      meta.name = "theme-color";
      document.head.appendChild(meta);
    }
    meta.content = theme === "dark" ? "#0e1013" : "#ffffff";
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      /* 저장 실패는 조용히 무시(테마는 세션 내에서 계속 동작) */
    }
  }, [theme]);

  const value = useMemo<ThemeCtx>(
    () => ({ theme, toggle: () => setTheme((t) => (t === "dark" ? "light" : "dark")) }),
    [theme],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useTheme(): ThemeCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error("useTheme must be used within ThemeProvider");
  return c;
}
