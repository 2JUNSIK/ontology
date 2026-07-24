import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 개발 서버 :5173 (백엔드 CORS 허용 오리진과 일치, main.py 참조).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
});
