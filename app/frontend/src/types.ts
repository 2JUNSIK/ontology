// 공통 중간표현 TS 타입 — backend/app/models.py 와 1:1 대응 (설계 불변식 §1).
// v2: 프로젝트 기반 지식그래프.

export interface Project {
  id: string;
  name: string;
  description: string;
  created_ts?: number;
}

// 지식 노드. name=값, type=타입 라벨(비면 미분류).
export interface Entity {
  name: string;
  type: string;
  description: string;
}

// 지식 관계. source/target=엔티티 이름, type=관계타입.
export interface Relation {
  source: string;
  target: string;
  type: string;
  description: string;
}

// Claude 추출 결과(미리보기/ingest 공용).
export interface Extraction {
  entities: Entity[];
  relations: Relation[];
  summary: string;
}

// ---- 그래프 시각화(/api/projects/{id}/graph) ----
export interface GraphNodeData {
  id: string; // = name (프로젝트 내 고유)
  name: string;
  type: string; // 색상용 대표 타입(첫 타입 라벨)
  types: string[]; // 전체 타입 라벨
  description: string;
}

export interface GraphLinkData {
  source: string;
  target: string;
  type: string;
  description: string;
}

export interface GraphData {
  nodes: GraphNodeData[];
  links: GraphLinkData[];
}

export interface IngestResponse {
  stats: Record<string, any>;
  graph: GraphData;
}
