import { useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import type { GraphData } from "../types";
import { formatQuantity } from "./KnowledgeInventory";

interface Props {
  data: GraphData;
}

// 라이트 배경에서 대비가 좋은 팔레트(toss 톤). 타입이 12개를 넘으면 색이 재사용된다(MVP 허용).
const PALETTE = [
  "#3182f6", "#12b886", "#f59f00", "#f04452", "#7c3aed",
  "#e64980", "#0ca678", "#e8590c", "#4263eb", "#c2255c",
  "#1098ad", "#9c36b5",
];
const UNTYPED = "#adb5bd";
const QUANTITY_RING = "#f59f00"; // 정량값(N10) 있는 노드 강조색(amber)

// degree(연결 수)에 비례한 노드 반지름 — 허브 노드를 크게. sqrt로 완만하게, 상한 고정.
const MIN_R = 4;
const MAX_R = 13;
function radiusForDegree(deg: number): number {
  return Math.min(MAX_R, MIN_R + Math.sqrt(deg) * 2.4);
}

// 링크 끝점이 문자열 id일 수도(원본) 객체일 수도(force-graph 변형 후) 있다.
function endpointId(v: unknown): string {
  if (v == null) return "";
  if (typeof v === "object") return String((v as { id: unknown }).id);
  return String(v);
}

export default function GraphView({ data }: Props) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [ready, setReady] = useState(false); // 최초 시뮬레이션 정지 전엔 "전체 보기"를 막는다(빈 좌표 fit 방지).
  const wrapRef = useRef<HTMLDivElement>(null);
  const fgRef = useRef<any>(null);
  const didFitRef = useRef(false); // 새 노드가 들어온 뒤 최초 1회만 자동 맞춤
  const prevIdsRef = useRef<Set<string>>(new Set());
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

  // 노드별 degree(연결 수) → 반지름. 원본 data.links(문자열 끝점)에서 계산.
  const degreeFor = useMemo(() => {
    const deg = new Map<string, number>();
    for (const l of data.links) {
      const s = endpointId(l.source);
      const t = endpointId(l.target);
      if (s) deg.set(s, (deg.get(s) ?? 0) + 1);
      if (t && t !== s) deg.set(t, (deg.get(t) ?? 0) + 1);
    }
    return (id: string) => radiusForDegree(deg.get(id) ?? 0);
  }, [data]);

  // 정량값(N10)을 가진 노드가 하나라도 있으면 범례에 안내 칩을 노출.
  const hasAnyValue = useMemo(() => data.nodes.some((n) => formatQuantity(n)), [data]);

  // 선택 노드는 id만 저장하고 라이브 데이터에서 조회 → 값/설명이 갱신되면 패널도 최신 반영,
  // 노드가 사라지면 자동으로 null(별도 cleanup 불필요).
  const selected = useMemo(
    () => (selectedId ? data.nodes.find((n) => n.id === selectedId) ?? null : null),
    [data, selectedId],
  );

  // 검색어와 이름이 부분일치하는 노드 id 집합(검색 중이 아니면 null).
  const matchIds = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return null;
    return new Set(
      data.nodes.filter((n) => n.name.toLowerCase().includes(q)).map((n) => n.id),
    );
  }, [search, data]);
  const matchCount = matchIds?.size ?? 0;

  // react-force-graph는 데이터를 변형하므로 복제해서 넘긴다.
  const graphData = useMemo(
    () => ({
      nodes: data.nodes.map((n) => ({ ...n })),
      links: data.links.map((l) => ({ ...l })),
    }),
    [data],
  );

  // 새 노드가 등장했을 때(최초 로드 / 추가 / 새 질의 결과)만 자동 맞춤을 예약한다.
  // 순수 삭제(노드 집합이 줄기만 함)에는 재맞춤하지 않아 사용자가 잡은 줌/뷰를 보존한다(S2).
  useEffect(() => {
    const prev = prevIdsRef.current;
    const hasNew = data.nodes.some((n) => !prev.has(n.id));
    prevIdsRef.current = new Set(data.nodes.map((n) => n.id));
    if (hasNew) didFitRef.current = false;
  }, [data]);

  const searching = matchIds !== null;

  return (
    <div className="graph-wrap" ref={wrapRef}>
      {graphData.nodes.length === 0 ? (
        <div className="center-msg">
          <div>아직 지식이 없습니다.</div>
          <div className="muted">위쪽 “지식 입력”에서 문장을 넣고 “추출 → 그래프에 추가”를 해보세요.</div>
        </div>
      ) : (
        <>
          <div className="graph-toolbar">
            <span className="graph-toolbar-icon" aria-hidden>🔍</span>
            <input
              placeholder="노드 검색…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="노드 이름 검색"
            />
            {searching && <span className="graph-search-count">{matchCount}개</span>}
            {search && (
              <button className="mini ghost" onClick={() => setSearch("")} aria-label="검색 지우기">
                ✕
              </button>
            )}
            <span className="graph-toolbar-sep" />
            <button
              className="mini ghost"
              onClick={() => fgRef.current?.zoomToFit(400, 60)}
              disabled={!ready}
              title="화면에 전체 그래프 맞추기"
            >
              전체 보기
            </button>
            <button
              className="mini ghost"
              onClick={() => fgRef.current?.d3ReheatSimulation()}
              title="노드를 다시 정렬"
            >
              재정렬
            </button>
          </div>

          <ForceGraph2D
            ref={fgRef}
            width={size.w}
            height={size.h}
            graphData={graphData}
            backgroundColor="#f9fafb"
            linkDirectionalArrowLength={4}
            linkDirectionalArrowRelPos={1}
            linkWidth={1.2}
            onNodeClick={(node: any) => setSelectedId(node.id as string)}
            onEngineStop={() => {
              setReady(true);
              if (!didFitRef.current) {
                fgRef.current?.zoomToFit(400, 60);
                didFitRef.current = true;
              }
            }}
            // linkColor / nodeCanvasObject / linkCanvasObject는 인라인으로 둔다.
            // 콜백 identity가 매 렌더 바뀌어야 정적(엔진 정지) 그래프에서도 재드로우가 트리거됨 → useCallback 금지.
            linkColor={(link: any) => {
              if (!searching) return "rgba(139,149,161,0.55)";
              const on =
                matchIds!.has(endpointId(link.source)) || matchIds!.has(endpointId(link.target));
              return on ? "rgba(139,149,161,0.55)" : "rgba(139,149,161,0.12)";
            }}
            nodeCanvasObject={(node: any, ctx, globalScale) => {
              if (node.x == null || node.y == null) return; // 첫 틱 좌표 미초기화 가드
              const label: string = node.name;
              const r = degreeFor(node.id);
              const isMatch = !searching || matchIds!.has(node.id);
              const dim = searching && !isMatch;

              ctx.globalAlpha = dim ? 0.18 : 1;

              // 정량값 노드: 바깥에 amber 링(패널을 안 열어도 값 있음을 인지).
              if (formatQuantity(node)) {
                ctx.beginPath();
                ctx.arc(node.x, node.y, r + 2.5, 0, 2 * Math.PI);
                ctx.strokeStyle = QUANTITY_RING;
                ctx.lineWidth = 1.6 / globalScale;
                ctx.stroke();
              }

              ctx.beginPath();
              ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
              ctx.fillStyle = colorFor(node.type);
              ctx.fill();

              // 선택 노드 또는 검색 일치 노드에 강조 테두리.
              if (selectedId === node.id) {
                ctx.strokeStyle = "#191f28";
                ctx.lineWidth = 2 / globalScale;
                ctx.stroke();
              } else if (searching && isMatch) {
                ctx.strokeStyle = "#191f28";
                ctx.lineWidth = 1.5 / globalScale;
                ctx.stroke();
              }

              const fontSize = Math.max(11 / globalScale, 2);
              ctx.font = `${fontSize}px 'Pretendard','Malgun Gothic',sans-serif`;
              ctx.textAlign = "center";
              ctx.textBaseline = "top";
              ctx.fillStyle = "#191f28";
              ctx.fillText(label, node.x, node.y + r + 1);

              ctx.globalAlpha = 1;
            }}
            nodePointerAreaPaint={(node: any, color, ctx) => {
              if (node.x == null || node.y == null) return;
              ctx.fillStyle = color;
              ctx.beginPath();
              ctx.arc(node.x, node.y, degreeFor(node.id) + 3, 0, 2 * Math.PI);
              ctx.fill();
            }}
            linkCanvasObjectMode={() => "after"}
            linkCanvasObject={(link: any, ctx, globalScale) => {
              const s = link.source;
              const t = link.target;
              if (typeof s !== "object" || typeof t !== "object") return;
              if (s.x == null || t.x == null) return;
              const dim = searching && !(matchIds!.has(s.id) || matchIds!.has(t.id));
              const mx = (s.x + t.x) / 2;
              const my = (s.y + t.y) / 2;
              const fontSize = Math.max(9 / globalScale, 1.5);
              ctx.globalAlpha = dim ? 0.18 : 1;
              ctx.font = `${fontSize}px 'Pretendard','Malgun Gothic',sans-serif`;
              ctx.fillStyle = "#8b95a1";
              ctx.textAlign = "center";
              ctx.textBaseline = "middle";
              ctx.fillText(link.type, mx, my);
              ctx.globalAlpha = 1;
            }}
          />

          {selected && (
            <div className="node-panel">
              <div className="row between">
                <b>{selected.name}</b>
                <button className="mini ghost" onClick={() => setSelectedId(null)}>
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

          {(legendTypes.length > 0 || hasAnyValue) && (
            <div className="legend">
              {legendTypes.map((t) => (
                <span className="dot" key={t}>
                  <i style={{ background: colorFor(t) }} />
                  {t}
                </span>
              ))}
              {hasAnyValue && (
                <span className="dot">
                  <i style={{ background: "transparent", border: `2px solid ${QUANTITY_RING}` }} />
                  정량값
                </span>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
