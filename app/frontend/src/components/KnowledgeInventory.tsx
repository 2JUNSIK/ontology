import { useEffect, useState } from "react";
import type { GraphData } from "../types";

interface Props {
  data: GraphData;
  busyKey: string | null; // 삭제 진행 중인 항목 키(중복 클릭 방지 + 스피너 표시)
  onDeleteEntity: (name: string) => void;
  onDeleteRelation: (source: string, target: string, type: string) => void;
}

export const entKey = (name: string) => `e:${name}`;
// 이름/타입에 구분자가 섞여도 충돌하지 않도록 배열을 그대로 직렬화해 키로 쓴다.
export const relKey = (source: string, type: string, target: string) =>
  "r:" + JSON.stringify([source, type, target]);

const PAGE_SIZE = 10; // 10개 초과 시 페이지 분할

function Pager({
  page,
  totalPages,
  onPage,
}: {
  page: number;
  totalPages: number;
  onPage: (p: number) => void;
}) {
  if (totalPages <= 1) return null;
  return (
    <div className="kg-pager">
      <button className="mini ghost" disabled={page <= 1} onClick={() => onPage(page - 1)}>
        ← 이전
      </button>
      <span className="kg-pager-info">
        {page} <span className="muted">/ {totalPages}</span>
      </span>
      <button className="mini ghost" disabled={page >= totalPages} onClick={() => onPage(page + 1)}>
        다음 →
      </button>
    </div>
  );
}

// 노드/관계를 "데이터"로 보여주고 개별 삭제한다. 10개 초과 시 페이지로 나눈다.
export default function KnowledgeInventory({
  data,
  busyKey,
  onDeleteEntity,
  onDeleteRelation,
}: Props) {
  const anyBusy = busyKey !== null;

  const [entPage, setEntPage] = useState(1);
  const [relPage, setRelPage] = useState(1);

  const entTotalPages = Math.max(1, Math.ceil(data.nodes.length / PAGE_SIZE));
  const relTotalPages = Math.max(1, Math.ceil(data.links.length / PAGE_SIZE));

  // 삭제 등으로 데이터가 줄어 현재 페이지가 범위를 벗어나면 마지막 페이지로 당긴다.
  useEffect(() => {
    if (entPage > entTotalPages) setEntPage(entTotalPages);
  }, [entPage, entTotalPages]);
  useEffect(() => {
    if (relPage > relTotalPages) setRelPage(relTotalPages);
  }, [relPage, relTotalPages]);

  const entStart = (Math.min(entPage, entTotalPages) - 1) * PAGE_SIZE;
  const relStart = (Math.min(relPage, relTotalPages) - 1) * PAGE_SIZE;
  const entRows = data.nodes.slice(entStart, entStart + PAGE_SIZE);
  const relRows = data.links.slice(relStart, relStart + PAGE_SIZE);

  const rangeLabel = (start: number, shown: number, total: number) =>
    total === 0 ? "" : `${start + 1}–${start + shown} / ${total}`;

  return (
    <div className="kg-inv">
      {/* 노드 */}
      <div>
        <div className="kg-inv-head">
          <h4>노드 <span className="muted">({data.nodes.length})</span></h4>
          {data.nodes.length > 0 && (
            <span className="muted kg-range">{rangeLabel(entStart, entRows.length, data.nodes.length)}</span>
          )}
        </div>
        {data.nodes.length === 0 ? (
          <div className="kg-empty">아직 노드가 없습니다. 위 “지식 입력”에서 문장을 추가해 보세요.</div>
        ) : (
          <>
            <div className="kg-table-wrap">
              <table className="kg-table">
                <thead>
                  <tr>
                    <th>이름</th>
                    <th>타입</th>
                    <th>설명</th>
                    <th className="actions" />
                  </tr>
                </thead>
                <tbody>
                  {entRows.map((n) => {
                    const key = entKey(n.name);
                    const busy = busyKey === key;
                    return (
                      <tr key={key} className={busy ? "row-busy" : ""}>
                        <td><b>{n.name}</b></td>
                        <td>
                          {n.types.length === 0 ? (
                            <span className="muted">미분류</span>
                          ) : (
                            n.types.map((t) => (
                              <span key={t} className="badge" style={{ marginRight: 4 }}>{t}</span>
                            ))
                          )}
                        </td>
                        <td className="kg-desc">{n.description || <span className="muted">—</span>}</td>
                        <td className="actions">
                          <button
                            className="mini danger"
                            disabled={anyBusy}
                            onClick={() => onDeleteEntity(n.name)}
                          >
                            {busy ? "삭제 중…" : "삭제"}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <Pager page={Math.min(entPage, entTotalPages)} totalPages={entTotalPages} onPage={setEntPage} />
          </>
        )}
      </div>

      {/* 관계 */}
      <div>
        <div className="kg-inv-head">
          <h4>관계 <span className="muted">({data.links.length})</span></h4>
          {data.links.length > 0 && (
            <span className="muted kg-range">{rangeLabel(relStart, relRows.length, data.links.length)}</span>
          )}
        </div>
        {data.links.length === 0 ? (
          <div className="kg-empty">아직 관계가 없습니다.</div>
        ) : (
          <>
            <div className="kg-table-wrap">
              <table className="kg-table">
                <thead>
                  <tr>
                    <th>출발</th>
                    <th>관계</th>
                    <th>도착</th>
                    <th>설명</th>
                    <th className="actions" />
                  </tr>
                </thead>
                <tbody>
                  {relRows.map((l) => {
                    const key = relKey(l.source, l.type, l.target);
                    const busy = busyKey === key;
                    return (
                      <tr key={key} className={busy ? "row-busy" : ""}>
                        <td className="mono">{l.source}</td>
                        <td><span className="badge rel">{l.type}</span></td>
                        <td className="mono">{l.target}</td>
                        <td className="kg-desc">{l.description || <span className="muted">—</span>}</td>
                        <td className="actions">
                          <button
                            className="mini danger"
                            disabled={anyBusy}
                            onClick={() => onDeleteRelation(l.source, l.target, l.type)}
                          >
                            {busy ? "삭제 중…" : "삭제"}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <Pager page={Math.min(relPage, relTotalPages)} totalPages={relTotalPages} onPage={setRelPage} />
          </>
        )}
      </div>
    </div>
  );
}
