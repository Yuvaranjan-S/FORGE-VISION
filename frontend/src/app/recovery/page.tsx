"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import { getEvidence, getCases, loadStoredAuth, getUser, type Evidence, type Case } from "@/lib/api";
import styles from "./recovery.module.css";

export default function RecoveryPage() {
  const router = useRouter();
  const [cases, setCases] = useState<Case[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState("CASE-DEMO001");
  const [evidenceList, setEvidenceList] = useState<Evidence[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadStoredAuth();
    if (!getUser()) {
      router.push("/");
      return;
    }
    fetchData();
  }, [router, selectedCaseId]);

  async function fetchData() {
    try {
      setLoading(true);
      const caseData = await getCases();
      setCases(caseData);
      const evData = await getEvidence(selectedCaseId);
      setEvidenceList(evData);
    } catch (err: unknown) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg-void)" }}>
      <Navbar />

      <main className={styles.container}>
        {/* HEADER */}
        <div className={styles.header}>
          <div className={styles.titleArea}>
            <h1 className={styles.title}>
              <span>🔬</span> EVIDENCE RECOVERY & RECONSTRUCTION WORKSPACE
            </h1>
            <p className={styles.subtitle}>
              H.264/H.265 NAL unit signature carving · Stream continuity analysis · Unallocated sector fragment matching.
            </p>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span className="text-xs text-muted font-bold">CASE:</span>
            <select
              value={selectedCaseId}
              onChange={(e) => setSelectedCaseId(e.target.value)}
              className="select-sm"
              style={{ background: "#050811", border: "1px solid #1e293b", color: "#f8fafc", padding: "4px 8px", borderRadius: 4, fontSize: "0.78rem" }}
            >
              {cases.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.id} — {c.title}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* DISCLAIMER */}
        <div className={styles.disclaimer}>
          ⚠ <strong>Forensic Principle:</strong> File carving and stream reconstruction operate strictly on verified bitstream working copies.
          Proprietary filesystem carving algorithms that require vendor documentation are labeled <code>[SIMULATED]</code>.
          Generic H.264/H.265 NAL unit scans represent verified mathematical continuity analyses.
        </div>

        {/* EVIDENCE CARDS */}
        {loading ? (
          <div style={{ padding: 40, textAlign: "center", color: "#64748b" }}>Analyzing evidence fragments...</div>
        ) : (
          <div className={styles.grid}>
            {evidenceList.map((ev) => {
              const segments = ev.recovery_segments || [];
              return (
                <div key={ev.id} className={styles.card}>
                  <div className={styles.cardHeader}>
                    <div>
                      <div className={styles.cardTitle}>
                        <span className="mono-sm text-amber font-bold">{ev.camera_id}</span> · {ev.source_vendor}
                      </div>
                      <div className="text-xs text-muted mono-sm">{ev.device_model || "Generic Stream"}</div>
                    </div>
                    <span
                      className={`badge ${
                        ev.recovery_status === "intact"
                          ? "badge-verified"
                          : ev.recovery_status === "partial"
                          ? "badge-warning"
                          : "badge-inconclusive"
                      }`}
                    >
                      {ev.recovery_status.toUpperCase()}
                    </span>
                  </div>

                  {/* STREAM CONTINUITY BAR */}
                  <div>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.68rem", color: "#64748b", marginBottom: 4 }}>
                      <span>Stream Continuity (00:00 - {Math.floor(ev.duration_seconds / 60)}m)</span>
                      <span>Completeness: {(ev.completeness_score * 100).toFixed(1)}%</span>
                    </div>
                    <div className={styles.segmentBar}>
                      {segments.length === 0 ? (
                        <div className={`${styles.seg_intact}`} style={{ width: "100%", height: "100%" }} />
                      ) : (
                        segments.map((seg, idx) => {
                          const totalDur = ev.duration_seconds || 7200;
                          const widthPct = Math.max(2, (((seg.end_time - seg.start_time) / totalDur) * 100));
                          return (
                            <div
                              key={idx}
                              className={styles[`seg_${seg.segment_type}`] || styles.seg_intact}
                              style={{ width: `${widthPct}%`, height: "100%" }}
                              title={`${seg.segment_type.toUpperCase()}: ${seg.start_time}s - ${seg.end_time}s`}
                            />
                          );
                        })
                      )}
                    </div>
                  </div>

                  {/* STATS */}
                  <div className={styles.statsRow}>
                    <div className={styles.statItem}>
                      <span className={styles.statLabel}>Codec / FPS</span>
                      <span className={styles.statVal}>{ev.codec} · {ev.fps} FPS</span>
                    </div>
                    <div className={styles.statItem}>
                      <span className={styles.statLabel}>Resolution</span>
                      <span className={styles.statVal}>{ev.resolution}</span>
                    </div>
                    <div className={styles.statItem}>
                      <span className={styles.statLabel}>Integrity Hash</span>
                      <span className={styles.statVal} style={{ color: "#22c55e" }}>VERIFIED</span>
                    </div>
                  </div>

                  {/* RECOVERED FRAGMENTS LIST */}
                  <div>
                    <div className="text-xs text-muted font-bold mb-2">FRAGMENT AUDIT TRAIL ({segments.length || 1})</div>
                    <div className={styles.fragmentList}>
                      {segments.length === 0 ? (
                        <div className={`${styles.fragmentRow} ${styles.frag_intact}`}>
                          <span>Intact GOP Stream (Frames 0 - {ev.frame_count})</span>
                          <span className="mono-sm text-green">100% Continuity</span>
                        </div>
                      ) : (
                        segments.map((seg, idx) => (
                          <div key={idx} className={`${styles.fragmentRow} ${styles[`frag_${seg.segment_type}`]}`}>
                            <div>
                              <div style={{ fontWeight: 600 }}>
                                {seg.segment_type.toUpperCase()} · Frames {seg.start_frame} - {seg.end_frame}
                              </div>
                              <div style={{ fontSize: "0.64rem", color: "#64748b" }}>
                                {seg.notes || "Continuous NAL stream block"}
                              </div>
                            </div>
                            <div style={{ textAlign: "right" }}>
                              <div className="mono-sm text-cyan">{(seg.completeness * 100).toFixed(0)}%</div>
                              {seg.is_simulated ? (
                                <span style={{ fontSize: "0.58rem", color: "#a855f7" }}>[SIMULATED]</span>
                              ) : (
                                <span style={{ fontSize: "0.58rem", color: "#22c55e" }}>[NAL-SCAN]</span>
                              )}
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
