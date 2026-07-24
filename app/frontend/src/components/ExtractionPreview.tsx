import { useEffect, useState } from "react";
import type { Extraction } from "../types";

interface Props {
  extraction: Extraction;
  onCancel: () => void;
  onConfirm: (edited: Extraction) => void;
  ingesting: boolean;
}

interface EntEdit {
  name: string;
  type: string;
  description: string;
  include: boolean;
}
interface RelEdit {
  source: string;
  target: string;
  type: string;
  description: string;
  include: boolean;
}

export default function ExtractionPreview({
  extraction,
  onCancel,
  onConfirm,
  ingesting,
}: Props) {
  const [ents, setEnts] = useState<EntEdit[]>([]);
  const [rels, setRels] = useState<RelEdit[]>([]);

  // 새 추출 결과가 오면 편집 상태를 초기화(전부 포함).
  useEffect(() => {
    setEnts(extraction.entities.map((e) => ({ ...e, include: true })));
    setRels(extraction.relations.map((r) => ({ ...r, include: true })));
  }, [extraction]);

  function updateEnt(i: number, patch: Partial<EntEdit>) {
    setEnts((prev) => prev.map((e, idx) => (idx === i ? { ...e, ...patch } : e)));
  }
  function updateRel(i: number, patch: Partial<RelEdit>) {
    setRels((prev) => prev.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  }

  // 추출로 제시된 엔티티 이름 집합(관계 끝점이 '제외된 노드'인지 판별용).
  const extractedNames = new Set(extraction.entities.map((e) => e.name));
  const includedNames = new Set(ents.filter((e) => e.include).map((e) => e.name));

  // 관계가 '추출됐지만 사용자가 제외한' 엔티티를 참조하면 차단(제외한 노드가 유령으로
  // 부활하는 조용한 혼란 방지). 애초에 엔티티로 제시되지 않은 이름(순수 stub)은 허용.
  function relBlocked(r: RelEdit): boolean {
    return [r.source, r.target].some(
      (n) => extractedNames.has(n) && !includedNames.has(n),
    );
  }

  function confirm() {
    const edited: Extraction = {
      entities: ents
        .filter((e) => e.include)
        .map(({ name, type, description }) => ({ name, type, description })),
      relations: rels
        .filter((r) => r.include && !relBlocked(r))
        .map(({ source, target, type, description }) => ({ source, target, type, description })),
      summary: extraction.summary,
    };
    onConfirm(edited);
  }

  const chosenEnts = ents.filter((e) => e.include).length;
  const chosenRels = rels.filter((r) => r.include && !relBlocked(r)).length;
  const blockedCount = rels.filter((r) => r.include && relBlocked(r)).length;

  return (
    <div className="panel" style={{ marginTop: 16 }}>
      <div className="row between">
        <h2 className="section-title">추출 미리보기</h2>
        <span className="meta-pill">
          노드 {chosenEnts}/{ents.length} · 관계 {chosenRels}/{rels.length}
        </span>
      </div>
      {extraction.summary && (
        <div className="muted" style={{ margin: "8px 0 12px" }}>{extraction.summary}</div>
      )}

      <h4 style={{ margin: "16px 0 8px" }}>노드(엔티티)</h4>
      {ents.length === 0 && <div className="muted">추출된 노드가 없습니다.</div>}
      {ents.map((e, i) => (
        <div className={"card prev" + (e.include ? "" : " excluded")} key={`e${i}`}>
          <label className="row" style={{ gap: 8, alignItems: "center" }}>
            <input
              type="checkbox"
              checked={e.include}
              onChange={(ev) => updateEnt(i, { include: ev.target.checked })}
            />
            <b>{e.name}</b>
            <span className="muted">:</span>
            <input
              className="inp"
              value={e.type}
              placeholder="타입(예: 현상)"
              onChange={(ev) => updateEnt(i, { type: ev.target.value })}
            />
          </label>
          <input
            className="inp full"
            value={e.description}
            placeholder="설명(선택)"
            onChange={(ev) => updateEnt(i, { description: ev.target.value })}
          />
        </div>
      ))}

      <h4 style={{ margin: "20px 0 8px" }}>관계</h4>
      {rels.length === 0 && <div className="muted">추출된 관계가 없습니다.</div>}
      {blockedCount > 0 && (
        <div className="notice" style={{ marginBottom: 8 }}>
          제외한 노드를 참조하는 관계 {blockedCount}개는 추가되지 않습니다(그 노드를 다시
          포함하면 관계도 살아납니다).
        </div>
      )}
      {rels.map((r, i) => {
        const blocked = relBlocked(r);
        const active = r.include && !blocked;
        return (
          <div className={"card prev" + (active ? "" : " excluded")} key={`r${i}`}>
            <label className="row" style={{ gap: 8, alignItems: "center", flexWrap: "wrap" }}>
              <input
                type="checkbox"
                checked={active}
                disabled={blocked}
                onChange={(ev) => updateRel(i, { include: ev.target.checked })}
              />
              <span className="mono">({r.source})</span>
              <span className="muted">-[</span>
              <input
                className="inp"
                value={r.type}
                placeholder="관계타입"
                onChange={(ev) => updateRel(i, { type: ev.target.value })}
              />
              <span className="muted">]-&gt;</span>
              <span className="mono">({r.target})</span>
            </label>
            {blocked && (
              <div className="muted" style={{ color: "var(--warning)", marginTop: 4 }}>
                제외된 노드를 참조 — 이 관계는 추가되지 않습니다.
              </div>
            )}
          </div>
        );
      })}

      <div className="row between" style={{ marginTop: 12 }}>
        <button className="ghost" onClick={onCancel} disabled={ingesting}>
          취소
        </button>
        <button
          className="primary"
          onClick={confirm}
          disabled={ingesting || chosenEnts + chosenRels === 0}
        >
          {ingesting ? "그래프에 반영 중…" : `그래프에 추가 (노드 ${chosenEnts} · 관계 ${chosenRels})`}
        </button>
      </div>
    </div>
  );
}
