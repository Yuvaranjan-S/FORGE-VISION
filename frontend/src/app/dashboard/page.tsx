"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { getCases, createCase, updateCase, loadStoredAuth, getUser, type Case } from "@/lib/api";
import styles from "./dashboard.module.css";

const STATUS_BADGE: Record<string, string> = {
  active: "badge-intact", closed: "badge-mismatch", archived: "badge-pending",
};

import Navbar from "@/components/Navbar";

export default function Dashboard() {
  const router = useRouter();
  const [cases, setCases] = useState<Case[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [statusUpdating, setStatusUpdating] = useState<string | null>(null);
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);

  useEffect(() => {
    loadStoredAuth();
    if (!getUser()) { router.replace("/"); return; }
    fetchCases();
  }, [router]);

  function showToast(msg: string, ok = true) {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3500);
  }

  async function fetchCases() {
    setLoading(true);
    try { setCases(await getCases()); }
    catch { setError("Failed to load cases — ensure backend is running"); }
    finally { setLoading(false); }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    try {
      const c = await createCase(newTitle, newDesc) as { case_id: string };
      setShowCreate(false); setNewTitle(""); setNewDesc("");
      router.push(`/case/${c.case_id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create case");
    } finally { setCreating(false); }
  }

  async function handleStatusChange(caseId: string, status: string, e: React.MouseEvent) {
    e.stopPropagation();
    setStatusUpdating(caseId);
    try {
      await updateCase(caseId, { status });
      showToast(`Case ${caseId} marked as ${status.toUpperCase()}`);
      await fetchCases();
    } catch (err: unknown) {
      showToast(err instanceof Error ? err.message : "Update failed", false);
    } finally { setStatusUpdating(null); }
  }

  return (
    <div className={styles.root}>
      <Navbar />

      {toast && (
        <div className={`${styles.toast} ${toast.ok ? styles.toastOk : styles.toastErr}`}>
          {toast.msg}
        </div>
      )}

      <div className={styles.body}>
        {/* Sidebar stats */}
        <aside className={styles.sidebar}>
          <div className={styles.sideSection}>
            <div className="section-header"><div className="section-title">SYSTEM STATUS</div></div>
            <div className={styles.statRow}><span>Cases Open</span><span className="text-amber">{cases.filter(c=>c.status==="active").length}</span></div>
            <div className={styles.statRow}><span>Total Evidence</span><span className="text-cyan">{cases.reduce((s,c)=>s+(c.evidence_count||0),0)}</span></div>
            <div className={styles.statRow}><span>AI Findings</span><span className="text-purple">{cases.reduce((s,c)=>s+(c.ai_finding_count||0),0)}</span></div>
          </div>
          <div className={styles.sideSection}>
            <div className="section-header"><div className="section-title">CAPABILITIES</div></div>
            {[
              ["✓", "Triple Hash (MD5+SHA256+SHA3)", "green"],
              ["✓", "Hash-Chained Custody Ledger", "green"],
              ["✓", "ELA Tamper Detection", "green"],
              ["✓", "Frame Dup Detection", "green"],
              ["✓", "Scene Change Analysis", "green"],
              ["✓", "Motion Heatmap", "green"],
              ["◐", "Object/Vehicle Detection", "amber"],
              ["◐", "Cross-Camera ReID", "amber"],
              ["◐", "Full Disk Carving", "amber"],
              ["◐", "Hikvision/Dahua Parsers", "amber"],
            ].map(([icon, label, color]) => (
              <div key={label} className={styles.capRow}>
                <span className={`text-${color}`}>{icon}</span>
                <span className={styles.capLabel}>{label}</span>
              </div>
            ))}
            <div className={styles.capLegend}>
              <span className="text-green">✓ Real</span>
              <span className="text-amber">◐ Simulated (labeled)</span>
            </div>
          </div>
        </aside>

        {/* Main content */}
        <main className={styles.main}>
          <div className={styles.mainHeader}>
            <div>
              <h1 className={styles.mainTitle}>INVESTIGATION CASES</h1>
              <div className={styles.mainSub}>{cases.length} case(s) in system</div>
            </div>
            <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
              + NEW CASE
            </button>
          </div>

          {error && <div className={styles.errorBanner}>⚠ {error}</div>}

          {/* Create case modal */}
          {showCreate && (
            <div className={styles.modal}>
              <div className={styles.modalCard}>
                <div className={styles.modalHeader}>
                  <span>CREATE NEW INVESTIGATION CASE</span>
                  <button className="btn btn-ghost btn-sm" onClick={() => setShowCreate(false)}>✕</button>
                </div>
                <form onSubmit={handleCreate} className={styles.modalForm}>
                  <div className="flex-col">
                    <label className="field-label">Case Title</label>
                    <input className="input" value={newTitle} onChange={e=>setNewTitle(e.target.value)}
                           placeholder="e.g. Operation Kite — Bank Robbery 15-Mar-2024" required />
                  </div>
                  <div className="flex-col">
                    <label className="field-label">Description</label>
                    <textarea className="input" value={newDesc} onChange={e=>setNewDesc(e.target.value)}
                              placeholder="Brief case description..." rows={3} />
                  </div>
                  <div className="flex-row" style={{justifyContent:"flex-end"}}>
                    <button type="button" className="btn btn-ghost" onClick={() => setShowCreate(false)}>Cancel</button>
                    <button type="submit" className="btn btn-primary" disabled={creating}>
                      {creating ? <><div className="spinner"/>Creating...</> : "Create Case →"}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}

          {/* Cases grid */}
          {loading ? (
            <div className={styles.loadingCenter}><div className="spinner" /><span>Loading cases...</span></div>
          ) : cases.length === 0 ? (
            <div className={styles.emptyState}>
              <div className={styles.emptyIcon}>🗂</div>
              <div className={styles.emptyTitle}>No cases yet</div>
              <div className={styles.emptySub}>Create a new investigation case or seed demo data</div>
              <button className="btn btn-primary" onClick={() => setShowCreate(true)}>+ Create First Case</button>
            </div>
          ) : (
            <div className={styles.caseGrid}>
              {cases.map(c => (
                <div key={c.id} className={styles.caseCard} onClick={() => router.push(`/case/${c.id}`)}>
                  <div className={styles.caseCardTop}>
                    <span className={`badge ${STATUS_BADGE[c.status] || "badge-pending"}`}>{c.status.toUpperCase()}</span>
                    <span className="mono-sm text-muted">{c.id}</span>
                  </div>
                  <div className={styles.caseTitle}>{c.title}</div>
                  {c.description && <div className={styles.caseDesc}>{c.description}</div>}
                  <div className={styles.caseMeta}>
                    <div className={styles.caseMetaItem}>
                      <span className="text-muted">Evidence</span>
                      <span className="text-amber font-bold">{c.evidence_count || 0}</span>
                    </div>
                    <div className={styles.caseMetaItem}>
                      <span className="text-muted">AI Findings</span>
                      <span className="text-purple font-bold">{c.ai_finding_count || 0}</span>
                    </div>
                    <div className={styles.caseMetaItem}>
                      <span className="text-muted">Custody Entries</span>
                      <span className="text-cyan font-bold">{c.custody_entry_count || 0}</span>
                    </div>
                  </div>
                  <div className={styles.caseFooter}>
                    <span className="text-muted text-xs">{new Date(c.created_at).toLocaleDateString("en-IN", {day:"2-digit",month:"short",year:"numeric"})}</span>
                    <span className={styles.openBtn}>OPEN →</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
