// 백엔드(FastAPI, :8000) 클라이언트. 엔드포인트는 PLAN.md §5 참조 (v2).
import axios from "axios";
import type { Extraction, GraphData, IngestResponse, Project } from "./types";

const BASE_URL = "http://localhost:8000";

// /extract 는 Claude 호출(최대 max_tokens=4000)로 지연될 수 있어 여유 있게 잡는다.
const client = axios.create({ baseURL: BASE_URL, timeout: 120000 });

export async function listProjects(): Promise<Project[]> {
  const { data } = await client.get<Project[]>("/api/projects");
  return data;
}

export async function createProject(name: string, description: string): Promise<Project> {
  const { data } = await client.post<Project>("/api/projects", { name, description });
  return data;
}

export async function deleteProject(id: string): Promise<{ entities_deleted: number; project_deleted: number }> {
  const { data } = await client.delete(`/api/projects/${encodeURIComponent(id)}`);
  return data;
}

// 주의: 실제 Claude API를 호출한다(키가 있으면 과금). 호출 측에서 사용자에게 고지할 것.
export async function extractKnowledge(projectId: string, text: string): Promise<Extraction> {
  const { data } = await client.post<Extraction>(
    `/api/projects/${encodeURIComponent(projectId)}/extract`,
    { text },
  );
  return data;
}

export async function ingestExtraction(
  projectId: string,
  extraction: Extraction,
): Promise<IngestResponse> {
  const { data } = await client.post<IngestResponse>(
    `/api/projects/${encodeURIComponent(projectId)}/ingest`,
    extraction,
  );
  return data;
}

export async function getProjectGraph(projectId: string): Promise<GraphData> {
  const { data } = await client.get<GraphData>(
    `/api/projects/${encodeURIComponent(projectId)}/graph`,
  );
  return data;
}

// axios 오류를 사람이 읽는 메시지로 변환(백엔드 detail 우선).
export function errMessage(e: unknown): string {
  if (axios.isAxiosError(e)) {
    const detail = (e.response?.data as any)?.detail;
    if (detail) return typeof detail === "string" ? detail : JSON.stringify(detail);
    if (e.code === "ERR_NETWORK") return "백엔드(:8000)에 연결할 수 없습니다. uvicorn이 켜져 있나요?";
    if (e.code === "ECONNABORTED") return "요청이 시간 초과되었습니다(Claude 응답 지연 가능). 잠시 후 다시 시도하세요.";
    return e.message;
  }
  return String(e);
}
