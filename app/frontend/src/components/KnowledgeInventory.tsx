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

// 노드/관계를 "데이터"로 보여주고 개별 삭제한다. 표는 /graph 응답을 그대로 사용한다.
export default function KnowledgeInventory({
  data,
  busyKey,
  onDeleteEntity,
  onDeleteRelation,
}: Props) {
  const anyBusy = busyKey !== null;

  return (
    <div className="kg-inv">
      {/* 노드 */}
      <div>
        <h4>노드 <span className="muted">({data.nodes.length})</span></h4>
        {data.nodes.length === 0 ? (
          <div className="kg-empty">아직 노드가 없습니다. 위 “지식 입력”에서 문장을 추가해 보세요.</div>
        ) : (
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
                {data.nodes.map((n) => {
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
        )}
      </div>

      {/* 관계 */}
      <div>
        <h4>관계 <span className="muted">({data.links.length})</span></h4>
        {data.links.length === 0 ? (
          <div className="kg-empty">아직 관계가 없습니다.</div>
        ) : (
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
                {data.links.map((l) => {
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
        )}
      </div>
    </div>
  );
}
