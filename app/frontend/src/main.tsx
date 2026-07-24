import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

// StrictMode는 생략한다: react-force-graph-2d 캔버스가 dev 이중 마운트에서
// 깜빡일 수 있어 시각 확인을 방해하기 때문(MVP 편의).
ReactDOM.createRoot(document.getElementById("root")!).render(<App />);
