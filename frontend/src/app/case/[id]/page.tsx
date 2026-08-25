"use client";
import { useState, useEffect, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import {
  loadStoredAuth, getUser, getToken, API_BASE,
  getCase, getEvidence, getTimeline, getCustody,
  ingestEvidence, verifyEvidence,
  runAuthenticity, runAIDetection, runMotionHeatmap, runCameraTamper, runCrossReID,
  queryEvidence, generateReport,
  getBookmarks, createBookmark, deleteBookmark,
  type Case, type Evidence, type TimelineData, type CustodyResponse, type NLPResponse, type Bookmark,
} from "@/lib/api";
import styles from "./workstation.module.css";

// ── STATUS UTILS ─────────────────────────────────────────────
function mediaUrl(path: string, token?: string | null) {
  return token ? `${API_BASE}${path}?token=${encodeURIComponent(token)}` : `${API_BASE}${path}`;
}
function heatUrl(id: string, token?: string | null) { return mediaUrl(`/evidence/${id}/heatmap`, token); }
function elaUrl(id: string, token?: string | null) { return mediaUrl(`/evidence/${id}/ela`, token); }

function statusBadge(status: string) {
  const map: Record<string, string> = {
    verified: "badge-verified", mismatch: "badge-mismatch",
    no_tamper_detected: "badge-verified", suspected_edit: "badge-tamper",
    inconclusive: "badge-tamper", pending: "badge-pending",
    intact: "badge-intact", partial: "badge-partial",
    reconstructed: "badge-reconstructed", unverified: "badge-pending",
  };
  return map[status] || "badge-pending";
}

const TABS = ["EVIDENCE", "TIMELINE", "AI FINDINGS", "AUTHENTICITY", "CUSTODY", "REID", "QUERY", "BOOKMARKS"];

export default function Workstation() {
  const { id: caseId } = useParams<{ id: string }>();
  const router = useRouter();
  const [caseData, setCaseData] = useState<Case | null>(null);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [selectedEv, setSelectedEv] = useState<Evidence | null>(null);
  const [timeline, setTimeline] = useState<TimelineData | null>(null);
  const [custody, setCustody] = useState<CustodyResponse | null>(null);
  const [tab, setTab] = useState("EVIDENCE");
  const [loading, setLoading] = useState(true);
  const [analysisLoading, setAnalysisLoading] = useState<string | null>(null);
  const [toast, setToast] = useState<{ msg: string; type: "ok" | "err" } | null>(null);
  const [nlpQuery, setNlpQuery] = useState("");
  const [nlpResult, setNlpResult] = useState<NLPResponse | null>(null);
  const [nlpLoading, setNlpLoading] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadCam, setUploadCam] = useState("CAM-05");
  const [uploading, setUploading] = useState(false);
  const [showIngest, setShowIngest] = useState(false);
  const [chainValid, setChainValid] = useState<boolean | null>(null);
  const [reidHops, setReidHops] = useState<unknown[]>([]);
  const [heatmapKey, setHeatmapKey] = useState(0);
  const [elaKey, setElaKey] = useState(0);
  const [bookmarks, setBookmarks] = useState<Bookmark[]>([]);
  const [showBookmarkModal, setShowBookmarkModal] = useState(false);
  const [bmTitle, setBmTitle] = useState("");
  const [bmNotes, setBmNotes] = useState("");
  const [bmTag, setBmTag] = useState("SUSPECT");
  const [bmTime, setBmTime] = useState("00:15:30");
  const [bmFrame, setBmFrame] = useState(2400);

  const fileRef = useRef<HTMLInputElement>(null);
  const user = getUser();

  useEffect(() => {
    loadStoredAuth();
    if (!getUser()) { router.replace("/"); return; }
    loadAll();
  }, [caseId]);

  async function loadAll() {
    setLoading(true);
    try {
      const [c, ev, tl, cu, bms] = await Promise.all([
        getCase(caseId), getEvidence(caseId),
        getTimeline(caseId), getCustody(caseId),
        getBookmarks(caseId),
      ]);
      setCaseData(c); setEvidence(ev); setTimeline(tl); setCustody(cu); setBookmarks(bms);
      setChainValid(cu.chain_verification.is_valid);
      if (ev.length > 0 && !selectedEv) setSelectedEv(ev[0]);
    } catch {
      showToast("Failed to load case data", "err");
    } finally { setLoading(false); }
  }

  async function handleCreateBookmark(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedEv) return;
    try {
      await createBookmark({
        case_id: caseId,
        evidence_id: selectedEv.id,
        camera_id: selectedEv.camera_id,
        timestamp_in_video: bmTime,
        frame_number: Number(bmFrame),
        title: bmTitle,
        notes: bmNotes,
        tag: bmTag,
      });
      showToast("Bookmark saved to case", "ok");
      setShowBookmarkModal(false);
      setBmTitle(""); setBmNotes("");
      const bms = await getBookmarks(caseId);
      setBookmarks(bms);
    } catch (err: unknown) {
      showToast(err instanceof Error ? err.message : "Failed to save bookmark", "err");
    }
  }

  async function handleDeleteBookmark(id: string) {
    try {
      await deleteBookmark(id);
      showToast("Bookmark removed", "ok");
      const bms = await getBookmarks(caseId);
      setBookmarks(bms);
    } catch (err: unknown) {
      showToast(err instanceof Error ? err.message : "Failed to delete bookmark", "err");
    }
  }

  function showToast(msg: string, type: "ok" | "err" = "ok") {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 4000);
  }

  async function runAnalysis(fn: () => Promise<unknown>, label: string) {
    if (!selectedEv) return;
    setAnalysisLoading(label);
    try {
      await fn();
      showToast(`${label} completed`, "ok");
      const ev = await getEvidence(caseId);
      setEvidence(ev);
      const updated = ev.find(e => e.id === selectedEv.id);
      if (updated) setSelectedEv(updated);
      if (label.includes("Heatmap")) setHeatmapKey(k => k + 1);
      if (label.includes("Authenticity")) setElaKey(k => k + 1);
      const tl = await getTimeline(caseId);
      setTimeline(tl);
      const cu = await getCustody(caseId);
      setCustody(cu); setChainValid(cu.chain_verification.is_valid);
    } catch (err: unknown) {
      showToast(err instanceof Error ? err.message : `${label} failed`, "err");
    } finally { setAnalysisLoading(null); }
  }

  async function handleIngest(e: React.FormEvent) {
    e.preventDefault();
    if (!uploadFile) return;
    setUploading(true);
    try {
      const result = await ingestEvidence(caseId, uploadFile, uploadCam, "CH-1");
      showToast(`Evidence ingested — ${result.hashes.sha256.slice(0,16)}...`, "ok");
      setShowIngest(false); setUploadFile(null);
      await loadAll();
    } catch (err: unknown) {
      showToast(err instanceof Error ? err.message : "Ingest failed", "err");
    } finally { setUploading(false); }
  }

  async function handleVerify() {
    if (!selectedEv) return;
    setAnalysisLoading("Verify Hash");
    try {
      const r = await verifyEvidence(selectedEv.id) as { integrity_status: string; sha256_match: boolean };
      showToast(`Hash ${r.sha256_match ? "✓ VERIFIED" : "⚠ MISMATCH"}`, r.sha256_match ? "ok" : "err");
      await loadAll();
    } catch { showToast("Verification failed", "err"); }
    finally { setAnalysisLoading(null); }
  }

  async function handleNLPQuery(e: React.FormEvent) {
    e.preventDefault();
    if (!nlpQuery.trim()) return;
    setNlpLoading(true);
    try {
      const r = await queryEvidence(caseId, nlpQuery);
      setNlpResult(r);
    } catch { showToast("Query failed", "err"); }
    finally { setNlpLoading(false); }
  }

  async function handleReID() {
    setAnalysisLoading("Cross-Camera ReID");
    try {
      const r = await runCrossReID(caseId, "Suspect A") as { hops: unknown[] };
      setReidHops(r.hops || []);
      setTab("REID");
      showToast(`ReID complete — ${r.hops?.length || 0} hops generated`, "ok");
      await loadAll();
    } catch { showToast("ReID failed", "err"); }
    finally { setAnalysisLoading(null); }
  }

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh", flexDirection: "column", gap: 16, background: "var(--bg-void)", color: "#64748b" }}>
        <div className="spinner" style={{ width: 36, height: 36, borderWidth: 3 }} />
        <div>Loading forensic workstation...</div>
      </div>
    );
  }

  return (
    <div className={styles.root}>
      <Navbar />

      {/* ── TOP CONTEXT BAR ──────────────────────────────── */}
      <header className={styles.topbar}>
        <div className={styles.topLeft}>
          <button className="btn btn-ghost btn-sm" onClick={() => router.push("/dashboard")}>← CASES</button>
          <div className={styles.topDivider} />
          <div className={styles.caseChip}>
            <span className="mono-sm text-amber">{caseId}</span>
            <span className={styles.caseChipTitle}>{caseData?.title}</span>
          </div>
        </div>
        <div className={styles.topRight}>
          {/* Chain status */}
          <div className={`${styles.chainBadge} ${chainValid === null ? "" : chainValid ? styles.chainOk : styles.chainBroken}`}>
            <div className={`status-dot ${chainValid ? "verified" : "mismatch"}`} />
            {chainValid === null ? "CHAIN ?" : chainValid ? "CHAIN INTACT" : "⚠ CHAIN BROKEN"}
          </div>
          {/* Evidence count */}
          <div className={styles.topStat}>
            <span className="text-muted text-xs">EVIDENCE</span>
            <span className="text-amber font-bold">{evidence.length}</span>
          </div>
          {/* Custody entries */}
          <div className={styles.topStat}>
            <span className="text-muted text-xs">CUSTODY</span>
            <span className="text-cyan font-bold">{custody?.entries?.length || 0}</span>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={() => generateReport(caseId).catch(() => showToast("Report failed", "err"))}>
            📄 REPORT
          </button>
          <span className="badge badge-ai">{user?.role?.toUpperCase()}</span>
        </div>
      </header>

      {/* ── MAIN 4-PANE LAYOUT ───────────────────────────── */}
      <div className={styles.workarea}>
        {/* ── LEFT PANE: Evidence Tree ─────────────────── */}
        <aside className={styles.leftPane}>
          <div className="section-header">
            <div className="section-title">🗃 EVIDENCE TREE</div>
            <button className="btn btn-primary btn-sm" onClick={() => setShowIngest(true)}>+ INGEST</button>
          </div>
          <div className={styles.evidenceList}>
            {evidence.length === 0 ? (
              <div className={styles.emptyTree}>
                <div>No evidence ingested</div>
                <button className="btn btn-primary btn-sm" onClick={() => setShowIngest(true)}>+ Ingest Evidence</button>
              </div>
            ) : evidence.map(ev => (
              <div
                key={ev.id}
                className={`${styles.evItem} ${selectedEv?.id === ev.id ? styles.evItemActive : ""}`}
                onClick={() => setSelectedEv(ev)}
              >
                <div className={styles.evItemTop}>
                  <span className="mono-sm text-muted">{ev.camera_id}</span>
                  <div className="flex-row" style={{gap:4}}>
                    {ev.source_type === "PUBLIC_RESEARCH_DATASET" ? (
                      <span className="badge badge-inconclusive" style={{fontSize:"0.6rem",padding:"1px 5px"}}>RESEARCH</span>
                    ) : ev.is_simulated_adapter ? (
                      <span className="badge badge-simulated" style={{fontSize:"0.62rem",padding:"1px 5px"}}>SIM</span>
                    ) : null}
                    <div className={`status-dot ${ev.integrity_status === "verified" ? "verified" : ev.integrity_status === "mismatch" ? "mismatch" : "pending"}`} />
                  </div>
                </div>
                <div className={styles.evItemVendor}>
                  {ev.source_vendor} {ev.vendor_classification_status === "SIMULATED_DEMO" ? "*" : ""}
                </div>
                <div className={styles.evItemMeta}>
                  <span className={`badge ${statusBadge(ev.recovery_status)}`} style={{fontSize:"0.6rem",padding:"1px 5px"}}>{ev.recovery_status}</span>
                  <span className={`badge ${statusBadge(ev.authenticity_status)}`} style={{fontSize:"0.6rem",padding:"1px 5px"}}>{ev.authenticity_status?.replace("_"," ")}</span>
                </div>
                <div className={styles.evItemCodec}>{ev.codec} · {ev.resolution} · {ev.fps}fps</div>
              </div>
            ))}
          </div>
        </aside>

        {/* ── CENTER PANE: Video + Timeline ────────────── */}
        <div className={styles.centerPane}>
          {/* Tab nav */}
          <div className={styles.tabBar}>
            {TABS.map(t => (
              <button key={t} className={`${styles.tab} ${tab === t ? styles.tabActive : ""}`} onClick={() => setTab(t)}>
                {t}
              </button>
            ))}
          </div>

          <div className={styles.tabContent}>
            {/* EVIDENCE TAB */}
            {tab === "EVIDENCE" && selectedEv && (
              <div className={styles.evidenceDetail}>
                {/* Video Player */}
                <div className={styles.thumbSection}>
                  <VideoPlayer
                    evidenceId={selectedEv.id}
                    cameraId={selectedEv.camera_id}
                    isSimulated={!!selectedEv.is_simulated_adapter}
                    token={getToken() || ""}
                  />
                </div>
                {/* Analysis actions */}
                <div className={styles.analysisBar}>
                  <button className="btn btn-ghost btn-sm" onClick={handleVerify} disabled={!!analysisLoading}>
                    {analysisLoading === "Verify Hash" ? <div className="spinner"/> : "🔐"} VERIFY HASH
                  </button>
                  <button className="btn btn-ghost btn-sm" onClick={() => runAnalysis(() => runAuthenticity(selectedEv.id), "Authenticity")} disabled={!!analysisLoading}>
                    {analysisLoading === "Authenticity" ? <div className="spinner"/> : "🔬"} AUTHENTICITY
                  </button>
                  <button className="btn btn-ghost btn-sm" onClick={() => runAnalysis(() => runAIDetection(selectedEv.id), "AI Detection")} disabled={!!analysisLoading}>
                    {analysisLoading === "AI Detection" ? <div className="spinner"/> : "🤖"} AI DETECT
                  </button>
                  <button className="btn btn-ghost btn-sm" onClick={() => runAnalysis(() => runMotionHeatmap(selectedEv.id), "Heatmap")} disabled={!!analysisLoading}>
                    {analysisLoading === "Heatmap" ? <div className="spinner"/> : "🌡"} HEATMAP
                  </button>
                  <button className="btn btn-ghost btn-sm" onClick={() => runAnalysis(() => runCameraTamper(selectedEv.id), "Camera Tamper")} disabled={!!analysisLoading}>
                    {analysisLoading === "Camera Tamper" ? <div className="spinner"/> : "📷"} CAM TAMPER
                  </button>
                  <button className="btn btn-ghost btn-sm text-amber" onClick={() => setShowBookmarkModal(true)}>
                    🔖 + BOOKMARK
                  </button>
                </div>
                {/* Heatmap + ELA */}
                <div className={styles.imageRow}>
                  <div className={styles.imagePanel}>
                    <div className={styles.imagePanelLabel}>MOTION HEATMAP</div>
                    <AnalysisImage
                      key={heatmapKey}
                      src={heatUrl(selectedEv.id, getToken())}
                      alt="Motion heatmap"
                      placeholder="▶ Run HEATMAP to generate"
                      className={styles.analysisImg}
                    />
                  </div>
                  <div className={styles.imagePanel}>
                    <div className={styles.imagePanelLabel}>ELA — ERROR LEVEL ANALYSIS</div>
                    <AnalysisImage
                      key={elaKey}
                      src={elaUrl(selectedEv.id, getToken())}
                      alt="ELA image"
                      placeholder="▶ Run AUTHENTICITY to generate"
                      className={styles.analysisImg}
                    />
                  </div>
                </div>
              </div>
            )}

            {/* TIMELINE TAB */}
            {tab === "TIMELINE" && <TimelineView timeline={timeline} />}

            {/* AI FINDINGS TAB */}
            {tab === "AI FINDINGS" && (
              <FindingsView evidence={evidence} selectedEv={selectedEv} />
            )}

            {/* AUTHENTICITY TAB */}
            {tab === "AUTHENTICITY" && (
              <AuthenticityView selectedEv={selectedEv} />
            )}

            {/* CUSTODY TAB */}
            {tab === "CUSTODY" && custody && (
              <CustodyView custody={custody} />
            )}

            {/* REID TAB */}
            {tab === "REID" && (
              <ReidView hops={reidHops as ReidHop[]} evidence={evidence} onRun={handleReID} loading={analysisLoading === "Cross-Camera ReID"} />
            )}

            {/* QUERY TAB */}
            {tab === "QUERY" && (
              <QueryView
                query={nlpQuery} setQuery={setNlpQuery}
                result={nlpResult} loading={nlpLoading}
                onSubmit={handleNLPQuery}
              />
            )}

            {/* BOOKMARKS TAB */}
            {tab === "BOOKMARKS" && (
              <BookmarksView
                bookmarks={bookmarks}
                onDelete={handleDeleteBookmark}
                onOpenCreate={() => setShowBookmarkModal(true)}
              />
            )}
          </div>
        </div>

        {/* ── RIGHT PANE: Metadata + Findings ──────────── */}
        <aside className={styles.rightPane}>
          <div className="section-header">
            <div className="section-title">📋 METADATA & STATUS</div>
          </div>
          {selectedEv ? (
            <div className={styles.metaScroll}>
              {/* Status badges */}
              <div className={styles.statusRow}>
                <div className={styles.statusItem}>
                  <div className={styles.statusLabel}>INTEGRITY</div>
                  <span className={`badge ${statusBadge(selectedEv.integrity_status)}`}>
                    {selectedEv.integrity_status.replace("_"," ").toUpperCase()}
                  </span>
                </div>
                <div className={styles.statusItem}>
                  <div className={styles.statusLabel}>AUTHENTICITY</div>
                  <span className={`badge ${statusBadge(selectedEv.authenticity_status)}`}>
                    {selectedEv.authenticity_status?.replace(/_/g," ").toUpperCase() || "PENDING"}
                  </span>
                </div>
                <div className={styles.statusItem}>
                  <div className={styles.statusLabel}>RECOVERY</div>
                  <span className={`badge ${statusBadge(selectedEv.recovery_status)}`}>
                    {selectedEv.recovery_status.toUpperCase()}
                  </span>
                </div>
              </div>

              {/* Hash values */}
              <div className={styles.metaSection}>
                <div className={styles.metaSectionTitle}>HASH VERIFICATION</div>
                {[["MD5", selectedEv.md5], ["SHA256", selectedEv.sha256], ["SHA3-256", selectedEv.sha3_256]].map(([label, val]) => (
                  <div key={label} className={styles.hashRow}>
                    <span className={styles.hashLabel}>{label}</span>
                    <span className="mono-sm text-cyan" style={{wordBreak:"break-all"}}>{val || "—"}</span>
                  </div>
                ))}
              </div>

              {/* Device & Provenance info */}
              <div className={styles.metaSection}>
                <div className={styles.metaSectionTitle}>PROVENANCE & DEVICE</div>
                {[
                  ["Source Type", selectedEv.source_type?.replace(/_/g, " ")],
                  ["Platform", selectedEv.source_platform || "Direct"],
                  ["Vendor", selectedEv.source_vendor],
                  ["Vendor Status", selectedEv.vendor_classification_status || "CONFIRMED"],
                  ["Parser", selectedEv.parser_used],
                  ["Model", selectedEv.device_model],
                  ["Firmware", selectedEv.firmware],
                  ["Camera ID", selectedEv.camera_id],
                  ["Channel", selectedEv.channel],
                ].map(([k, v]) => v ? (
                  <div key={k} className={styles.metaRow}>
                    <span className={styles.metaKey}>{k}</span>
                    <span className={styles.metaVal}>{v}</span>
                  </div>
                ) : null)}
                {selectedEv.is_simulated_adapter || selectedEv.vendor_classification_status === "SIMULATED_DEMO" ? (
                  <div className={styles.simNote}>⚠ SIMULATED ADAPTER / DEMO FORMAT — for evaluation only</div>
                ) : null}
              </div>

              {/* Video info */}
              <div className={styles.metaSection}>
                <div className={styles.metaSectionTitle}>VIDEO PROPERTIES</div>
                {[
                  ["Codec", selectedEv.codec],
                  ["Resolution", selectedEv.resolution],
                  ["Frame Rate", selectedEv.fps ? `${selectedEv.fps} fps` : null],
                  ["Duration", selectedEv.duration_seconds ? `${Math.floor(selectedEv.duration_seconds/60)}m ${Math.floor(selectedEv.duration_seconds%60)}s` : null],
                  ["Bitrate", selectedEv.bitrate_kbps ? `${selectedEv.bitrate_kbps} kbps` : null],
                  ["Frame Count", selectedEv.frame_count?.toString()],
                  ["File Size", selectedEv.file_size_bytes ? `${(selectedEv.file_size_bytes/1048576).toFixed(1)} MB` : null],
                  ["Clock Drift", selectedEv.clock_drift_seconds ? `${selectedEv.clock_drift_seconds}s` : null],
                ].map(([k, v]) => v ? (
                  <div key={k} className={styles.metaRow}>
                    <span className={styles.metaKey}>{k}</span>
                    <span className={styles.metaVal}>{v}</span>
                  </div>
                ) : null)}
              </div>

              {/* Completeness */}
              {selectedEv.recovery_status !== "intact" && (
                <div className={styles.metaSection}>
                  <div className={styles.metaSectionTitle}>COMPLETENESS</div>
                  <div className={styles.completenessBar}>
                    <div className={styles.completenessTrack}>
                      <div className={styles.completenessBar2} style={{width:`${(selectedEv.completeness_score||1)*100}%`}} />
                    </div>
                    <span className="mono-sm text-amber">{((selectedEv.completeness_score||1)*100).toFixed(0)}%</span>
                  </div>
                  <div className={styles.metaNote}>Frame completeness score</div>
                </div>
              )}

              {/* Findings summary */}
              {selectedEv.findings_summary && Object.keys(selectedEv.findings_summary).length > 0 && (
                <div className={styles.metaSection}>
                  <div className={styles.metaSectionTitle}>AI FINDINGS SUMMARY</div>
                  {Object.entries(selectedEv.findings_summary).map(([type, count]) => (
                    <div key={type} className={styles.metaRow}>
                      <span className={`badge badge-ai`} style={{fontSize:"0.65rem"}}>{type}</span>
                      <span className="text-amber font-bold">{count}</span>
                    </div>
                  ))}
                  <div className={styles.simNote}>⚠ AI findings require investigator review</div>
                </div>
              )}

              {/* Ingest info */}
              <div className={styles.metaSection}>
                <div className={styles.metaSectionTitle}>INGEST RECORD</div>
                {[
                  ["Ingested By", selectedEv.ingested_by],
                  ["Ingested At", selectedEv.ingested_at ? new Date(selectedEv.ingested_at).toLocaleString("en-IN") : null],
                  ["Parser Confidence", selectedEv.parser_confidence ? `${(selectedEv.parser_confidence*100).toFixed(0)}%` : null],
                ].map(([k, v]) => v ? (
                  <div key={k} className={styles.metaRow}>
                    <span className={styles.metaKey}>{k}</span>
                    <span className={styles.metaVal}>{v}</span>
                  </div>
                ) : null)}
                {selectedEv.notes && <div className={styles.metaNote}>{selectedEv.notes}</div>}
              </div>
            </div>
          ) : (
            <div className={styles.noSelection}>Select an evidence item</div>
          )}
        </aside>
      </div>

      {/* ── CUSTODY LOG STRIP ────────────────────────────── */}
      <footer className={styles.custodyStrip}>
        <div className={styles.custodyLabel}>
          <span className={`status-dot ${chainValid ? "verified" : "mismatch"}`} />
          CHAIN OF CUSTODY · {custody?.entries?.length || 0} ENTRIES
        </div>
        <div className={styles.custodyEntries}>
          {custody?.entries?.slice(-8).map(entry => (
            <div key={entry.id} className={styles.custodyChip}>
              <span className="text-amber mono-sm">[{entry.seq}]</span>
              <span className="text-xs">{entry.action}</span>
              <span className="text-muted text-xs">{entry.operator_id}</span>
              <span className="mono-sm text-cyan" style={{fontSize:"0.6rem"}}>{entry.this_entry_hash?.slice(0,10)}…</span>
            </div>
          ))}
        </div>
      </footer>

      {/* ── INGEST MODAL ─────────────────────────────────── */}
      {showIngest && (
        <div className={styles.modal}>
          <div className={styles.modalCard}>
            <div className={styles.modalHeader}>
              <span>🔐 FORENSIC EVIDENCE INGEST</span>
              <button className="btn btn-ghost btn-sm" onClick={() => setShowIngest(false)}>✕</button>
            </div>
            <form onSubmit={handleIngest} className={styles.modalBody}>
              <div className={styles.ingestInfo}>
                Triple hash (MD5 + SHA256 + SHA3-256) will be computed on ingest.
                Evidence will be sealed as read-only. Custody event auto-created.
              </div>
              <div className="flex-col">
                <label className="field-label">Evidence File (MP4, AVI, MKV, or disk image)</label>
                <input
                  ref={fileRef} type="file" className="input"
                  accept=".mp4,.avi,.mkv,.mov,.ts,.m4v,.bin,.dd,.e01"
                  onChange={e => setUploadFile(e.target.files?.[0] || null)}
                  required
                />
              </div>
              <div className="flex-col">
                <label className="field-label">Camera / Source ID</label>
                <input className="input input-mono" value={uploadCam}
                       onChange={e => setUploadCam(e.target.value)} placeholder="CAM-01" />
              </div>
              {uploadFile && (
                <div className={styles.filePreview}>
                  <div><span className="text-muted">File:</span> <span className="text-amber">{uploadFile.name}</span></div>
                  <div><span className="text-muted">Size:</span> <span>{(uploadFile.size/1048576).toFixed(2)} MB</span></div>
                </div>
              )}
              <div className="flex-row" style={{justifyContent:"flex-end"}}>
                <button type="button" className="btn btn-ghost" onClick={() => setShowIngest(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={uploading || !uploadFile}>
                  {uploading ? <><div className="spinner"/>Ingesting...</> : "🔐 INGEST & HASH"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      {showBookmarkModal && selectedEv && (
        <div className={styles.modal}>
          <div className={styles.modalCard}>
            <div className={styles.modalHeader}>
              <span>🔖 CREATE EVIDENCE BOOKMARK</span>
              <button className="btn btn-ghost btn-sm" onClick={() => setShowBookmarkModal(false)}>✕</button>
            </div>
            <form onSubmit={handleCreateBookmark} className={styles.modalBody}>
              <div className={styles.ingestInfo}>
                Bookmarks attach critical timestamps and frames to the formal case report and export ledger.
              </div>
              <div className="flex-col">
                <label className="field-label">Bookmark Title *</label>
                <input
                  className="input"
                  required
                  placeholder="e.g. Suspect exits via North Door"
                  value={bmTitle}
                  onChange={e => setBmTitle(e.target.value)}
                />
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                <div className="flex-col">
                  <label className="field-label">Tag Category</label>
                  <select
                    className="select"
                    value={bmTag}
                    onChange={e => setBmTag(e.target.value)}
                  >
                    <option value="SUSPECT">SUSPECT</option>
                    <option value="VEHICLE">VEHICLE</option>
                    <option value="ANOMALY">ANOMALY</option>
                    <option value="RECOVERED">RECOVERED</option>
                    <option value="CUSTOM">CUSTOM</option>
                  </select>
                </div>
                <div className="flex-col">
                  <label className="field-label">Video Timestamp (HH:MM:SS)</label>
                  <input
                    className="input input-mono"
                    value={bmTime}
                    onChange={e => setBmTime(e.target.value)}
                    placeholder="00:15:30"
                  />
                </div>
              </div>
              <div className="flex-col">
                <label className="field-label">Frame Number</label>
                <input
                  type="number"
                  className="input input-mono"
                  value={bmFrame}
                  onChange={e => setBmFrame(Number(e.target.value))}
                />
              </div>
              <div className="flex-col">
                <label className="field-label">Investigator Notes & Basis</label>
                <textarea
                  className="input"
                  rows={2}
                  placeholder="Appearance features, motion path, or recovery detail..."
                  value={bmNotes}
                  onChange={e => setBmNotes(e.target.value)}
                />
              </div>
              <div className="flex-row" style={{ justifyContent: "flex-end", marginTop: 8 }}>
                <button type="button" className="btn btn-ghost" onClick={() => setShowBookmarkModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={!bmTitle.trim()}>
                  Save Bookmark
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── TOAST ─────────────────────────────────────────── */}
      {toast && (
        <div className={`${styles.toast} ${toast.type === "err" ? styles.toastErr : styles.toastOk}`}>
          {toast.msg}
        </div>
      )}
    </div>
  );
}

// ── TIMELINE VIEW ─────────────────────────────────────────────
function TimelineView({ timeline }: { timeline: TimelineData | null }) {
  if (!timeline) return <div className={styles.emptyTab}>No timeline data</div>;
  const tracks = timeline.tracks;

  return (
    <div className={styles.timelineWrap}>
      <div className={styles.timelineHeader}>
        <span className="text-muted text-xs">CAMERA / CHANNEL</span>
        <span className={styles.timelineBar}>RECORDING TIMELINE (click segments for details)</span>
      </div>
      {tracks.map(track => (
        <div key={track.evidence_id} className={styles.timelineTrack}>
          <div className={styles.trackLabel}>
            <div className="text-xs font-bold">{track.camera_id}</div>
            <div className="text-xs text-muted">{track.source_vendor}</div>
            {track.is_simulated && <span className="badge badge-simulated" style={{fontSize:"0.58rem"}}>SIM</span>}
          </div>
          <div className={styles.trackBar}>
            {track.segments.length > 0 ? track.segments.map(seg => (
              <div
                key={seg.id}
                className={`${styles.trackSegment} ${styles[`seg_${seg.segment_type}` as keyof typeof styles]}`}
                style={{ width: `${(1 / track.segments.length) * 100}%` }}
                title={`${seg.segment_type} · completeness ${(seg.completeness * 100).toFixed(0)}% · frames ${seg.start_frame}–${seg.end_frame}`}
              >
                {seg.segment_type === "gap" && <span className={styles.gapLabel}>GAP</span>}
              </div>
            )) : (
              <div className={styles.seg_intact} style={{width:"100%",height:"100%",borderRadius:4}} />
            )}
            {/* AI event markers */}
            {timeline.ai_events
              .filter(e => e.evidence_id === track.evidence_id)
              .slice(0, 10)
              .map(ev => (
                <div key={ev.id} className={styles.eventMarker}
                     title={`${ev.label} @ frame ${ev.frame_number} (${(ev.confidence*100).toFixed(0)}% conf)`} />
              ))
            }
          </div>
          <div className={styles.trackStatus}>
            <span className={`badge ${statusBadge(track.integrity_status)}`} style={{fontSize:"0.58rem"}}>{track.integrity_status}</span>
            <span className={`badge ${statusBadge(track.authenticity_status)}`} style={{fontSize:"0.58rem"}}>{track.authenticity_status?.replace(/_/g," ")}</span>
          </div>
        </div>
      ))}
      <div className={styles.timelineLegend}>
        <span className={styles.legendItem}><span className={styles.legendDot} style={{background:"var(--green-500)"}}/>Intact</span>
        <span className={styles.legendItem}><span className={styles.legendDot} style={{background:"var(--orange-500)"}}/>Partial/Recovered</span>
        <span className={styles.legendItem}><span className={styles.legendDot} style={{background:"var(--red-500)"}}/>Gap</span>
        <span className={styles.legendItem}><span className={styles.legendDot} style={{background:"var(--amber-500)"}}/>AI Event</span>
      </div>
    </div>
  );
}

// ── FINDINGS VIEW ─────────────────────────────────────────────
function FindingsView({ evidence, selectedEv: _selectedEv }: { evidence: Evidence[]; selectedEv: Evidence | null }) {
  const allFindings = evidence.flatMap(e =>
    (e.findings_summary ? Object.entries(e.findings_summary).flatMap(([type, count]) =>
      Array(count).fill(null).map((_, i) => ({ type, camera_id: e.camera_id, evidence_id: e.id, i }))
    ) : [])
  );

  return (
    <div className={styles.findingsWrap}>
      <div className={styles.findingsDisclaimer}>
        ⚠ AI findings are investigative leads — not forensic conclusions. All marked [SIMULATED] require real model integration.
      </div>
      {evidence.map(ev => (
        ev.findings_summary && Object.keys(ev.findings_summary).length > 0 ? (
          <div key={ev.id} className={styles.findingGroup}>
            <div className={styles.findingGroupHeader}>
              <span className="text-amber font-bold">{ev.camera_id}</span>
              <span className="text-muted text-xs">{ev.source_vendor}</span>
              {ev.is_simulated_adapter ? <span className="badge badge-simulated" style={{fontSize:"0.6rem"}}>SIM ADAPTER</span> : null}
            </div>
            {Object.entries(ev.findings_summary).map(([type, count]) => (
              <div key={type} className={styles.findingRow}>
                <span className="badge badge-ai">{type}</span>
                <span className="text-amber font-bold">{count}×</span>
                <span className="text-xs text-muted">detected · frames distributed across clip</span>
                <span className="badge badge-simulated" style={{fontSize:"0.6rem"}}>SIMULATED</span>
              </div>
            ))}
          </div>
        ) : null
      ))}
      {allFindings.length === 0 && (
        <div className={styles.emptyTab}>Run AI Detection on evidence items to generate findings.</div>
      )}
    </div>
  );
}

// ── AUTHENTICITY VIEW ─────────────────────────────────────────
function AuthenticityView({ selectedEv }: { selectedEv: Evidence | null }) {
  if (!selectedEv?.authenticity_findings || selectedEv.authenticity_findings.length === 0) {
    return <div className={styles.emptyTab}>No authenticity analysis run yet. Select evidence and click AUTHENTICITY.</div>;
  }
  return (
    <div className={styles.authWrap}>
      <div className={styles.findingsDisclaimer}>
        ⚠ All findings require expert human review. This tool flags statistical anomalies only — it does not reach forensic conclusions.
      </div>
      <div className={styles.authGrid}>
        {selectedEv.authenticity_findings.map((f) => (
          <div key={f.id} className={`${styles.authCard} ${styles[`auth_${f.severity}` as keyof typeof styles]}`}>
            <div className={styles.authCardHeader}>
              <span className={`badge ${f.severity === "high" ? "badge-mismatch" : f.severity === "medium" ? "badge-tamper" : "badge-pending"}`}>
                {f.severity?.toUpperCase()}
              </span>
              <span className={styles.authType}>{f.check_type}</span>
              {f.is_simulated ? <span className="badge badge-simulated" style={{fontSize:"0.6rem"}}>SIMULATED</span> : null}
            </div>
            <div className={styles.authConf}>Confidence: <span className="text-amber">{(f.confidence*100).toFixed(0)}%</span></div>
            {f.frame_number && <div className="text-xs text-muted">Frame #{f.frame_number}</div>}
            <div className={styles.authDetail}>{f.detail}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── CUSTODY VIEW ──────────────────────────────────────────────
function CustodyView({ custody }: { custody: CustodyResponse }) {
  const { entries, chain_verification: cv } = custody;
  return (
    <div className={styles.custodyWrap}>
      <div className={`${styles.chainStatus} ${cv.is_valid ? styles.chainOk : styles.chainBroken}`}>
        <span className={`status-dot ${cv.is_valid ? "verified" : "mismatch"}`} />
        {cv.is_valid
          ? `✓ CHAIN INTACT — ${cv.entry_count} entries verified. Tamper-evident hash chain confirmed.`
          : `⚠ CHAIN BROKEN at entry #${cv.broken_at_seq} — Evidence may have been modified after acquisition.`}
      </div>
      <div className={styles.custodyTable}>
        <div className={styles.custodyTableHead}>
          <span>SEQ</span><span>ACTION</span><span>OPERATOR</span><span>ROLE</span>
          <span>TIMESTAMP</span><span>PREV HASH</span><span>THIS HASH</span>
        </div>
        {entries.map(entry => (
          <div key={entry.id} className={styles.custodyTableRow}>
            <span className="text-amber mono-sm">{entry.seq}</span>
            <span className="text-xs font-bold">{entry.action}</span>
            <span className="text-xs text-muted">{entry.operator_id}</span>
            <span className={`badge ${entry.operator_role === "supervisor" ? "badge-tamper" : "badge-ai"}`} style={{fontSize:"0.58rem"}}>{entry.operator_role}</span>
            <span className="mono-sm text-xs">{entry.timestamp?.slice(0,19)}</span>
            <span className="mono-sm text-cyan" style={{fontSize:"0.6rem"}}>{entry.prev_entry_hash?.slice(0,12) || "GENESIS"}…</span>
            <span className="mono-sm text-green" style={{fontSize:"0.6rem"}}>{entry.this_entry_hash?.slice(0,12)}…</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── REID VIEW ─────────────────────────────────────────────────
interface ReidHop {
  id: string; subject_label: string; from_evidence_id: string; from_frame: number;
  to_evidence_id: string; to_frame: number; similarity_score: number;
  match_basis: string; is_simulated: number; disclaimer: string;
}

function ReidView({ hops, evidence, onRun, loading }: { hops: ReidHop[]; evidence: Evidence[]; onRun: () => void; loading: boolean }) {
  const evMap = Object.fromEntries(evidence.map(e => [e.id, e]));
  return (
    <div className={styles.reidWrap}>
      <div className={styles.reidHeader}>
        <div>
          <div className="font-bold text-sm">CROSS-CAMERA RE-IDENTIFICATION</div>
          <div className="text-xs text-muted">Appearance-based path reconstruction · NOT biometric identification</div>
        </div>
        <button className="btn btn-cyan btn-sm" onClick={onRun} disabled={loading}>
          {loading ? <div className="spinner"/> : "▶"} RUN ReID
        </button>
      </div>
      <div className={styles.disclaimer}>
        ⚠ DISCLAIMER: This module uses appearance-based similarity matching only (clothing color, build, vehicle type/color).
        It does NOT constitute biometric identification. All hops require investigator verification.
      </div>
      {hops.length === 0 ? (
        <div className={styles.emptyTab}>Run cross-camera ReID to generate suspect/vehicle path hops.</div>
      ) : (
        <div className={styles.reidPath}>
          {hops.map((hop) => {
            const fromEv = evMap[hop.from_evidence_id];
            const toEv = evMap[hop.to_evidence_id];
            return (
              <div key={hop.id} className={styles.reidHop}>
                <div className={styles.reidCam}>
                  <div className={styles.reidCamBubble}>{fromEv?.camera_id || "?"}</div>
                  <div className="text-xs text-muted">Frame #{hop.from_frame}</div>
                </div>
                <div className={styles.reidArrow}>
                  <div className={styles.reidScore}>{(hop.similarity_score*100).toFixed(0)}%</div>
                  <div className={styles.reidBasis}>{hop.match_basis}</div>
                  <div className={styles.arrowLine}><span>→</span></div>
                  {hop.is_simulated ? <span className="badge badge-simulated" style={{fontSize:"0.6rem"}}>SIM</span> : null}
                </div>
                <div className={styles.reidCam}>
                  <div className={styles.reidCamBubble}>{toEv?.camera_id || "?"}</div>
                  <div className="text-xs text-muted">Frame #{hop.to_frame}</div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── QUERY VIEW ────────────────────────────────────────────────
function QueryView({ query, setQuery, result, loading, onSubmit }: {
  query: string; setQuery: (v: string) => void;
  result: NLPResponse | null; loading: boolean;
  onSubmit: (e: React.FormEvent) => void;
}) {
  const EXAMPLES = [
    "Show all vehicles detected in this case",
    "Any tamper or authenticity flags?",
    "What is the chain of custody status?",
    "Show persons detected across all cameras",
    "Any camera tampering events?",
    "Summary of this investigation",
  ];
  return (
    <div className={styles.queryWrap}>
      <div className={styles.queryHeader}>
        <div className="font-bold text-sm">NATURAL LANGUAGE INVESTIGATION ENGINE</div>
        <div className="text-xs text-muted">Strictly grounded to stored evidence — no hallucination. Every answer cites the evidence ID/frame.</div>
      </div>
      <form onSubmit={onSubmit} className={styles.queryForm}>
        <input
          className="input" value={query} onChange={e => setQuery(e.target.value)}
          placeholder='e.g. "Any tamper flags?" or "Show all vehicles on Camera 2"'
        />
        <button className="btn btn-primary" type="submit" disabled={loading || !query.trim()}>
          {loading ? <div className="spinner"/> : "QUERY →"}
        </button>
      </form>
      <div className={styles.queryExamples}>
        {EXAMPLES.map(ex => (
          <button key={ex} className={styles.exampleChip} onClick={() => setQuery(ex)}>{ex}</button>
        ))}
      </div>
      {result && (
        <div className={styles.queryResult}>
          <div className={styles.queryResultHeader}>
            <span className="text-amber">ANSWER</span>
            <span className="badge badge-verified">Confidence {(result.confidence*100).toFixed(0)}%</span>
            <span className="text-xs text-muted">Intent: {result.intent}</span>
          </div>
          <div className={styles.queryAnswer}>{result.answer}</div>
          {result.citations && result.citations.length > 0 && (
            <div className={styles.queryCitations}>
              <div className="text-xs text-muted font-bold">CITATIONS ({result.citations.length})</div>
              {(result.citations as Record<string, unknown>[]).slice(0, 5).map((c, _i) => (
                <div key={_i} className={styles.citationRow}>
                  {Object.entries(c).filter(([,v]) => v).map(([k, v]) => (
                    <span key={k}><span className="text-muted">{k}:</span> <span className="mono-sm text-cyan">{String(v)}</span></span>
                  ))}
                </div>
              ))}
            </div>
          )}
          <div className={styles.groundingNote}>{result.grounding_rule}</div>
        </div>
      )}
    </div>
  );
}

// ── VIDEO PLAYER ──────────────────────────────────────────────
function VideoPlayer({ evidenceId, cameraId, isSimulated, token }: {
  evidenceId: string; cameraId: string; isSimulated: boolean; token: string;
}) {
  const [videoFailed, setVideoFailed] = useState(false);
  const [thumbFailed, setThumbFailed] = useState(false);
  const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";
  const tokenQ = token ? `?token=${encodeURIComponent(token)}` : "";
  const videoSrc = `${API}/evidence/${evidenceId}/video${tokenQ}`;
  const thumbSrc = `${API}/evidence/${evidenceId}/thumbnail${tokenQ}`;

  const showPlaceholder = videoFailed && thumbFailed;

  return (
    <div style={{ position: "relative", background: "#0a0e1a", borderRadius: 6, overflow: "hidden", border: "1px solid var(--border)", minHeight: 180 }}>
      {!videoFailed && (
        <video
          key={evidenceId}
          controls
          preload="metadata"
          style={{ width: "100%", maxHeight: 260, display: "block", background: "#000" }}
          onError={() => setVideoFailed(true)}
        >
          <source src={videoSrc} />
        </video>
      )}
      {videoFailed && !thumbFailed && (
        <img
          src={thumbSrc}
          alt={`${cameraId} thumbnail`}
          style={{ width: "100%", maxHeight: 260, objectFit: "cover", display: "block" }}
          onError={() => setThumbFailed(true)}
        />
      )}
      {showPlaceholder && (
        <div style={{
          display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
          height: 180, gap: 10, color: "#334155",
        }}>
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#334155" strokeWidth="1.2">
            <rect x="2" y="7" width="20" height="14" rx="2"/>
            <path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/>
            <circle cx="12" cy="13" r="3"/>
          </svg>
          <div style={{ fontSize: "0.75rem", fontFamily: "monospace", textAlign: "center", lineHeight: 1.6 }}>
            <div style={{ color: "#f59e0b", fontWeight: 700, marginBottom: 4 }}>{cameraId}</div>
            <div>No video file in evidence store</div>
            <div style={{ fontSize: "0.65rem", color: "#1e3a5f", marginTop: 4 }}>Ingest a real video file to enable playback</div>
          </div>
        </div>
      )}
      {/* Overlay badges */}
      <div style={{ position: "absolute", top: 8, left: 8, display: "flex", gap: 6, alignItems: "center", pointerEvents: "none" }}>
        {!showPlaceholder && (
          <span className="mono-sm text-amber" style={{ background: "rgba(0,0,0,0.7)", padding: "2px 6px", borderRadius: 4, fontSize: "0.7rem" }}>
            {cameraId}
          </span>
        )}
        {isSimulated && <span className="badge badge-simulated" style={{ fontSize: "0.62rem" }}>SIMULATED ADAPTER</span>}
      </div>
      {/* Forensic watermark */}
      {!showPlaceholder && (
        <div style={{ position: "absolute", bottom: 8, right: 8, fontSize: "0.58rem", color: "rgba(100,116,139,0.8)", fontFamily: "monospace", background: "rgba(0,0,0,0.5)", padding: "1px 5px", borderRadius: 3, pointerEvents: "none" }}>
          FORGE-VISION · EVIDENCE SEALED
        </div>
      )}
    </div>
  );
}

// ── ANALYSIS IMAGE COMPONENT ──────────────────────────────────
function AnalysisImage({ src, alt, placeholder, className }: {
  src: string; alt: string; placeholder: string; className?: string;
}) {
  const [failed, setFailed] = useState(false);
  const [loaded, setLoaded] = useState(false);

  return (
    <div style={{ position: "relative", width: "100%", height: 160, background: "#060913", overflow: "hidden", display: "flex", alignItems: "center", justifyContent: "center" }}>
      {!failed && (
        <img
          src={src}
          alt={alt}
          className={className}
          style={{ width: "100%", height: "100%", objectFit: "contain", display: loaded ? "block" : "none" }}
          onLoad={() => setLoaded(true)}
          onError={() => setFailed(true)}
        />
      )}
      {(!loaded || failed) && (
        <div style={{
          display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
          gap: 8, padding: 12, textAlign: "center", color: "#475569", width: "100%", height: "100%",
        }}>
          <div style={{ fontSize: "1.4rem", opacity: 0.6 }}>🔬</div>
          <div style={{ fontSize: "0.72rem", fontFamily: "monospace", color: "#64748b", maxWidth: 220, lineHeight: 1.5 }}>
            {placeholder}
          </div>
        </div>
      )}
    </div>
  );
}

// ── BOOKMARKS VIEW ────────────────────────────────────────────
function BookmarksView({
  bookmarks,
  onDelete,
  onOpenCreate,
}: {
  bookmarks: Bookmark[];
  onDelete: (id: string) => void;
  onOpenCreate: () => void;
}) {
  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <div className="font-bold text-sm text-amber">INVESTIGATOR EVIDENCE BOOKMARKS ({bookmarks.length})</div>
          <div className="text-xs text-muted">Key frames, timestamps, suspect leads, and anomaly tags saved for the forensic report.</div>
        </div>
        <button onClick={onOpenCreate} className="btn btn-primary btn-sm">+ Add Bookmark</button>
      </div>

      {bookmarks.length === 0 ? (
        <div style={{ padding: 40, textAlign: "center", color: "#64748b", background: "var(--bg-card)", borderRadius: 6 }}>
          No bookmarks created yet. Click "+ Add Bookmark" or use the bookmark button on any evidence stream.
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {bookmarks.map((bm) => (
            <div
              key={bm.id}
              style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                padding: "10px 14px", background: "var(--bg-card)", border: "1px solid var(--border-base)",
                borderRadius: 6, gap: 12,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span className="badge badge-warning" style={{ fontSize: "0.65rem" }}>{bm.tag}</span>
                <div>
                  <div style={{ fontWeight: 700, color: "#f8fafc", fontSize: "0.82rem" }}>{bm.title}</div>
                  <div style={{ fontSize: "0.7rem", color: "#94a3b8" }}>{bm.notes || "No notes attached"}</div>
                  <div style={{ fontSize: "0.64rem", color: "#64748b", marginTop: 2 }}>
                    Created by {bm.created_by} · {bm.created_at?.slice(0, 10)}
                  </div>
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <div style={{ textAlign: "right" }}>
                  <div className="mono-sm text-cyan">{bm.camera_id}</div>
                  <div className="mono-sm text-amber" style={{ fontSize: "0.68rem" }}>{bm.timestamp_in_video}</div>
                </div>
                <button
                  onClick={() => onDelete(bm.id)}
                  className="btn btn-ghost btn-sm text-danger"
                  style={{ fontSize: "0.7rem", padding: "2px 6px" }}
                >
                  ✕
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


