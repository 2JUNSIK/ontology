import { useEffect, useState } from "react";
import { createProject, deleteProject, errMessage, listProjects } from "./api";
import ProjectList from "./components/ProjectList";
import Workspace from "./components/Workspace";
import ThemeToggle from "./components/ThemeToggle";
import { useToast } from "./components/ui/Toast";
import { useConfirm } from "./components/ui/ConfirmDialog";
import type { Project } from "./types";

export default function App() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [current, setCurrent] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const toast = useToast();
  const confirm = useConfirm();

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
      toast.success(`프로젝트 ‘${p.name}’를 만들었습니다.`);
    } catch (e) {
      const msg = errMessage(e);
      setError(msg);
      toast.error(msg);
    } finally {
      setCreating(false);
    }
  }

  async function handleDelete(p: Project) {
    if (deletingId) return; // 진행 중 이중 클릭 방지
    const ok = await confirm({
      title: "프로젝트 삭제",
      body: `‘${p.name}’와 그 지식그래프를 삭제할까요?\n되돌릴 수 없습니다.`,
      confirmText: "삭제",
      danger: true,
    });
    if (!ok) return;
    setError(null);
    setDeletingId(p.id);
    try {
      await deleteProject(p.id);
      if (current?.id === p.id) setCurrent(null);
      await refresh();
      toast.success(`프로젝트 ‘${p.name}’를 삭제했습니다.`);
    } catch (e) {
      const msg = errMessage(e);
      setError(msg);
      toast.error(msg);
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
          <ThemeToggle />
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
