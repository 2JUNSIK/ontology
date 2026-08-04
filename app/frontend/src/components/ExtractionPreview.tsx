import { useEffect, useState } from "react";
import type { Extraction } from "../types";

// datalist 힌트용 표준 어휘(백엔드 seed_ontology.STANDARD_ENTITY_TYPES/STANDARD_RELATION_TYPES와
// 느슨하게 동기화). 자유입력을 허용하되 표준 선택을 유도할 뿐이라 완벽 일치는 불필요하다.
const STD_ENTITY_TYPES = [
  "저수지", "하천", "댐", "측정소", "시설", "수질항목", "수문항목", "측정값",
  "생물", "현상", "제도", "경보단계", "오염원", "대응조치", "기관", "지표",
];
const STD_RELATION_TYPES = [
  "원인", "단계", "기준지표", "유입", "관할", "측정", "위치", "대응", "포함", "발령",
];

interface Props {
  extraction: Extraction;
  warnings?: string[];
  onCancel: () => void;
  onConfirm: (edited: Extraction) => void;
  ingesting: boolean;
}

interface EntEdit {
  name: string;
  type: string;
  description: string;
  value?: number | null;
  unit?: string;
  comparator?: string;
  observed_at?: string;
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
  warnings = [],
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
        .map(({ name, type, description, value, unit, comparator, observed_at }) => ({
          name,
          type,
          description,
          value,
          unit,
          comparator,
          observed_at,
        })),
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
      {/* datalist: 타입 입력 자동완성용 표준 어휘(자유입력 허용) */}
      <datalist id="std-entity-types">
        {STD_ENTITY_TYPES.map((t) => (
          <option key={t} value={t} />
        ))}
      </datalist>
      <datalist id="std-relation-types">
        {STD_RELATION_TYPES.map((t) => (
          <option key={t} value={t} />
        ))}
      </datalist>

      <div className="row between">
        <h2 className="section-title">추출 미리보기</h2>
        <span className="meta-pill">
          노드 {chosenEnts}/{ents.length} · 관계 {chosenRels}/{rels.length}
        </span>
      </div>

      {warnings.length > 0 && (
        <div className="notice" style={{ margin: "8px 0 0", borderColor: "var(--warning)" }}>
          <b>⚠ 관계 타입 검증 경고 {warnings.length}건</b>
          <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>
            {warnings.map((w, i) => (
              <li key={i} className="muted">{w}</li>
            ))}
          </ul>
          <div className="muted" style={{ marginTop: 6 }}>
            참고용입니다. 관계는 자동 삭제되지 않으니, 타입이 잘못됐으면 고치고 맞으면 그대로 두세요.
          </div>
        </div>
      )}

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
              list="std-entity-types"
              onChange={(ev) => updateEnt(i, { type: ev.target.value })}
            />
          </label>
          <input
            className="inp full"
            value={e.description}
            placeholder="설명(선택)"
            onChange={(ev) => updateEnt(i, { description: ev.target.value })}
          />
          <div className="row" style={{ gap: 6, marginTop: 6, alignItems: "center", flexWrap: "wrap" }}>
            <span className="muted" style={{ fontSize: 12 }}>정량(선택):</span>
            <select
              className="inp"
              value={e.comparator ?? ""}
              style={{ width: 72 }}
              onChange={(ev) => updateEnt(i, { comparator: ev.target.value })}
            >
              <option value="">연산자</option>
              <option value=">=">≥</option>
              <option value="<=">≤</option>
              <option value=">">&gt;</option>
              <option value="<">&lt;</option>
              <option value="=">=</option>
            </select>
            <input
              className="inp"
              type="number"
              value={e.value ?? ""}
              placeholder="값"
              style={{ width: 110 }}
              onChange={(ev) => {
                const raw = ev.target.value;
                const num = Number(raw);
                updateEnt(i, { value: raw === "" || Number.isNaN(num) ? null : num });
              }}
            />
            <input
              className="inp"
              value={e.unit ?? ""}
              placeholder="단위(예: cells/mL)"
              style={{ width: 140 }}
              onChange={(ev) => updateEnt(i, { unit: ev.target.value })}
            />
          </div>
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
                list="std-relation-types"
                onChange={(ev) => updateRel(i, { type: ev.target.value })}
              />
              <span className="muted">]-&gt;</span>
              <span className="mono">({r.target})</span>
            </label>
            {blocked && (
              <div className="muted" style={{ color: "var(--warning-ink)", marginTop: 4 }}>
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
