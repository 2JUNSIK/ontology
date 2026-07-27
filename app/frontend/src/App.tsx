import { useEffect, useState } from "react";
import { createProject, deleteProject, errMessage, listProjects } from "./api";
import ProjectList from "./components/ProjectList";
import Workspace from "./components/Workspace";
import type { Project } from "./types";

export default function App() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [current, setCurrent] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      setProjects(await listProjects());
    } catch (e) {
      setError(errMessage(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleCreate(name: string, description: string) {
    setCreating(true);
    setError(null);
    try {
      const p = await createProject(name, description);
      await refresh();
      setCurrent(p); // 만들고 바로 작업공간 진입
    } catch (e) {
      setError(errMessage(e));
    } finally {
      setCreating(false);
    }
  }

  async function handleDelete(p: Project) {
    if (deletingId) return; // 진행 중 이중 클릭 방지
    setError(null);
    setDeletingId(p.id);
    try {
      await deleteProject(p.id);
      if (current?.id === p.id) setCurrent(null);
      await refresh();
    } catch (e) {
      setError(errMessage(e));
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar-inner">
          <div className="brand">
            <span className="brand-mark">🌊</span>
            <div>
              <div className="brand-title">지식그래프 빌더</div>
            </div>
          </div>
        </div>
      </header>

      <main className="content">
        {error && <div className="error">{error}</div>}

        {current ? (
          <Workspace project={current} onBack={() => { setCurrent(null); refresh(); }} />
        ) : (
          <ProjectList
            projects={projects}
            loading={loading}
            creating={creating}
            deletingId={deletingId}
            onSelect={setCurrent}
            onCreate={handleCreate}
            onDelete={handleDelete}
          />
        )}
      </main>
    </div>
  );
}
