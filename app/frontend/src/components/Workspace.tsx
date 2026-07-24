import { useEffect, useState } from "react";
import { errMessage, extractKnowledge, getProjectGraph, ingestExtraction } from "../api";
import type { Extraction, GraphData, Project } from "../types";
import ExtractionPreview from "./ExtractionPreview";
import GraphView from "./GraphView";

interface Props {
  project: Project;
  onBack: () => void;
}

const EMPTY: GraphData = { nodes: [], links: [] };

export default function Workspace({ project, onBack }: Props) {
  const [graph, setGraph] = useState<GraphData>(EMPTY);
  const [text, setText] = useState("");
  const [extraction, setExtraction] = useState<Extraction | null>(null);
  const [emptyExtract, setEmptyExtract] = useState(false);
  const [ingestMsg, setIngestMsg] = useState<string | null>(null);

  const [loadingGraph, setLoadingGraph] = useState(true);
  const [extracting, setExtracting] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadGraph() {
    setLoadingGraph(true);
    setError(null);
    try {
      setGraph(await getProjectGraph(project.id));
    } catch (e) {
      setError(errMessage(e));
    } finally {
      setLoadingGraph(false);
    }
  }

  useEffect(() => {
    loadGraph();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id]);

  function handleBack() {
    if (extraction && !window.confirm("추출 미리보기가 아직 있습니다. 나가면 사라집니다. 계속할까요?"))
      return;
    onBack();
  }

  async function handleExtract() {
    if (!text.trim()) return;
    setExtracting(true);
    setError(null);
    setExtraction(null);
    setEmptyExtract(false);
    setIngestMsg(null);
    try {
      const res = await extractKnowledge(project.id, text);
      if (res.entities.length === 0 && res.relations.length === 0) {
        setEmptyExtract(true);
      } else {
        setExtraction(res);
      }
    } catch (e) {
      setError(errMessage(e));
    } finally {
      setExtracting(false);
    }
  }

  async function handleIngest(edited: Extraction) {
    setIngesting(true);
    setError(null);
    try {
      const res = await ingestExtraction(project.id, edited);
      setGraph(res.graph);
      setExtraction(null);
      setEmptyExtract(false);
      setText("");
      const c = (res.stats?.counters ?? {}) as Record<string, number>;
      setIngestMsg(
        `반영 완료 — 새 노드 ${c.nodes_created ?? 0}개, 새 관계 ${c.relationships_created ?? 0}개` +
          " (기존 항목은 병합됨)",
      );
    } catch (e) {
      setError(errMessage(e));
    } finally {
      setIngesting(false);
    }
  }

  return (
    <div>
      <div className="ws-head">
        <div>
          <button className="mini ghost" onClick={handleBack} style={{ marginLeft: -6 }}>
            ← 프로젝트 목록
          </button>
          <h1 className="ws-title">{project.name}</h1>
          {project.description && <div className="muted">{project.description}</div>}
        </div>
        <span className="meta-pill">
          노드 {graph.nodes.length} · 관계 {graph.links.length}
        </span>
      </div>

      {error && <div className="error">{error}</div>}

      <div className="workspace-grid">
        {/* 좌: 누적 지식그래프 */}
        <div className="panel graph-panel">
          <div className="row between" style={{ marginBottom: 16 }}>
            <h2 className="section-title">지식그래프</h2>
            <button className="mini" onClick={loadGraph} disabled={loadingGraph}>
              새로고침
            </button>
          </div>
          {loadingGraph ? (
            <div className="graph-wrap">
              <div className="center-msg">불러오는 중…</div>
            </div>
          ) : (
            <GraphView data={graph} />
          )}
        </div>

        {/* 우: 지식 입력 + 추출 미리보기 */}
        <div>
          <div className="panel">
            <h2 className="section-title">지식 입력</h2>
            <p className="section-desc" style={{ marginBottom: 14 }}>
              문장 단위로 넣을수록 추출이 정확합니다.
            </p>
            <div className="notice info">
              ⓘ 문장을 입력하면 <b>Claude가 노드·관계를 추출</b>합니다. “추출”은 실제 Claude
              API를 호출합니다(키가 있으면 과금).
            </div>
            <textarea
              placeholder={
                "예) 조류경보제는 관심·경계·대발생 3단계로 운영된다.\n예) 관심 단계는 남조류세포수가 1000 cells/mL 이상일 때 발령된다."
              }
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
            <div className="row between" style={{ marginTop: 12 }}>
              <span className="muted" />
              <button className="primary" onClick={handleExtract} disabled={extracting || !text.trim()}>
                {extracting ? "추출 중… (Claude 호출)" : "추출 →"}
              </button>
            </div>
          </div>

          {ingestMsg && (
            <div className="notice success" style={{ marginTop: 16 }}>
              ✓ {ingestMsg}
            </div>
          )}

          {emptyExtract && (
            <div className="notice" style={{ marginTop: 16 }}>
              추출된 노드·관계가 없습니다. 문장을 더 구체적으로 바꿔 다시 시도해 보세요.
              (Claude 키가 없거나 호출이 실패했을 수도 있습니다.)
            </div>
          )}

          {extraction && (
            <ExtractionPreview
              extraction={extraction}
              ingesting={ingesting}
              onCancel={() => setExtraction(null)}
              onConfirm={handleIngest}
            />
          )}
        </div>
      </div>
    </div>
  );
}
