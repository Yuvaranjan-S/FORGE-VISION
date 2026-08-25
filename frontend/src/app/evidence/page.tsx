"use client";
import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import {
  listAllEvidence, getCases, getDatasets, verifyEvidence,
  runAIDetection, loadStoredAuth, getUser, getToken, API_BASE,
  type Evidence, type Case, type Dataset,
} from "@/lib/api";
import styles from "./evidence.module.css";

const SOURCE_FILTERS = [
  { id: "ALL", label: "All Sources" },
  { id: "PUBLIC_RESEARCH_DATASET", label: "Public Research" },
  { id: "AUTHORIZED_DVR_EXPORT", label: "Authorized DVR" },
  { id: "VENDOR_SAMPLE", label: "Vendor Sample" },
  { id: "SYNTHETIC_DEMO", label: "Synthetic Demo" },
];

const VENDOR_FILTERS = [
  { id: "ALL", label: "All Vendors" },
  { id: "Unknown", label: "Unknown" },
  { id: "Hikvision", label: "Hikvision" },
  { id: "Dahua", label: "Dahua" },
  { id: "CP Plus", label: "CP Plus" },
];

const INTEGRITY_FILTERS = [
  { id: "ALL", label: "All Integrity" },
  { id: "verified", label: "✓ Verified" },
  { id: "mismatch", label: "✕ Mismatch" },
  { id: "unverified", label: "○ Unverified" },
];

function formatDuration(secs: number): string {
  if (!secs || isNaN(secs)) return "—";
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

function formatSize(bytes: number): string {
  if (!bytes) return "—";
  if (bytes > 1024 * 1024 * 1024) return `${(bytes / (1024 ** 3)).toFixed(1)} GB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function CamEvidencePage() {
  const router = useRouter();

  const [evidenceList, setEvidenceList] = useState<Evidence[]>([]);
  const [cases, setCases] = useState<Case[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [sourceFilter, setSourceFilter] = useState("ALL");
  const [vendorFilter, setVendorFilter] = useState("ALL");
  const [integrityFilter, setIntegrityFilter] = useState("ALL");
  const [caseFilter, setCaseFilter] = useState("ALL");
  const [datasetFilter, setDatasetFilter] = useState("ALL");
  const [searchQuery, setSearchQuery] = useState("");

  const [activeVideoEv, setActiveVideoEv] = useState<Evidence | null>(null);
  const [activeDetailEv, setActiveDetailEv] = useState<Evidence | null>(null);
  const [verifyingId, setVerifyingId] = useState<string | null>(null);
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);

  const datasetMap: Record<string, Dataset> = {};
  for (const ds of datasets) datasetMap[ds.id] = ds;

  function showToast(msg: string, ok = true) {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3500);
  }

  useEffect(() => {
    loadStoredAuth();
    if (!getUser()) { router.push("/"); return; }
    loadAll();
  }, [router]);

  useEffect(() => {
    fetchEvidence();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceFilter, vendorFilter, integrityFilter, caseFilter, searchQuery]);

  async function loadAll() {
    try {
      setLoading(true);
      const [c, ds] = await Promise.all([getCases(), getDatasets()]);
      setCases(c);
      setDatasets(ds);
      await fetchEvidence();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  }

  const fetchEvidence = useCallback(async () => {
    try {
      setLoading(true);
      const data = await listAllEvidence({
        source_type: sourceFilter !== "ALL" ? sourceFilter : undefined,
        vendor: vendorFilter !== "ALL" ? vendorFilter : undefined,
        integrity_status: integrityFilter !== "ALL" ? integrityFilter : undefined,
        case_id: caseFilter !== "ALL" ? caseFilter : undefined,
        search: searchQuery.trim() || undefined,
        limit: 200,
      });
      setEvidenceList(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load evidence");
    } finally {
      setLoading(false);
    }
  }, [sourceFilter, vendorFilter, integrityFilter, caseFilter, searchQuery]);

  const filteredEvidence = datasetFilter === "ALL"
    ? evidenceList
    : evidenceList.filter(ev => ev.dataset_id === datasetFilter);

  async function handleVerify(ev: Evidence, e?: React.MouseEvent) {
    e?.stopPropagation();
    try {
      setVerifyingId(ev.id);
      const res = await verifyEvidence(ev.id) as { integrity_status: string };
      showToast(`Hash ${res.integrity_status === "verified" ? "✓ VERIFIED" : "✕ MISMATCH"} — ${ev.camera_id}`, res.integrity_status === "verified");
      fetchEvidence();
    } catch {
      showToast("Verification failed", false);
    } finally {
      setVerifyingId(null);
    }
  }

  async function handleRunAI(ev: Evidence) {
    try {
      setAnalysisId(ev.id);
      await runAIDetection(ev.id);
      showToast(`AI analysis launched for ${ev.camera_id}`, true);
      fetchEvidence();
    } catch {
      showToast("AI analysis failed", false);
    } finally {
      setAnalysisId(null);
    }
  }

  function renderSourceBadge(sourceType?: string) {
    switch (sourceType) {
      case "PUBLIC_RESEARCH_DATASET": return <span className={styles.badgePublic}>PUBLIC RESEARCH</span>;
      case "AUTHORIZED_DVR_EXPORT": case "AUTHORIZED_CCTV_RECORDING": return <span className={styles.badgeAuth}>AUTHORIZED EVIDENCE</span>;
      case "VENDOR_SAMPLE": return <span className={styles.badgeVendor}>VENDOR SAMPLE</span>;
      case "SYNTHETIC_DEMO": return <span className={styles.badgeSynthetic}>SYNTHETIC DEMO</span>;
      default: return <span className={styles.badgePublic}>USER UPLOADED</span>;
    }
  }

  function renderVendorBadge(ev: Evidence) {
    if (ev.vendor_classification_status === "SIMULATED_DEMO" || ev.is_simulated_adapter)
      return <span className="badge badge-simulated" style={{ fontSize: "0.6rem" }}>{ev.source_vendor}* DEMO</span>;
    if (!ev.source_vendor || ev.source_vendor === "Unknown" || ev.vendor_classification_status === "UNKNOWN")
      return <span className="badge badge-inconclusive" style={{ fontSize: "0.6rem" }}>Vendor: Unknown</span>;
    return <span className="badge badge-verified" style={{ fontSize: "0.6rem" }}>{ev.source_vendor}</span>;
  }

  function renderIntegrityIcon(status: string) {
    if (status === "verified") return <span style={{ color: "#22c55e" }}>✓ VERIFIED</span>;
    if (status === "mismatch") return <span style={{ color: "#ef4444" }}>✕ MISMATCH</span>;
    return <span style={{ color: "#94a3b8" }}>○ UNVERIFIED</span>;
  }

  function shortDatasetName(name: string): string {
    return name
      .replace("VIRAT CCTV Video Benchmark", "VIRAT CCTV")
      .replace("UCF Crime / Real-World Anomaly Detection in CCTV", "UCF Crime")
      .replace("Residential Activity Capture Dataset (RACD)", "RACD")
      .replace("CCTV Action Recognition Benchmark", "CCTV Action")
      .replace("Multi-view Traffic Intersection CCTV Dataset", "Traffic CCTV")
      .replace("FORGE-VISION ", "");
  }

  const uniqueDatasets = datasets.filter(ds => evidenceList.some(ev => ev.dataset_id === ds.id));

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg-void)" }}>
      <Navbar />

      {toast && (
        <div style={{ position: "fixed", top: 72, right: 24, zIndex: 2000, background: toast.ok ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)", border: `1px solid ${toast.ok ? "#22c55e" : "#ef4444"}`, borderRadius: 8, padding: "10px 18px", fontSize: "0.82rem", color: toast.ok ? "#4ade80" : "#f87171", backdropFilter: "blur(12px)" }}>
          {toast.msg}
        </div>
      )}

      <main className={styles.container}>
        {/* HEADER */}
        <div className={styles.header}>
          <div className={styles.titleArea}>
            <h1 className={styles.title}><span>📹</span> CAM / EVIDENCE EXPLORER</h1>
            <p className={styles.subtitle}>Camera evidence repository — real dataset footage with SHA-256 integrity, FFprobe metadata, and chain-of-custody ledger.</p>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 10, alignItems: "flex-end" }}>
            <div className={styles.headerStats}>
              <div className={styles.statCard}><span className={styles.statValue}>{filteredEvidence.length}</span><span className={styles.statLabel}>Cameras</span></div>
              <div className={styles.statCard}><span className={styles.statValue} style={{ color: "#22c55e" }}>{filteredEvidence.filter(e => e.integrity_status === "verified").length}</span><span className={styles.statLabel}>Verified</span></div>
              <div className={styles.statCard}><span className={styles.statValue} style={{ color: "#06b6d4" }}>{filteredEvidence.filter(e => e.source_type === "PUBLIC_RESEARCH_DATASET").length}</span><span className={styles.statLabel}>Kaggle</span></div>
            </div>
            <button onClick={() => router.push("/datasets")} className="btn btn-primary btn-sm" style={{ fontSize: "0.75rem" }}>
              + Import Videos to CAM →
            </button>
          </div>
        </div>

        {error && <div style={{ background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", borderRadius: 8, padding: "10px 16px", marginBottom: 16, color: "#f87171", fontSize: "0.8rem" }}>{error}</div>}

        {/* FILTERS */}
        <section className={styles.filterSection}>
          <div className={styles.searchBar}>
            <input type="text" placeholder="🔍 Search Camera ID, Evidence ID, filename, dataset, vendor..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)} className={styles.searchInput} />
            {cases.length > 0 && (
              <select value={caseFilter} onChange={e => setCaseFilter(e.target.value)} className="select" style={{ fontSize: "0.78rem", padding: "7px 12px", background: "rgba(2,6,23,0.7)", color: "#f8fafc", borderColor: "rgba(255,255,255,0.12)", borderRadius: 6, minWidth: 200 }}>
                <option value="ALL">All Cases</option>
                {cases.map(c => <option key={c.id} value={c.id}>{c.id}: {c.title}</option>)}
              </select>
            )}
          </div>

          {uniqueDatasets.length > 0 && (
            <div className={styles.filterRow}>
              <div className={styles.filterGroup}>
                <span className={styles.filterGroupLabel}>Dataset:</span>
                <div className={styles.filterChips}>
                  <button onClick={() => setDatasetFilter("ALL")} className={`${styles.chip} ${datasetFilter === "ALL" ? styles.chipActive : ""}`}>All Datasets</button>
                  {uniqueDatasets.map(ds => (
                    <button key={ds.id} onClick={() => setDatasetFilter(ds.id)} className={`${styles.chip} ${datasetFilter === ds.id ? styles.chipActive : ""}`}>
                      {shortDatasetName(ds.name).slice(0, 28)}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          <div className={styles.filterRow}>
            <div className={styles.filterGroup}>
              <span className={styles.filterGroupLabel}>Source:</span>
              <div className={styles.filterChips}>
                {SOURCE_FILTERS.map(s => <button key={s.id} onClick={() => setSourceFilter(s.id)} className={`${styles.chip} ${sourceFilter === s.id ? styles.chipActive : ""}`}>{s.label}</button>)}
              </div>
            </div>
            <div className={styles.filterGroup}>
              <span className={styles.filterGroupLabel}>Vendor:</span>
              <div className={styles.filterChips}>
                {VENDOR_FILTERS.map(v => <button key={v.id} onClick={() => setVendorFilter(v.id)} className={`${styles.chip} ${vendorFilter === v.id ? styles.chipActiveAmber : ""}`}>{v.label}</button>)}
              </div>
            </div>
            <div className={styles.filterGroup}>
              <span className={styles.filterGroupLabel}>Integrity:</span>
              <div className={styles.filterChips}>
                {INTEGRITY_FILTERS.map(inf => <button key={inf.id} onClick={() => setIntegrityFilter(inf.id)} className={`${styles.chip} ${integrityFilter === inf.id ? styles.chipActive : ""}`}>{inf.label}</button>)}
              </div>
            </div>
          </div>
        </section>

        {/* CAM CARDS */}
        {loading ? (
          <div style={{ padding: 60, textAlign: "center", color: "#64748b" }}>
            <div className="spinner" style={{ width: 28, height: 28, margin: "0 auto 12px" }} />Loading camera evidence...
          </div>
        ) : filteredEvidence.length === 0 ? (
          <div style={{ padding: 60, textAlign: "center", background: "var(--bg-card)", borderRadius: 10, color: "#64748b", border: "1px solid rgba(255,255,255,0.06)" }}>
            <div style={{ fontSize: "2.5rem", marginBottom: 10 }}>📷</div>
            <div style={{ fontWeight: 700, color: "#f8fafc", marginBottom: 4 }}>No Camera Evidence Found</div>
            <div style={{ fontSize: "0.78rem", marginBottom: 16 }}>Import Kaggle benchmark footage from the Dataset Library to build your evidence repository.</div>
            <button onClick={() => router.push("/datasets")} className="btn btn-primary">📦 Go to Dataset Library →</button>
          </div>
        ) : (
          <div className={styles.camGrid}>
            {filteredEvidence.map(ev => {
              const ds = ev.dataset_id ? datasetMap[ev.dataset_id] : null;
              const dsName = ds ? shortDatasetName(ds.name) : (ev.source_name || "");
              const thumbUrl = ev.thumbnail_path ? `${API_BASE}/evidence/${ev.id}/thumbnail?token=${encodeURIComponent(getToken() || "")}` : null;
              return (
                <div key={ev.id} className={styles.camCard}>
                  <div className={styles.camThumbWrap} onClick={() => setActiveVideoEv(ev)} title="Click to play video">
                    {thumbUrl
                      ? <img src={thumbUrl} alt={ev.camera_id} className={styles.camThumb} />
                      : <div className={styles.thumbPlaceholder}><span style={{ fontSize: "2rem" }}>🎥</span><span style={{ fontSize: "0.72rem" }}>{ev.original_filename || "CCTV"}</span></div>
                    }
                    <div className={styles.thumbPlayOverlay}>▶</div>
                    <div className={styles.thumbDuration}>{formatDuration(ev.duration_seconds)}</div>
                    <div className={styles.thumbSourceBadge}>{renderSourceBadge(ev.source_type)}</div>
                    {ev.is_simulated_adapter ? <div className={styles.thumbSimBadge}>SIMULATED</div> : null}
                  </div>

                  <div className={styles.camIdRow}>
                    <span className={styles.camId}>{ev.camera_id}</span>
                    <span className={styles.integrityChip} style={{ color: ev.integrity_status === "verified" ? "#22c55e" : ev.integrity_status === "mismatch" ? "#ef4444" : "#94a3b8" }}>
                      {ev.integrity_status === "verified" ? "✓ VERIFIED" : ev.integrity_status === "mismatch" ? "✕ MISMATCH" : "○ UNVERIFIED"}
                    </span>
                  </div>

                  <div className={styles.camDatasetRow}>
                    {dsName && <span className={styles.camDatasetName}>{dsName}</span>}
                    {renderVendorBadge(ev)}
                  </div>

                  <div className={styles.camMetaGrid}>
                    <div className={styles.camMetaItem}><span className={styles.camMetaKey}>Resolution</span><span className={styles.camMetaVal}>{ev.resolution || "—"}</span></div>
                    <div className={styles.camMetaItem}><span className={styles.camMetaKey}>FPS</span><span className={styles.camMetaVal}>{ev.fps ? `${ev.fps}fps` : "—"}</span></div>
                    <div className={styles.camMetaItem}><span className={styles.camMetaKey}>Duration</span><span className={styles.camMetaVal}>{formatDuration(ev.duration_seconds)}</span></div>
                    <div className={styles.camMetaItem}><span className={styles.camMetaKey}>Codec</span><span className={styles.camMetaVal}>{ev.codec || "—"}</span></div>
                  </div>

                  <div className={styles.camHashRow}>
                    <span style={{ color: "#475569", fontSize: "0.62rem" }}>SHA-256:</span>
                    <span style={{ color: "#22c55e", fontSize: "0.62rem", fontFamily: "monospace" }}>{ev.sha256 ? ev.sha256.slice(0, 20) + "…" : "COMPUTING"}</span>
                  </div>

                  <div className={styles.camActions}>
                    <button className="btn btn-primary btn-sm" style={{ flex: 1, fontSize: "0.72rem" }} onClick={() => setActiveVideoEv(ev)}>▶ OPEN VIDEO</button>
                    <button className="btn btn-ghost btn-sm" style={{ flex: 1, fontSize: "0.72rem" }} onClick={() => setActiveDetailEv(ev)}>🔍 VIEW EVIDENCE</button>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        <div className={styles.disclaimerBanner}>
          <span style={{ fontSize: "1.1rem" }}>ℹ️</span>
          <div>
            <strong>Forensic Provenance Rule:</strong> Public Kaggle CCTV research datasets have <code>vendor = &quot;Unknown&quot;</code> and <code>vendor_classification_status = &quot;UNKNOWN&quot;</code> to prevent falsification. <strong>* SIMULATED VENDOR DATA</strong> labels demo-only synthetic formats. Original files are preserved read-only.
          </div>
        </div>
      </main>

      {/* VIDEO MODAL */}
      {activeVideoEv && (
        <div className={styles.modalOverlay} onClick={() => setActiveVideoEv(null)}>
          <div className={styles.videoModalContent} onClick={e => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <div className={styles.modalTitle}>
                <span>📹</span>
                <span style={{ fontFamily: "monospace", color: "#f59e0b" }}>{activeVideoEv.camera_id}</span>
                <span className="mono-sm text-cyan" style={{ fontSize: "0.72rem" }}>{activeVideoEv.original_filename || activeVideoEv.source_name}</span>
              </div>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <button onClick={() => { setActiveVideoEv(null); setActiveDetailEv(activeVideoEv); }} className="btn btn-ghost btn-sm" style={{ fontSize: "0.68rem" }}>🔍 Evidence Details</button>
                <button onClick={() => setActiveVideoEv(null)} className={styles.closeBtn}>✕</button>
              </div>
            </div>
            <div className={styles.videoContainer}>
              <video controls autoPlay className={styles.videoPlayer} src={`${API_BASE}/evidence/${activeVideoEv.id}/video?token=${encodeURIComponent(getToken() || "")}`}>
                Your browser does not support HTML5 video streaming.
              </video>
            </div>
            <div style={{ padding: "10px 16px", background: "#090d16", display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.75rem", borderTop: "1px solid rgba(255,255,255,0.07)", flexWrap: "wrap", gap: 8 }}>
              <div style={{ display: "flex", gap: 16 }}>
                <span><span className="text-muted">Source:</span> <span className="text-cyan font-bold">{activeVideoEv.source_type?.replace(/_/g, " ")}</span></span>
                <span><span className="text-muted">Vendor:</span> <span className="text-amber font-bold">{activeVideoEv.source_vendor}</span></span>
                <span><span className="text-muted">SHA-256:</span> <span style={{ color: "#22c55e", fontFamily: "monospace" }}>{activeVideoEv.sha256?.slice(0, 16)}…</span></span>
              </div>
              <button onClick={() => { setActiveVideoEv(null); router.push(`/case/${activeVideoEv.case_id}`); }} className="btn btn-primary btn-sm">Open in Workstation →</button>
            </div>
          </div>
        </div>
      )}

      {/* EVIDENCE DETAIL SLIDE-OVER */}
      {activeDetailEv && (
        <>
          <div className={styles.slideOverBackdrop} onClick={() => setActiveDetailEv(null)} />
          <div className={styles.slideOverPanel}>
            <div className={styles.slideOverHeader}>
              <div>
                <div className={styles.slideOverCamId}>{activeDetailEv.camera_id}</div>
                <div style={{ fontSize: "0.7rem", color: "#64748b", marginTop: 2 }}>Evidence Detail — {activeDetailEv.id.slice(0, 16)}…</div>
              </div>
              <button onClick={() => setActiveDetailEv(null)} className={styles.closeBtn}>✕</button>
            </div>

            <div className={styles.slideOverBody}>
              <div className={styles.detailSection}>
                <div className={styles.detailSectionTitle}>Identifiers</div>
                <div className={styles.detailField}><span className={styles.detailKey}>Evidence ID</span><span className={styles.detailVal} style={{ fontFamily: "monospace", color: "#06b6d4", fontSize: "0.72rem" }}>{activeDetailEv.id}</span></div>
                <div className={styles.detailField}><span className={styles.detailKey}>Camera ID</span><span className={styles.detailVal} style={{ fontFamily: "monospace", color: "#f59e0b" }}>{activeDetailEv.camera_id}</span></div>
                <div className={styles.detailField}><span className={styles.detailKey}>Original Camera</span><span className={styles.detailVal}>{activeDetailEv.original_camera_id || "—"}</span></div>
                <div className={styles.detailField}><span className={styles.detailKey}>Channel</span><span className={styles.detailVal}>{activeDetailEv.channel || "—"}</span></div>
              </div>

              <div className={styles.detailSection}>
                <div className={styles.detailSectionTitle}>Provenance</div>
                <div className={styles.detailField}><span className={styles.detailKey}>Dataset</span><span className={styles.detailVal}>{activeDetailEv.dataset_id ? (datasetMap[activeDetailEv.dataset_id] ? shortDatasetName(datasetMap[activeDetailEv.dataset_id].name) : activeDetailEv.dataset_id) : "—"}</span></div>
                <div className={styles.detailField}><span className={styles.detailKey}>Filename</span><span className={styles.detailVal} style={{ wordBreak: "break-all", fontSize: "0.72rem" }}>{activeDetailEv.original_filename || activeDetailEv.source_name || "—"}</span></div>
                <div className={styles.detailField}><span className={styles.detailKey}>Source Platform</span><span className={styles.detailVal}>{activeDetailEv.source_platform || "—"}</span></div>
                <div className={styles.detailField}><span className={styles.detailKey}>Source Type</span><span className={styles.detailVal}>{activeDetailEv.source_type?.replace(/_/g, " ") || "—"}</span></div>
                <div className={styles.detailField}><span className={styles.detailKey}>Provider</span><span className={styles.detailVal}>{activeDetailEv.source_provider || "—"}</span></div>
                <div className={styles.detailField}><span className={styles.detailKey}>Vendor</span><span className={styles.detailVal}>{activeDetailEv.source_vendor || "Unknown"}</span></div>
                <div className={styles.detailField}><span className={styles.detailKey}>Vendor Status</span><span className={styles.detailVal}>{activeDetailEv.vendor_classification_status || "UNKNOWN"}</span></div>
              </div>

              <div className={styles.detailSection}>
                <div className={styles.detailSectionTitle}>Video Metadata</div>
                <div className={styles.detailField}><span className={styles.detailKey}>File Size</span><span className={styles.detailVal}>{formatSize(activeDetailEv.file_size_bytes)}</span></div>
                <div className={styles.detailField}><span className={styles.detailKey}>Duration</span><span className={styles.detailVal}>{formatDuration(activeDetailEv.duration_seconds)}</span></div>
                <div className={styles.detailField}><span className={styles.detailKey}>Resolution</span><span className={styles.detailVal}>{activeDetailEv.resolution || "—"}</span></div>
                <div className={styles.detailField}><span className={styles.detailKey}>FPS</span><span className={styles.detailVal}>{activeDetailEv.fps ? `${activeDetailEv.fps} fps` : "—"}</span></div>
                <div className={styles.detailField}><span className={styles.detailKey}>Codec</span><span className={styles.detailVal}>{activeDetailEv.codec || "—"}</span></div>
                <div className={styles.detailField}><span className={styles.detailKey}>Bitrate</span><span className={styles.detailVal}>{activeDetailEv.bitrate_kbps ? `${activeDetailEv.bitrate_kbps} kbps` : "—"}</span></div>
              </div>

              <div className={styles.detailSection}>
                <div className={styles.detailSectionTitle}>Forensic Status</div>
                <div className={styles.detailField}><span className={styles.detailKey}>Integrity</span><span className={styles.detailVal}>{renderIntegrityIcon(activeDetailEv.integrity_status)}</span></div>
                <div className={styles.detailField}><span className={styles.detailKey}>Authenticity</span><span className={styles.detailVal}>{activeDetailEv.authenticity_status?.replace(/_/g, " ") || "—"}</span></div>
                <div className={styles.detailField}><span className={styles.detailKey}>Recovery Status</span><span className={styles.detailVal}>{activeDetailEv.recovery_status || "—"}</span></div>
                <div className={styles.detailField}><span className={styles.detailKey}>AI Analysis</span><span className={styles.detailVal}>{activeDetailEv.analysis_status || "pending"}</span></div>
                <div className={styles.detailField}><span className={styles.detailKey}>Import Date</span><span className={styles.detailVal}>{activeDetailEv.import_date || activeDetailEv.ingested_at?.slice(0, 10) || "—"}</span></div>
              </div>

              <div className={styles.detailSection}>
                <div className={styles.detailSectionTitle}>Cryptographic Hashes</div>
                <div style={{ background: "rgba(2,6,23,0.8)", borderRadius: 6, padding: "10px 12px", border: "1px solid rgba(34,197,94,0.2)" }}>
                  <div style={{ marginBottom: 6 }}>
                    <div style={{ fontSize: "0.6rem", color: "#475569", textTransform: "uppercase", marginBottom: 2 }}>SHA-256 — INTEGRITY VERIFIED</div>
                    <div style={{ fontFamily: "monospace", fontSize: "0.65rem", color: "#22c55e", wordBreak: "break-all" }}>{activeDetailEv.sha256 || "—"}</div>
                  </div>
                  {activeDetailEv.md5 && <div style={{ marginBottom: 6 }}><div style={{ fontSize: "0.6rem", color: "#475569", textTransform: "uppercase", marginBottom: 2 }}>MD5</div><div style={{ fontFamily: "monospace", fontSize: "0.65rem", color: "#94a3b8", wordBreak: "break-all" }}>{activeDetailEv.md5}</div></div>}
                  {activeDetailEv.sha3_256 && <div><div style={{ fontSize: "0.6rem", color: "#475569", textTransform: "uppercase", marginBottom: 2 }}>SHA3-256</div><div style={{ fontFamily: "monospace", fontSize: "0.65rem", color: "#94a3b8", wordBreak: "break-all" }}>{activeDetailEv.sha3_256}</div></div>}
                </div>
              </div>

              <div className={styles.detailSection}>
                <div className={styles.detailSectionTitle}>File Paths</div>
                <div className={styles.detailField}><span className={styles.detailKey}>Original File Path</span><span className={styles.detailVal} style={{ wordBreak: "break-all", fontSize: "0.65rem", fontFamily: "monospace", color: "#94a3b8" }}>{activeDetailEv.file_path || "—"}</span></div>
                <div className={styles.detailField}><span className={styles.detailKey}>Processing Copy</span><span className={styles.detailVal} style={{ wordBreak: "break-all", fontSize: "0.65rem", fontFamily: "monospace", color: "#64748b" }}>Same as evidence (read-only sealed copy)</span></div>
              </div>

              <div className={styles.detailActions}>
                <button className="btn btn-primary" style={{ fontSize: "0.78rem" }} onClick={() => setActiveVideoEv(activeDetailEv)}>▶ Play Video</button>
                <button className="btn btn-secondary" style={{ fontSize: "0.78rem" }} onClick={() => handleRunAI(activeDetailEv)} disabled={analysisId === activeDetailEv.id}>
                  {analysisId === activeDetailEv.id ? "Analyzing…" : "🤖 Run AI Analysis"}
                </button>
                <button className="btn btn-ghost" style={{ fontSize: "0.78rem" }} onClick={() => handleVerify(activeDetailEv)} disabled={verifyingId === activeDetailEv.id}>
                  {verifyingId === activeDetailEv.id ? "Verifying…" : "🔐 Verify Hash"}
                </button>
                <button className="btn btn-outline" style={{ fontSize: "0.78rem" }} onClick={() => { setActiveDetailEv(null); router.push(`/case/${activeDetailEv.case_id}`); }}>
                  Open in Workstation →
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
