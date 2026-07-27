import { useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import type { GraphData, GraphNodeData } from "../types";
import { formatQuantity } from "./KnowledgeInventory";

interface Props {
  data: GraphData;
}

// 라이트 배경에서 대비가 좋은 팔레트(toss 톤)
const PALETTE = [
  "#3182f6", "#12b886", "#f59f00", "#f04452", "#7c3aed",
  "#e64980", "#0ca678", "#e8590c", "#4263eb", "#c2255c",
  "#1098ad", "#9c36b5",
];
const UNTYPED = "#adb5bd";

export default function GraphView({ data }: Props) {
  const [selected, setSelected] = useState<GraphNodeData | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 800, h: 560 });

  // 컨테이너 크기에 맞춰 캔버스 크기 조정
  useEffect(() => {
    if (!wrapRef.current) return;
    const el = wrapRef.current;
    const ro = new ResizeObserver(() => setSize({ w: el.clientWidth, h: el.clientHeight }));
    ro.observe(el);
    setSize({ w: el.clientWidth, h: el.clientHeight });
    return () => ro.disconnect();
  }, []);

  // 타입별 색상 맵(미분류는 회색)
  const colorFor = useMemo(() => {
    const types = Array.from(new Set(data.nodes.map((n) => n.type).filter(Boolean)));
    const map = new Map<string, string>();
    types.forEach((t, i) => map.set(t, PALETTE[i % PALETTE.length]));
    return (type: string) => (type ? map.get(type) ?? UNTYPED : UNTYPED);
  }, [data]);

  const legendTypes = useMemo(
    () => Array.from(new Set(data.nodes.map((n) => n.type).filter(Boolean))),
    [data],
  );

  // react-force-graph는 데이터를 변형하므로 복제해서 넘긴다.
  const graphData = useMemo(
    () => ({
      nodes: data.nodes.map((n) => ({ ...n })),
      links: data.links.map((l) => ({ ...l })),
    }),
    [data],
  );

  // 선택 노드가 그래프에서 사라지면(예: 새 그래프) 패널 닫기
  useEffect(() => {
    if (selected && !data.nodes.some((n) => n.id === selected.id)) setSelected(null);
  }, [data, selected]);

  return (
    <div className="graph-wrap" ref={wrapRef}>
      {graphData.nodes.length === 0 ? (
        <div className="center-msg">
          <div>아직 지식이 없습니다.</div>
          <div className="muted">위쪽 “지식 입력”에서 문장을 넣고 “추출 → 그래프에 추가”를 해보세요.</div>
        </div>
      ) : (
        <>
          <ForceGraph2D
            width={size.w}
            height={size.h}
            graphData={graphData}
            backgroundColor="#f9fafb"
            nodeRelSize={6}
            linkColor={() => "rgba(139,149,161,0.55)"}
            linkDirectionalArrowLength={4}
            linkDirectionalArrowRelPos={1}
            linkWidth={1.2}
            onNodeClick={(node: any) => setSelected(node as GraphNodeData)}
            nodeCanvasObject={(node: any, ctx, globalScale) => {
              if (node.x == null || node.y == null) return; // 첫 틱 좌표 미초기화 가드
              const label: string = node.name;
              const r = 6;
              ctx.beginPath();
              ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
              ctx.fillStyle = colorFor(node.type);
              ctx.fill();
              if (selected && selected.id === node.id) {
                ctx.strokeStyle = "#191f28";
                ctx.lineWidth = 2 / globalScale;
                ctx.stroke();
              }
              const fontSize = Math.max(11 / globalScale, 2);
              ctx.font = `${fontSize}px 'Pretendard','Malgun Gothic',sans-serif`;
              ctx.textAlign = "center";
              ctx.textBaseline = "top";
              ctx.fillStyle = "#191f28";
              ctx.fillText(label, node.x, node.y + r + 1);
            }}
            nodePointerAreaPaint={(node: any, color, ctx) => {
              if (node.x == null || node.y == null) return;
              ctx.fillStyle = color;
              ctx.beginPath();
              ctx.arc(node.x, node.y, 9, 0, 2 * Math.PI);
              ctx.fill();
            }}
            linkCanvasObjectMode={() => "after"}
            linkCanvasObject={(link: any, ctx, globalScale) => {
              const s = link.source;
              const t = link.target;
              if (typeof s !== "object" || typeof t !== "object") return;
              if (s.x == null || t.x == null) return;
              const mx = (s.x + t.x) / 2;
              const my = (s.y + t.y) / 2;
              const fontSize = Math.max(9 / globalScale, 1.5);
              ctx.font = `${fontSize}px 'Pretendard','Malgun Gothic',sans-serif`;
              ctx.fillStyle = "#8b95a1";
              ctx.textAlign = "center";
              ctx.textBaseline = "middle";
              ctx.fillText(link.type, mx, my);
            }}
          />

          {selected && (
            <div className="node-panel">
              <div className="row between">
                <b>{selected.name}</b>
                <button className="mini ghost" onClick={() => setSelected(null)}>
                  ✕
                </button>
              </div>
              {selected.types.length > 0 && (
                <div style={{ marginTop: 6 }}>
                  {selected.types.map((t) => (
                    <span key={t} className="badge" style={{ marginLeft: 0, marginRight: 4 }}>
                      {t}
                    </span>
                  ))}
                </div>
              )}
              {formatQuantity(selected) && (
                <div style={{ marginTop: 8 }}>
                  <span className="badge">값</span>{" "}
                  <span className="mono">{formatQuantity(selected)}</span>
                </div>
              )}
              {selected.description && (
                <div className="muted" style={{ marginTop: 8 }}>{selected.description}</div>
              )}
            </div>
          )}

          {legendTypes.length > 0 && (
            <div className="legend">
              {legendTypes.map((t) => (
                <span className="dot" key={t}>
                  <i style={{ background: colorFor(t) }} />
                  {t}
                </span>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
