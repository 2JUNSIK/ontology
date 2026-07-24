import { useState } from "react";
import type { Project } from "../types";

interface Props {
  projects: Project[];
  loading: boolean;
  creating: boolean;
  deletingId: string | null;
  onSelect: (p: Project) => void;
  onCreate: (name: string, description: string) => void;
  onDelete: (p: Project) => void;
}

export default function ProjectList({
  projects,
  loading,
  creating,
  deletingId,
  onSelect,
  onCreate,
  onDelete,
}: Props) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  function submit() {
    if (!name.trim()) return;
    onCreate(name.trim(), description.trim());
    setName("");
    setDescription("");
  }

  return (
    <div>
      <section className="hero">
        <span className="hero-eyebrow">Knowledge Graph Builder</span>
        <h1 className="hero-title">
          지식을 문장으로 입력하면,
          <br />
          그래프가 됩니다.
        </h1>
        <p className="hero-sub">
          온톨로지를 몰라도 괜찮아요. 아는 것을 한 문장씩 적으면 Claude가 노드와 관계를
          찾아 프로젝트 지식그래프에 차곡차곡 쌓아 드립니다.
        </p>
      </section>

      <div className="panel">
        <h2 className="section-title">새 프로젝트</h2>
        <p className="section-desc">주제별로 독립된 지식그래프를 만들어 관리하세요.</p>
        <div className="row" style={{ gap: 12, flexWrap: "wrap", marginTop: 18 }}>
          <input
            style={{ minWidth: 220 }}
            placeholder="프로젝트 이름 (예: 녹조 대응)"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
          />
          <input
            style={{ flex: 1, minWidth: 240 }}
            placeholder="설명 (선택)"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
          />
          <button className="primary" onClick={submit} disabled={creating || !name.trim()}>
            {creating ? "생성 중…" : "＋ 프로젝트 만들기"}
          </button>
        </div>
      </div>

      <div className="panel" style={{ marginTop: 20 }}>
        <h2 className="section-title">내 프로젝트</h2>
        <p className="section-desc">
          {loading
            ? "불러오는 중…"
            : `${projects.length}개의 프로젝트`}
        </p>
        <div style={{ marginTop: 18 }}>
          {!loading && projects.length === 0 && (
            <div className="muted">아직 프로젝트가 없습니다. 위에서 하나 만들어 보세요.</div>
          )}
          {projects.map((p) => (
            <div className="card project-card" key={p.id}>
              <div className="row between">
                <div>
                  <h4>{p.name}</h4>
                  {p.description && <div className="muted">{p.description}</div>}
                </div>
                <div className="row" style={{ gap: 8 }}>
                  <button
                    className="mini primary"
                    onClick={() => onSelect(p)}
                    disabled={deletingId === p.id}
                  >
                    열기 →
                  </button>
                  <button
                    className="mini danger"
                    disabled={deletingId !== null}
                    onClick={() => {
                      if (
                        window.confirm(
                          `프로젝트 '${p.name}'와 그 지식그래프를 삭제할까요? 되돌릴 수 없습니다.`,
                        )
                      )
                        onDelete(p);
                    }}
                  >
                    {deletingId === p.id ? "삭제 중…" : "삭제"}
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
