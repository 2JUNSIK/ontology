import { useRef, useState } from "react";
import type { Project } from "../types";
import Skeleton from "./ui/Skeleton";

interface Props {
  projects: Project[];
  loading: boolean;
  creating: boolean;
  deletingId: string | null;
  onSelect: (p: Project) => void;
  onCreate: (name: string, description: string) => void;
  onDelete: (p: Project) => void; // 확인 모달은 App(useConfirm)에서 처리
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
  const nameRef = useRef<HTMLInputElement>(null);

  function submit() {
    if (!name.trim()) return;
    onCreate(name.trim(), description.trim());
    setName("");
    setDescription("");
  }

  // 빈 상태 CTA: 생성 폼의 이름 입력으로 스크롤·포커스.
  function focusNewProject() {
    nameRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    nameRef.current?.focus();
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
        <div className="row stack-mobile" style={{ gap: 12, flexWrap: "wrap", marginTop: 18 }}>
          <input
            ref={nameRef}
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
            {creating ? <><span className="spinner" aria-hidden />생성 중…</> : "＋ 프로젝트 만들기"}
          </button>
        </div>
      </div>

      <div className="panel" style={{ marginTop: 20 }}>
        <h2 className="section-title">내 프로젝트</h2>
        <p className="section-desc">
          {loading ? "불러오는 중…" : `${projects.length}개의 프로젝트`}
        </p>
        <div style={{ marginTop: 18 }}>
          {loading &&
            [0, 1, 2].map((i) => (
              <div className="skeleton-card" key={i}>
                <Skeleton width="42%" height={18} />
                <Skeleton width="66%" height={13} />
              </div>
            ))}

          {!loading && projects.length === 0 && (
            <div className="empty-state">
              <div className="empty-icon" aria-hidden>🗂️</div>
              <div className="empty-title">아직 프로젝트가 없습니다</div>
              <div className="muted">첫 프로젝트를 만들어 지식그래프를 시작해 보세요.</div>
              <button className="primary" style={{ marginTop: 4 }} onClick={focusNewProject}>
                ＋ 첫 프로젝트 만들기
              </button>
            </div>
          )}

          {!loading &&
            projects.map((p) => (
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
                      onClick={() => onDelete(p)}
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
