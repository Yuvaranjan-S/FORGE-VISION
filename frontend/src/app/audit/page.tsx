"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import { getAuditLogs, loadStoredAuth, getUser, type AuditLog } from "@/lib/api";
import styles from "./audit.module.css";

export default function AuditLogsPage() {
  const router = useRouter();
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [actionFilter, setActionFilter] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadStoredAuth();
    if (!getUser()) {
      router.push("/");
      return;
    }
    fetchLogs();
  }, [router, actionFilter]);

  async function fetchLogs() {
    try {
      setLoading(true);
      const res = await getAuditLogs(undefined, actionFilter || undefined, 100);
      setLogs(res.logs || []);
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
              <span>🛡️</span> FORENSIC AUDIT LOG & COMPLIANCE INSPECTION
            </h1>
            <p className={styles.subtitle}>
              Immutable record of every evidence intake, hash validation, parser execution, and report export.
            </p>
          </div>

          <div style={{ display: "flex", gap: 10 }}>
            <input
              type="text"
              placeholder="Filter by action (e.g. ingest, report)..."
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
              className="input-sm"
              style={{ background: "#050811", border: "1px solid #1e293b", color: "#f8fafc", padding: "6px 12px", borderRadius: 4, fontSize: "0.78rem" }}
            />
          </div>
        </div>

        {/* LOG TABLE */}
        <div className={styles.tableWrap}>
          <div className={styles.tableHead}>
            <span>Timestamp</span>
            <span>Operator</span>
            <span>Role</span>
            <span>Action & Detail</span>
            <span>Resource</span>
          </div>

          {loading ? (
            <div style={{ padding: 40, textAlign: "center", color: "#64748b" }}>Loading audit records...</div>
          ) : logs.length === 0 ? (
            <div style={{ padding: 40, textAlign: "center", color: "#64748b" }}>No audit log records found.</div>
          ) : (
            logs.map((log) => (
              <div key={log.id} className={styles.tableRow}>
                <span className="mono-sm text-muted">{log.timestamp?.slice(0, 19).replace("T", " ")}</span>
                <span style={{ fontWeight: 600, color: "#f8fafc" }}>{log.full_name || log.username || log.user_id}</span>
                <span className={`badge ${log.role === "supervisor" ? "badge-warning" : "badge-verified"}`} style={{ fontSize: "0.62rem" }}>
                  {(log.role || "USER").toUpperCase()}
                </span>
                <div>
                  <div className="mono-sm text-amber font-bold">{log.action}</div>
                  <div style={{ fontSize: "0.7rem", color: "#94a3b8" }}>{log.detail || "-"}</div>
                </div>
                <span className="mono-sm text-cyan">{log.resource || "SYSTEM"}</span>
              </div>
            ))
          )}
        </div>
      </main>
    </div>
  );
}
