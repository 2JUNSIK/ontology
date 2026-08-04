import ReactDOM from "react-dom/client";
import App from "./App";
import { ThemeProvider } from "./theme";
import { ToastProvider } from "./components/ui/Toast";
import { ConfirmProvider } from "./components/ui/ConfirmDialog";
import "./index.css";

// StrictMode는 생략한다: react-force-graph-2d 캔버스가 dev 이중 마운트에서
// 깜빡일 수 있어 시각 확인을 방해하기 때문(MVP 편의).
// 전역 프로바이더: 테마(다크/라이트) · 토스트 알림 · 확인 모달을 App 전체에 제공한다.
ReactDOM.createRoot(document.getElementById("root")!).render(
  <ThemeProvider>
    <ToastProvider>
      <ConfirmProvider>
        <App />
      </ConfirmProvider>
    </ToastProvider>
  </ThemeProvider>,
);
