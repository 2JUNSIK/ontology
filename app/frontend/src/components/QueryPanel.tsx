import { useState } from "react";
import { errMessage, queryGraph } from "../api";
import type { QueryResponse } from "../types";
import GraphView from "./GraphView";
import KnowledgeInventory from "./KnowledgeInventory";

interface Props {
  projectId: string;
}

function fmtCell(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

// 자연어 질문 → Claude가 읽기 전용 Cypher로 변환·실행 → 결과를 그래프 + 표로 보여준다.
// (탐색은 읽기 전용이라 누적 그래프를 바꾸지 않는다. 결과는 이 패널 안에서만 관리.)
export default function QueryPanel({ projectId }: Props) {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleQuery() {
    if (!question.trim()) return;
    setLoading(true);
    setError(null);
    try {
      setResult(await queryGraph(projectId, question));
    } catch (e) {
      setError(errMessage(e));
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  const hasGraph =
    !!result && (result.graph.nodes.length > 0 || result.graph.links.length > 0);
  const hasRows = !!result && result.rows.length > 0;

  return (
    <div className="panel">
      <h2 className="section-title">지식 탐색</h2>
      <p className="section-desc" style={{ marginBottom: 14 }}>
        자연어로 질문하면 Claude가 Cypher로 바꿔 지식그래프를 읽어옵니다.
      </p>
      <div className="notice info">
        ⓘ 질문을 <b>읽기 전용 Cypher로 변환·실행</b>합니다. “탐색”은 실제 Claude API를
        호출합니다(키가 있으면 과금). 데이터는 변경되지 않습니다.
      </div>

      <textarea
        placeholder={
          "예) 녹조와 직접 연결된 개념을 모두 보여줘\n예) 경보단계 타입 노드는 뭐가 있어?"
        }
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
      />
      <div className="row between" style={{ marginTop: 12 }}>
        <span className="muted" />
        <button className="primary" onClick={handleQuery} disabled={loading || !question.trim()}>
          {loading ? "탐색 중… (Claude 호출)" : "탐색 →"}
        </button>
      </div>

      {error && (
        <div className="error" style={{ marginTop: 14 }}>
          {error}
        </div>
      )}

      {result && (
        <div style={{ marginTop: 18 }}>
          {/* ① 생성된 Cypher (투명성·검증·학습) */}
          {result.cypher && (
            <div className="query-cypher">
              <div className="query-cypher-head">
                <span className="badge">생성된 Cypher</span>
                {result.explanation && <span className="muted">{result.explanation}</span>}
              </div>
              <pre>{result.cypher}</pre>
            </div>
          )}

          {result.error ? (
            <div className="notice" style={{ marginTop: 14 }}>
              ⚠ {result.error}
            </div>
          ) : (
            <>
              <div className="notice info" style={{ marginTop: 14 }}>
                결과 — 노드 {result.graph.nodes.length} · 관계 {result.graph.links.length}
                {hasRows && !hasGraph ? ` · 행 ${result.rows.length}` : ""}
              </div>

              {/* ② 결과 그래프 + 노드/관계 표 */}
              {hasGraph && (
                <>
                  <div style={{ marginTop: 14 }}>
                    <GraphView data={result.graph} />
                  </div>
                  <div style={{ marginTop: 14 }}>
                    <KnowledgeInventory data={result.graph} readOnly />
                  </div>
                </>
              )}

              {/* ③ 스칼라/집계 결과 표(그래프 요소가 아닌 경우) */}
              {!hasGraph && hasRows && (
                <div className="kg-table-wrap" style={{ marginTop: 14 }}>
                  <table className="kg-table">
                    <thead>
                      <tr>
                        {result.columns.map((c, i) => (
                          <th key={i}>{c}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {result.rows.slice(0, 100).map((row, ri) => (
                        <tr key={ri}>
                          {row.map((cell, ci) => (
                            <td key={ci} className="mono">
                              {fmtCell(cell)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {!hasGraph && !hasRows && (
                <div className="notice" style={{ marginTop: 14 }}>
                  조건에 맞는 결과가 없습니다. 질문을 바꿔 다시 시도해 보세요.
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
