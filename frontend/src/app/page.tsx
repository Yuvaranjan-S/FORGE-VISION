"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { login, loadStoredAuth, getUser } from "@/lib/api";
import styles from "./login.module.css";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadStoredAuth();
    if (getUser()) router.replace("/dashboard");
  }, [router]);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setError(""); setLoading(true);
    try {
      await login(username, password);
      router.push("/dashboard");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={styles.root}>
      {/* Background grid */}
      <div className={styles.grid} />

      {/* Scan line */}
      <div className={styles.scanline} />

      <div className={styles.wrapper}>
        {/* Logo */}
        <div className={styles.logo}>
          <div className={styles.logoIcon}>
            <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
              <polygon points="20,3 37,12 37,28 20,37 3,28 3,12" stroke="#f59e0b" strokeWidth="1.5" fill="rgba(245,158,11,0.06)"/>
              <circle cx="20" cy="20" r="6" stroke="#06b6d4" strokeWidth="1.5" fill="rgba(6,182,212,0.1)"/>
              <line x1="20" y1="3" x2="20" y2="14" stroke="#f59e0b" strokeWidth="1"/>
              <line x1="20" y1="26" x2="20" y2="37" stroke="#f59e0b" strokeWidth="1"/>
              <line x1="3" y1="12" x2="14" y2="17" stroke="#f59e0b" strokeWidth="1"/>
              <line x1="26" y1="23" x2="37" y2="28" stroke="#f59e0b" strokeWidth="1"/>
              <line x1="37" y1="12" x2="26" y2="17" stroke="#f59e0b" strokeWidth="1"/>
              <line x1="14" y1="23" x2="3" y2="28" stroke="#f59e0b" strokeWidth="1"/>
            </svg>
          </div>
          <div>
            <div className={styles.logoName}>FORGE-VISION</div>
            <div className={styles.logoTagline}>Forensic Video Intelligence Platform</div>
          </div>
        </div>

        {/* Login card */}
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <div className={styles.cardTitle}>SECURE ACCESS</div>
            <div className={styles.cardSub}>Authorized personnel only — all access is logged</div>
          </div>

          <form onSubmit={handleLogin} className={styles.form}>
            <div className={styles.field}>
              <label className="field-label">Operator ID</label>
              <input
                className="input input-mono"
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                placeholder="username"
                autoComplete="username"
                required
              />
            </div>
            <div className={styles.field}>
              <label className="field-label">Passphrase</label>
              <input
                className="input input-mono"
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••••"
                autoComplete="current-password"
                required
              />
            </div>

            {error && (
              <div className={styles.error}>
                <span>⚠</span> {error}
              </div>
            )}

            <button className="btn btn-primary btn-lg" type="submit" disabled={loading} style={{width:"100%", justifyContent:"center"}}>
              {loading ? <><div className="spinner" /> Authenticating...</> : "→ ENTER WORKSTATION"}
            </button>
          </form>

          <div className={styles.demoHint}>
            <div className={styles.demoTitle}>DEMO CREDENTIALS</div>
            {[
              ["investigator", "forensiq2024", "Investigator"],
              ["supervisor", "supervisor2024", "Supervisor"],
              ["auditor", "auditor2024", "Auditor"],
            ].map(([u, p, role]) => (
              <button key={u} className={styles.demoBtn} onClick={() => { setUsername(u); setPassword(p); }}>
                <span className={styles.demoRole}>{role}</span>
                <span className="mono-sm text-muted">{u} / {p}</span>
              </button>
            ))}
          </div>
        </div>

        <div className={styles.footer}>
          SIH150 — Smart India Hackathon 2024 &nbsp;|&nbsp; FORGE-VISION v1.0.0
        </div>
      </div>
    </div>
  );
}
