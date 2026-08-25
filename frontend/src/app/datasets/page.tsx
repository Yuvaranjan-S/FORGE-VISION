"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import {
  getDatasets, registerDataset, importDataset,
  generateSyntheticDataset, deleteDataset,
  getKaggleSources, getKaggleAuthStatus,
  importKaggleSample, importKaggleDirectory, scanKaggleLocal, getKaggleJobStatus,
  scanDatasetVideos, importDatasetVideos,
  getCases, loadStoredAuth, getUser,
  type Dataset, type KaggleSource, type KaggleAuthStatus, type DirectoryScanResult,
  type KaggleJobStatus, type Case, type DatasetVideoScanResult, type DatasetVideoFile,
} from "@/lib/api";
import styles from "./datasets.module.css";

const SOURCE_CATEGORIES = [
  { id: "ALL", label: "All Datasets" },
  { id: "PUBLIC_RESEARCH_DATASET", label: "Public Research Benchmarks" },
  { id: "AUTHORIZED_DVR_EXPORT", label: "Authorized DVR/NVR Exports" },
  { id: "VENDOR_SAMPLE", label: "Vendor Samples" },
  { id: "SYNTHETIC_DEMO", label: "Synthetic Demos" },
  { id: "USER_UPLOADED", label: "User Uploads" },
];

export default function DatasetsPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<"registered" | "kaggle">("registered");
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [kaggleSources, setKaggleSources] = useState<KaggleSource[]>([]);
  const [kaggleAuth, setKaggleAuth] = useState<KaggleAuthStatus | null>(null);
  const [cases, setCases] = useState<Case[]>([]);
  const [activeCategory, setActiveCategory] = useState("ALL");
  const [loading, setLoading] = useState(true);
  const [_error, setError] = useState<string | null>(null);

  // Modals
  const [showRegisterModal, setShowRegisterModal] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);
  const [selectedDataset, setSelectedDataset] = useState<Dataset | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  // Kaggle Sample Import Modal State
  const [selectedKaggleSource, setSelectedKaggleSource] = useState<KaggleSource | null>(null);
  const [sampleCount, setSampleCount] = useState(5);
  const [sampleTargetCase, setSampleTargetCase] = useState("CASE-DEMO001");
  const [sampleCategory, setSampleCategory] = useState("ALL");
  const [activeJob, setActiveJob] = useState<KaggleJobStatus | null>(null);

  // Import-to-CAM Modal State
  const [showCamImportModal, setShowCamImportModal] = useState(false);
  const [camImportDataset, setCamImportDataset] = useState<Dataset | null>(null);
  const [camScanResult, setCamScanResult] = useState<DatasetVideoScanResult | null>(null);
  const [camScanLoading, setCamScanLoading] = useState(false);
  const [camSelectedFiles, setCamSelectedFiles] = useState<Set<string>>(new Set());
  const [camTargetCase, setCamTargetCase] = useState("CASE-DEMO001");
  const [camJob, setCamJob] = useState<KaggleJobStatus | null>(null);

  // Local Folder Scan Modal State
  const [showLocalScanModal, setShowLocalScanModal] = useState(false);
  const [localDirPath, setLocalDirPath] = useState("");
  const [scanResult, setScanResult] = useState<DirectoryScanResult | null>(null);
  const [scanSelectedSourceKey, setScanSelectedSourceKey] = useState("virat-cctv");
  const [scanTargetCase, setScanTargetCase] = useState("CASE-DEMO001");

  // Register Form State
  const [regName, setRegName] = useState("");
  const [regSourceType, setRegSourceType] = useState("PUBLIC_RESEARCH_DATASET");
  const [regProvider, setRegProvider] = useState("");
  const [regDesc, setRegDesc] = useState("");
  const [regLicense, setRegLicense] = useState("Research / Educational Use");
  const [regRef, setRegRef] = useState("");
  const [regVendor, setRegVendor] = useState("Generic Video Streams");
  const [regFiles] = useState(1);
  const [regCameras] = useState(4);

  // Guided Import Wizard State
  const [importStep, setImportStep] = useState(1);
  const [importName, setImportName] = useState("");
  const [importSourceType, setImportSourceType] = useState("AUTHORIZED_DVR_EXPORT");
  const [importProvider, setImportProvider] = useState("Direct Custody Intake");
  const [importVendor, setImportVendor] = useState("Hikvision");
  const [importCaseId, setImportCaseId] = useState("CASE-DEMO001");
  const [importFiles, setImportFiles] = useState<FileList | null>(null);

  useEffect(() => {
    loadStoredAuth();
    if (!getUser()) {
      router.push("/");
      return;
    }
    loadAllData();
  }, [router]);

  // Background Job Polling — Kaggle Import
  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (activeJob && (activeJob.status === "queued" || activeJob.status === "in_progress")) {
      timer = setInterval(async () => {
        try {
          const updated = await getKaggleJobStatus(activeJob.job_id);
          setActiveJob(updated);
          if (updated.status === "completed") {
            fetchDatasets();
            fetchKaggleSources();
          }
        } catch {
          // ignore poll error
        }
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [activeJob]);

  // Background Job Polling — CAM Import
  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (camJob && (camJob.status === "queued" || camJob.status === "in_progress")) {
      timer = setInterval(async () => {
        try {
          const updated = await getKaggleJobStatus(camJob.job_id);
          setCamJob(updated);
          if (updated.status === "completed") fetchDatasets();
        } catch {
          // ignore poll error
        }
      }, 1200);
    }
    return () => clearInterval(timer);
  }, [camJob]);

  async function loadAllData() {
    try {
      setLoading(true);
      await Promise.all([fetchDatasets(), fetchKaggleSources(), fetchAuthStatus(), fetchCases()]);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load datasets");
    } finally {
      setLoading(false);
    }
  }

  async function fetchDatasets() {
    const data = await getDatasets();
    setDatasets(data);
  }

  async function fetchKaggleSources() {
    const sources = await getKaggleSources();
    setKaggleSources(sources);
  }

  async function fetchAuthStatus() {
    const auth = await getKaggleAuthStatus();
    setKaggleAuth(auth);
  }

  async function fetchCases() {
    const c = await getCases();
    setCases(c);
  }

  async function handleRegister(e: React.FormEvent) {
    e.preventDefault();
    try {
      setActionLoading(true);
      await registerDataset({
        name: regName,
        source_type: regSourceType,
        source_provider: regProvider,
        description: regDesc,
        license: regLicense,
        source_reference: regRef,
        vendor: regVendor,
        file_count: Number(regFiles),
        camera_count: Number(regCameras),
        case_id: "CASE-DEMO001",
        forensic_status: regSourceType === "PUBLIC_RESEARCH_DATASET" ? "RESEARCH_BENCHMARK" : "AUTHENTIC",
      });
      setShowRegisterModal(false);
      resetRegForm();
      fetchDatasets();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to register dataset");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleImportSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!importFiles || importFiles.length === 0) {
      alert("Please select at least one file to import");
      return;
    }
    try {
      setActionLoading(true);
      const fd = new FormData();
      fd.append("dataset_name", importName);
      fd.append("source_type", importSourceType);
      fd.append("source_provider", importProvider);
      fd.append("vendor", importVendor);
      fd.append("case_id", importCaseId);
      for (let i = 0; i < importFiles.length; i++) {
        fd.append("files", importFiles[i]);
      }
      await importDataset(fd);
      setShowImportModal(false);
      setImportStep(1);
      fetchDatasets();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to import dataset files");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleLaunchKaggleSampleImport(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedKaggleSource) return;
    try {
      setActionLoading(true);
      const res = await importKaggleSample(
        selectedKaggleSource.id,
        sampleTargetCase,
        sampleCount,
        sampleCategory
      );
      const jobInitial = await getKaggleJobStatus(res.job_id);
      setActiveJob(jobInitial);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to launch Kaggle import");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleScanDirectory(e: React.FormEvent) {
    e.preventDefault();
    if (!localDirPath.trim()) return;
    try {
      setActionLoading(true);
      const res = await scanKaggleLocal(localDirPath.trim());
      setScanResult(res);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to scan folder");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleImportScannedFiles() {
    if (!scanResult || scanResult.videos.length === 0) return;
    try {
      setActionLoading(true);
      const res = await importKaggleDirectory(
        scanSelectedSourceKey,
        scanResult.directory_path,
        scanTargetCase,
        scanResult.videos.map((v) => v.full_path)
      );
      setShowLocalScanModal(false);
      setScanResult(null);
      const jobInitial = await getKaggleJobStatus(res.job_id);
      setActiveJob(jobInitial);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to import local folder");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleGenerateSynthetic() {
    try {
      setActionLoading(true);
      const res = await generateSyntheticDataset("CASE-DEMO001", "Warehouse", 8);
      alert(`✅ ${res.message} (${res.cameras_created} cameras generated)`);
      fetchDatasets();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to generate synthetic dataset");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Are you sure you want to delete this dataset registration?")) return;
    try {
      await deleteDataset(id);
      fetchDatasets();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to delete dataset");
    }
  }

  // ── IMPORT-TO-CAM HANDLERS ─────────────────────────────────
  async function openCamImportModal(ds: Dataset) {
    setCamImportDataset(ds);
    setCamScanResult(null);
    setCamSelectedFiles(new Set());
    setCamJob(null);
    setCamTargetCase(cases[0]?.id || "CASE-DEMO001");
    setShowCamImportModal(true);
    // Auto-scan on open
    try {
      setCamScanLoading(true);
      const res = await scanDatasetVideos(ds.id);
      setCamScanResult(res);
      // Pre-select available (not yet imported) files
      const available = new Set(res.files.filter(f => !f.already_imported).map(f => f.file_path));
      setCamSelectedFiles(available);
    } catch (err: unknown) {
      alert("Scan failed: " + (err instanceof Error ? err.message : "Error"));
    } finally {
      setCamScanLoading(false);
    }
  }

  function toggleCamFile(filePath: string) {
    setCamSelectedFiles(prev => {
      const next = new Set(prev);
      if (next.has(filePath)) next.delete(filePath); else next.add(filePath);
      return next;
    });
  }

  async function handleCamImport() {
    if (!camImportDataset) return;
    const selectedPaths = Array.from(camSelectedFiles);
    if (selectedPaths.length === 0) { alert("Select at least one video to import."); return; }
    try {
      setActionLoading(true);
      const res = await importDatasetVideos(camImportDataset.id, {
        case_id: camTargetCase,
        selected_files: selectedPaths,
      });
      const jobInitial = await getKaggleJobStatus(res.job_id);
      setCamJob(jobInitial);
    } catch (err: unknown) {
      alert("Import failed: " + (err instanceof Error ? err.message : "Error"));
    } finally {
      setActionLoading(false);
    }
  }

  function resetRegForm() {
    setRegName("");
    setRegProvider("");
    setRegDesc("");
    setRegRef("");
  }

  const filteredDatasets = datasets.filter((ds) => {
    if (activeCategory === "ALL") return true;
    return ds.source_type === activeCategory;
  });

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg-void)" }}>
      <Navbar />

      <main className={styles.container}>
        {/* HEADER */}
        <div className={styles.header}>
          <div className={styles.titleArea}>
            <h1 className={styles.title}>
              <span>📦</span> DATASET LIBRARY & PROVENANCE REGISTRY
            </h1>
            <p className={styles.subtitle}>
              Unified multi-source forensic evidence catalog · Public Kaggle surveillance benchmarks, authorized DVR/NVR exports & synthetic evaluation suites.
            </p>
          </div>

          <div className={styles.actions}>
            <button
              onClick={() => setShowLocalScanModal(true)}
              className="btn btn-secondary btn-sm"
              style={{ fontSize: "0.72rem" }}
            >
              📁 Scan Local Folder
            </button>
            <button
              onClick={() => setShowRegisterModal(true)}
              className="btn btn-secondary btn-sm"
              style={{ fontSize: "0.72rem" }}
            >
              + Register Benchmark
            </button>
            <button
              onClick={() => setShowImportModal(true)}
              className="btn btn-primary btn-sm"
              style={{ fontSize: "0.72rem" }}
            >
              + Ingest Wizard
            </button>
            <button
              onClick={handleGenerateSynthetic}
              className="btn btn-outline btn-sm text-amber"
              style={{ fontSize: "0.72rem" }}
            >
              ⚡ Generate Synthetic Suite
            </button>
          </div>
        </div>

        {/* TOP LEVEL NAVIGATION TABS */}
        <div className={styles.navTabs}>
          <button
            onClick={() => setActiveTab("registered")}
            className={`${styles.navTab} ${activeTab === "registered" ? styles.navTabActive : ""}`}
          >
            <span>📦</span> Registered Ingested Datasets ({datasets.length})
          </button>
          <button
            onClick={() => setActiveTab("kaggle")}
            className={`${styles.navTab} ${activeTab === "kaggle" ? styles.navTabActive : ""}`}
          >
            <span>🌐</span> Kaggle CCTV Sources Catalog ({kaggleSources.length})
          </button>

          {kaggleAuth && (
            <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8, fontSize: "0.72rem" }}>
              <span className="text-muted">Kaggle Auth:</span>
              {kaggleAuth.authenticated ? (
                <span className="badge badge-verified" title={`Authenticated via ${kaggleAuth.auth_source}`}>
                  ● API CONNECTED ({kaggleAuth.username || "User"})
                </span>
              ) : (
                <span className="badge badge-pending" title="Using local benchmark generators and folder ingestion without external API key">
                  ○ OFFLINE / LOCAL SAMPLE MODE
                </span>
              )}
            </div>
          )}
        </div>

        {/* ACTIVE BACKGROUND JOB BANNER */}
        {activeJob && (
          <div className={styles.progressWrap}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.8rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                {activeJob.status === "in_progress" || activeJob.status === "queued" ? (
                  <span className="spinner" style={{ width: 14, height: 14 }} />
                ) : activeJob.status === "completed" ? (
                  <span style={{ color: "#22c55e" }}>✓</span>
                ) : (
                  <span style={{ color: "#ef4444" }}>✕</span>
                )}
                <strong>Job {activeJob.job_id}:</strong>{" "}
                <span className="text-cyan">{activeJob.stage.replace(/_/g, " ").toUpperCase()}</span>
                {activeJob.total_files > 0 && (
                  <span className="text-muted">({activeJob.processed_files}/{activeJob.total_files} files)</span>
                )}
              </div>
              <div className="mono-sm text-amber font-bold">{activeJob.progress_percent}%</div>
            </div>

            <div className={styles.progressBarTrack}>
              <div className={styles.progressBarFill} style={{ width: `${activeJob.progress_percent}%` }} />
            </div>

            {activeJob.status === "completed" && (
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.72rem" }}>
                <span className="text-green font-bold">
                  ✓ Successfully imported {activeJob.imported_count} video(s) with SHA-256 hashes into {activeJob.case_id}.
                </span>
                <button onClick={() => router.push(`/evidence?case_id=${activeJob.case_id}`)} className="btn btn-primary btn-sm" style={{ padding: "2px 8px", fontSize: "0.68rem" }}>
                  View in Evidence Explorer →
                </button>
              </div>
            )}
            {activeJob.status === "failed" && (
              <div className="text-danger" style={{ fontSize: "0.72rem" }}>
                Job failed: {activeJob.error}
              </div>
            )}
          </div>
        )}

        {/* ── TAB 1: REGISTERED DATASETS ───────────────────────── */}
        {activeTab === "registered" && (
          <>
            {/* CATEGORY FILTER BAR */}
            <div className={styles.filterBar}>
              {SOURCE_CATEGORIES.map((cat) => (
                <button
                  key={cat.id}
                  onClick={() => setActiveCategory(cat.id)}
                  className={`${styles.filterChip} ${activeCategory === cat.id ? styles.filterChipActive : ""}`}
                >
                  {cat.label}
                </button>
              ))}
            </div>

            {/* DATASETS GRID */}
            {loading ? (
              <div style={{ padding: 40, textAlign: "center", color: "#64748b" }}>Loading datasets...</div>
            ) : filteredDatasets.length === 0 ? (
              <div style={{ padding: 60, textAlign: "center", color: "#64748b", background: "var(--bg-card)", borderRadius: 8 }}>
                <div style={{ fontSize: "2rem", marginBottom: 8 }}>📭</div>
                <div style={{ fontWeight: 700, color: "#f8fafc" }}>No Datasets Found</div>
                <div style={{ fontSize: "0.75rem", marginTop: 4 }}>
                  Switch to the &quot;Kaggle CCTV Sources Catalog&quot; tab to import real benchmark surveillance footage.
                </div>
              </div>
            ) : (
              <div className={styles.grid}>
                {filteredDatasets.map((ds) => (
                  <div key={ds.id} className={styles.card}>
                    <div className={styles.cardHeader}>
                      <div className={styles.cardTitle}>{ds.name}</div>
                      <span
                        className={`badge ${
                          ds.forensic_status === "AUTHENTIC"
                            ? "badge-verified"
                            : ds.forensic_status === "DEMO_ONLY"
                            ? "badge-simulated"
                            : "badge-inconclusive"
                        }`}
                      >
                        {ds.forensic_status}
                      </span>
                    </div>

                    <div className={styles.cardMeta}>
                      <div className={styles.metaItem}>
                        <span className={styles.metaLabel}>Source Type</span>
                        <span className={styles.metaValue} style={{ color: "#06b6d4" }}>
                          {ds.source_type.replace(/_/g, " ")}
                        </span>
                      </div>
                      <div className={styles.metaItem}>
                        <span className={styles.metaLabel}>Vendor / OEM</span>
                        <span className={styles.metaValue}>{ds.vendor}</span>
                      </div>
                      <div className={styles.metaItem}>
                        <span className={styles.metaLabel}>Cameras / Files</span>
                        <span className={styles.metaValue}>{ds.camera_count} Cams · {ds.file_count} Files</span>
                      </div>
                      <div className={styles.metaItem}>
                        <span className={styles.metaLabel}>Total Size</span>
                        <span className={styles.metaValue}>
                          {(ds.total_size_bytes / (1024 * 1024)).toFixed(1)} MB
                        </span>
                      </div>
                    </div>

                    <p className={styles.description}>{ds.description || "No description provided."}</p>

                    <div className={styles.cardFooter}>
                      <div className={styles.hashTag}>
                        SHA256: {ds.sha256 ? ds.sha256.slice(0, 16) + "..." : "COMPUTING"}
                      </div>
                      <div style={{ display: "flex", gap: 6 }}>
                        <button
                          onClick={() => setSelectedDataset(ds)}
                          className="btn btn-ghost btn-sm"
                          style={{ fontSize: "0.68rem", padding: "2px 8px" }}
                        >
                          Provenance
                        </button>
                        {ds.case_id && (
                          <button
                            onClick={() => router.push(`/case/${ds.case_id}`)}
                            className="btn btn-outline btn-sm"
                            style={{ fontSize: "0.68rem", padding: "2px 8px" }}
                          >
                            Open Case
                          </button>
                        )}
                        <button
                          onClick={() => openCamImportModal(ds)}
                          className="btn btn-primary btn-sm"
                          style={{ fontSize: "0.68rem", padding: "2px 8px" }}
                          title="Import videos from this dataset into CAM / Evidence"
                        >
                          📹 Import to CAM
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {/* ── TAB 2: KAGGLE CCTV SOURCES CATALOG ───────────────── */}
        {activeTab === "kaggle" && (
          <div className={styles.grid}>
            {kaggleSources.map((src) => (
              <div key={src.id} className={styles.kaggleSourceCard}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
                  <div>
                    <div style={{ fontSize: "1.05rem", fontWeight: 700, color: "#f8fafc" }}>{src.name}</div>
                    <div className="mono-sm text-cyan" style={{ fontSize: "0.68rem", marginTop: 2 }}>
                      {src.kaggle_dataset_identifier}
                    </div>
                  </div>
                  <span
                    className={`badge ${
                      src.status === "IMPORTED"
                        ? styles.statusImported
                        : src.status === "AVAILABLE"
                        ? styles.statusAvailable
                        : styles.statusAuthRequired
                    }`}
                  >
                    {src.status.replace(/_/g, " ")}
                  </span>
                </div>

                <div className={styles.cardMeta}>
                  <div className={styles.metaItem}>
                    <span className={styles.metaLabel}>Provider / Lab</span>
                    <span className={styles.metaValue}>{src.provider}</span>
                  </div>
                  <div className={styles.metaItem}>
                    <span className={styles.metaLabel}>License</span>
                    <span className={styles.metaValue} style={{ color: "#f59e0b" }}>{src.license}</span>
                  </div>
                </div>

                <p className={styles.description}>{src.description}</p>

                <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                  {src.categories.map((cat, i) => (
                    <span key={i} className={styles.categoryTag}>
                      • {cat}
                    </span>
                  ))}
                </div>

                <div className={styles.cardFooter}>
                  <a
                    href={src.source_reference}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn btn-ghost btn-sm"
                    style={{ fontSize: "0.68rem", padding: "2px 8px" }}
                  >
                    ↗ View Source
                  </a>

                  <button
                    onClick={() => {
                      setSelectedKaggleSource(src);
                      setSampleCategory("ALL");
                    }}
                    className="btn btn-primary btn-sm"
                    style={{ fontSize: "0.72rem", padding: "4px 12px" }}
                  >
                    ⚡ Import Sample
                  </button>
                  {src.status === "IMPORTED" && src.imported_dataset_id && (
                    <button
                      onClick={() => {
                        const ds = datasets.find(d => d.id === src.imported_dataset_id);
                        if (ds) openCamImportModal(ds);
                      }}
                      className="btn btn-secondary btn-sm"
                      style={{ fontSize: "0.72rem", padding: "4px 12px" }}
                    >
                      📹 Import to CAM
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* KAGGLE SAMPLE IMPORT MODAL */}
        {selectedKaggleSource && (
          <div className={styles.modalOverlay} onClick={() => setSelectedKaggleSource(null)}>
            <div className={styles.modalContent} onClick={(e) => e.stopPropagation()}>
              <div className={styles.modalHeader}>
                <h3 className={styles.modalTitle}>
                  Import Kaggle Surveillance Footage · {selectedKaggleSource.name}
                </h3>
                <button onClick={() => setSelectedKaggleSource(null)} className={styles.closeBtn}>✕</button>
              </div>

              <form onSubmit={handleLaunchKaggleSampleImport} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                <div style={{ background: "rgba(6, 182, 212, 0.08)", border: "1px solid rgba(6, 182, 212, 0.2)", padding: 12, borderRadius: 6, fontSize: "0.74rem" }}>
                  <strong>Dataset Identifier:</strong> <span className="mono-sm text-cyan">{selectedKaggleSource.kaggle_dataset_identifier}</span><br />
                  <strong>License Terms:</strong> <span className="text-amber">{selectedKaggleSource.license}</span><br />
                  <strong>Provenance Rule:</strong> Ingested footage will be designated as <code>PUBLIC_RESEARCH_DATASET</code> with <code>Vendor: Unknown</code>.
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                  <div className={styles.formGroup}>
                    <label className={styles.formLabel}>Number of Sample Videos</label>
                    <select
                      value={sampleCount}
                      onChange={(e) => setSampleCount(Number(e.target.value))}
                      className={styles.select}
                    >
                      <option value={4}>4 Sample Videos (~35 MB)</option>
                      <option value={8}>8 Sample Videos (~70 MB)</option>
                      <option value={15}>15 Sample Videos (~130 MB)</option>
                      <option value={25}>25 Sample Videos (~220 MB)</option>
                    </select>
                  </div>

                  <div className={styles.formGroup}>
                    <label className={styles.formLabel}>Target Case</label>
                    <select
                      value={sampleTargetCase}
                      onChange={(e) => setSampleTargetCase(e.target.value)}
                      className={styles.select}
                    >
                      {cases.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.id} — {c.title}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className={styles.formGroup}>
                  <label className={styles.formLabel}>Scenario / Category Filter</label>
                  <select
                    value={sampleCategory}
                    onChange={(e) => setSampleCategory(e.target.value)}
                    className={styles.select}
                  >
                    <option value="ALL">All Categories ({selectedKaggleSource.categories.join(", ")})</option>
                    {selectedKaggleSource.categories.map((c, i) => (
                      <option key={i} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </div>

                <div style={{ background: "rgba(2, 6, 23, 0.6)", padding: 10, borderRadius: 6, fontSize: "0.72rem", color: "#94a3b8" }}>
                  ✓ Computes true cryptographic SHA-256, SHA-512, MD5, SHA3-256 on local files.<br />
                  ✓ Extracts FFprobe container metadata (resolution, fps, codec, duration).<br />
                  ✓ Generates OpenCV surveillance video thumbnail.<br />
                  ✓ Appends <code>DATASET_IMPORTED</code> event to chain-of-custody ledger.
                </div>

                <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 6 }}>
                  <button type="button" onClick={() => setSelectedKaggleSource(null)} className="btn btn-ghost btn-sm">
                    Cancel
                  </button>
                  <button type="submit" disabled={actionLoading} className="btn btn-primary btn-sm">
                    {actionLoading ? "Queueing Job..." : "⚡ Ingest Sample Benchmark"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* LOCAL FOLDER SCANNER MODAL */}
        {showLocalScanModal && (
          <div className={styles.modalOverlay} onClick={() => setShowLocalScanModal(false)}>
            <div className={styles.modalContent} onClick={(e) => e.stopPropagation()}>
              <div className={styles.modalHeader}>
                <h3 className={styles.modalTitle}>Scan & Import Local Kaggle Dataset Folder</h3>
                <button onClick={() => setShowLocalScanModal(false)} className={styles.closeBtn}>✕</button>
              </div>

              <form onSubmit={handleScanDirectory} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <div className={styles.formGroup}>
                  <label className={styles.formLabel}>Local Directory Path</label>
                  <div style={{ display: "flex", gap: 8 }}>
                    <input
                      type="text"
                      required
                      placeholder="e.g. data/kaggle/ucf_crime or C:/Datasets/VIRAT"
                      value={localDirPath}
                      onChange={(e) => setLocalDirPath(e.target.value)}
                      className={styles.input}
                      style={{ flex: 1 }}
                    />
                    <button type="submit" disabled={actionLoading} className="btn btn-secondary btn-sm">
                      {actionLoading ? "Scanning..." : "🔍 Scan"}
                    </button>
                  </div>
                </div>

                {scanResult && scanResult.valid && (
                  <div style={{ background: "var(--bg-deep)", padding: 12, borderRadius: 6, display: "flex", flexDirection: "column", gap: 8, fontSize: "0.75rem" }}>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                      <div><strong>Videos Found:</strong> <span className="text-cyan font-bold">{scanResult.video_count}</span></div>
                      <div><strong>Images Found:</strong> <span className="text-purple font-bold">{scanResult.image_count}</span></div>
                      <div><strong>Annotations / XML:</strong> <span className="text-amber font-bold">{scanResult.annotation_count}</span></div>
                      <div><strong>Total Size:</strong> {(scanResult.total_size_bytes / (1024 * 1024)).toFixed(1)} MB</div>
                    </div>

                    <div className={styles.formGroup} style={{ marginTop: 6 }}>
                      <label className={styles.formLabel}>Associate Kaggle Benchmark Catalog</label>
                      <select
                        value={scanSelectedSourceKey}
                        onChange={(e) => setScanSelectedSourceKey(e.target.value)}
                        className={styles.select}
                      >
                        {kaggleSources.map((s) => (
                          <option key={s.id} value={s.id}>
                            {s.name}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className={styles.formGroup}>
                      <label className={styles.formLabel}>Target Case</label>
                      <select
                        value={scanTargetCase}
                        onChange={(e) => setScanTargetCase(e.target.value)}
                        className={styles.select}
                      >
                        {cases.map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.id} — {c.title}
                          </option>
                        ))}
                      </select>
                    </div>

                    <button
                      type="button"
                      onClick={handleImportScannedFiles}
                      disabled={scanResult.video_count === 0 || actionLoading}
                      className="btn btn-primary btn-sm"
                      style={{ marginTop: 8 }}
                    >
                      Ingest {scanResult.video_count} Scanned Video(s) Into Case →
                    </button>
                  </div>
                )}
              </form>
            </div>
          </div>
        )}

        {/* PROVENANCE DETAIL MODAL */}
        {selectedDataset && (
          <div className={styles.modalOverlay} onClick={() => setSelectedDataset(null)}>
            <div className={styles.modalContent} onClick={(e) => e.stopPropagation()}>
              <div className={styles.modalHeader}>
                <h3 className={styles.modalTitle}>Dataset Provenance & Source Metadata</h3>
                <button onClick={() => setSelectedDataset(null)} className={styles.closeBtn}>✕</button>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 12, fontSize: "0.8rem" }}>
                <div style={{ display: "grid", gridTemplateColumns: "140px 1fr", gap: 8, background: "var(--bg-deep)", padding: 12, borderRadius: 6 }}>
                  <span className="text-muted font-bold">Dataset ID:</span>
                  <span className="mono-sm text-cyan">{selectedDataset.id}</span>

                  <span className="text-muted font-bold">Name:</span>
                  <span>{selectedDataset.name}</span>

                  <span className="text-muted font-bold">Source Type:</span>
                  <span className="text-amber font-bold">{selectedDataset.source_type}</span>

                  <span className="text-muted font-bold">Provider / Author:</span>
                  <span>{selectedDataset.source_provider}</span>

                  <span className="text-muted font-bold">License / Terms:</span>
                  <span>{selectedDataset.license}</span>

                  <span className="text-muted font-bold">Source Reference:</span>
                  <span className="mono-sm">{selectedDataset.source_reference || "Direct Acquisition"}</span>

                  <span className="text-muted font-bold">Collection Method:</span>
                  <span>{selectedDataset.collection_method || "Forensic Image Intake"}</span>

                  <span className="text-muted font-bold">Collection Date:</span>
                  <span>{selectedDataset.collection_date || selectedDataset.created_at.slice(0, 10)}</span>

                  <span className="text-muted font-bold">SHA-256 Hash:</span>
                  <span className="mono-sm text-green">{selectedDataset.sha256}</span>
                </div>

                <div style={{ background: "rgba(245, 158, 11, 0.05)", border: "1px solid rgba(245, 158, 11, 0.2)", padding: 10, borderRadius: 6, fontSize: "0.72rem", color: "#cbd5e1" }}>
                  <strong>Forensic Integrity Note:</strong> Original bytes are preserved read-only in accordance with digital forensics standards.
                  All analytical workflows (YOLO detection, ELA, scene-change) operate exclusively on working copy derivatives.
                </div>
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
                <button onClick={() => handleDelete(selectedDataset.id)} className="btn btn-ghost text-danger btn-sm">
                  Delete Registration
                </button>
                <button onClick={() => setSelectedDataset(null)} className="btn btn-secondary btn-sm">
                  Close
                </button>
              </div>
            </div>
          </div>
        )}

        {/* REGISTER BENCHMARK MODAL */}
        {showRegisterModal && (
          <div className={styles.modalOverlay} onClick={() => setShowRegisterModal(false)}>
            <div className={styles.modalContent} onClick={(e) => e.stopPropagation()}>
              <div className={styles.modalHeader}>
                <h3 className={styles.modalTitle}>Register Public Research / Lab Dataset</h3>
                <button onClick={() => setShowRegisterModal(false)} className={styles.closeBtn}>✕</button>
              </div>

              <form onSubmit={handleRegister} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <div className={styles.formGroup}>
                  <label className={styles.formLabel}>Dataset Name *</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. VIRAT Video Dataset Release 2.0"
                    value={regName}
                    onChange={(e) => setRegName(e.target.value)}
                    className={styles.input}
                  />
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                  <div className={styles.formGroup}>
                    <label className={styles.formLabel}>Source Category</label>
                    <select
                      value={regSourceType}
                      onChange={(e) => setRegSourceType(e.target.value)}
                      className={styles.select}
                    >
                      <option value="PUBLIC_RESEARCH_DATASET">Public Research Benchmark</option>
                      <option value="AUTHORIZED_DVR_EXPORT">Authorized DVR Export</option>
                      <option value="VENDOR_SAMPLE">Vendor Sample</option>
                      <option value="TEAM_COLLECTED_TEST_DATA">Team Collected Test Data</option>
                    </select>
                  </div>

                  <div className={styles.formGroup}>
                    <label className={styles.formLabel}>Vendor / OEM</label>
                    <input
                      type="text"
                      placeholder="e.g. Unknown / Hikvision"
                      value={regVendor}
                      onChange={(e) => setRegVendor(e.target.value)}
                      className={styles.input}
                    />
                  </div>
                </div>

                <div className={styles.formGroup}>
                  <label className={styles.formLabel}>Source Provider / University / Agency *</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. University of Central Florida / DARPA"
                    value={regProvider}
                    onChange={(e) => setRegProvider(e.target.value)}
                    className={styles.input}
                  />
                </div>

                <div className={styles.formGroup}>
                  <label className={styles.formLabel}>License & Terms</label>
                  <input
                    type="text"
                    placeholder="e.g. Creative Commons / Academic Research Use"
                    value={regLicense}
                    onChange={(e) => setRegLicense(e.target.value)}
                    className={styles.input}
                  />
                </div>

                <div className={styles.formGroup}>
                  <label className={styles.formLabel}>Dataset Description</label>
                  <textarea
                    rows={2}
                    placeholder="Brief description of footage resolution, scenarios, anomaly classes..."
                    value={regDesc}
                    onChange={(e) => setRegDesc(e.target.value)}
                    className={styles.textarea}
                  />
                </div>

                <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 8 }}>
                  <button type="button" onClick={() => setShowRegisterModal(false)} className="btn btn-ghost btn-sm">
                    Cancel
                  </button>
                  <button type="submit" className="btn btn-primary btn-sm" disabled={actionLoading}>
                    {actionLoading ? "Registering..." : "Register Dataset"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* 3-STEP GUIDED INGESTION WIZARD MODAL */}
        {showImportModal && (
          <div className={styles.modalOverlay} onClick={() => setShowImportModal(false)}>
            <div className={styles.modalContent} onClick={(e) => e.stopPropagation()}>
              <div className={styles.modalHeader}>
                <h3 className={styles.modalTitle}>Guided Forensic Dataset Ingestion Wizard</h3>
                <button onClick={() => setShowImportModal(false)} className={styles.closeBtn}>✕</button>
              </div>

              <div className={styles.stepIndicator}>
                <div className={`${styles.step} ${importStep >= 1 ? styles.stepActive : ""}`} />
                <div className={`${styles.step} ${importStep >= 2 ? styles.stepActive : ""}`} />
                <div className={`${styles.step} ${importStep >= 3 ? styles.stepActive : ""}`} />
              </div>

              {/* Step 1: Source Info */}
              {importStep === 1 && (
                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  <div className="text-xs text-amber font-bold">STEP 1: SOURCE PROVENANCE & IDENTIFICATION</div>
                  <div className={styles.formGroup}>
                    <label className={styles.formLabel}>Dataset Name *</label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. CCTV Batch Acquisition - Sector 4"
                      value={importName}
                      onChange={(e) => setImportName(e.target.value)}
                      className={styles.input}
                    />
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                    <div className={styles.formGroup}>
                      <label className={styles.formLabel}>Source Category</label>
                      <select
                        value={importSourceType}
                        onChange={(e) => setImportSourceType(e.target.value)}
                        className={styles.select}
                      >
                        <option value="AUTHORIZED_DVR_EXPORT">Authorized DVR/NVR Export</option>
                        <option value="AUTHORIZED_CCTV_RECORDING">Authorized CCTV Recording</option>
                        <option value="VENDOR_SAMPLE">Vendor Sample</option>
                        <option value="USER_UPLOADED">User Uploaded</option>
                      </select>
                    </div>

                    <div className={styles.formGroup}>
                      <label className={styles.formLabel}>Target Case</label>
                      <select
                        value={importCaseId}
                        onChange={(e) => setImportCaseId(e.target.value)}
                        className={styles.select}
                      >
                        {cases.map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.id} — {c.title}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 8 }}>
                    <button type="button" onClick={() => setShowImportModal(false)} className="btn btn-ghost btn-sm">Cancel</button>
                    <button
                      type="button"
                      disabled={!importName}
                      onClick={() => setImportStep(2)}
                      className="btn btn-primary btn-sm"
                    >
                      Next: Select Files →
                    </button>
                  </div>
                </div>
              )}

              {/* Step 2: File Selection */}
              {importStep === 2 && (
                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  <div className="text-xs text-amber font-bold">STEP 2: FILE SELECTION & TRIPLE-HASH ENFORCEMENT</div>
                  <div style={{ border: "2px dashed #334155", borderRadius: 8, padding: 24, textAlign: "center", background: "var(--bg-deep)" }}>
                    <input
                      type="file"
                      multiple
                      accept="video/*,.mp4,.avi,.mkv,.dav,.dat,.bin"
                      onChange={(e) => setImportFiles(e.target.files)}
                      style={{ display: "block", margin: "0 auto", color: "#94a3b8" }}
                    />
                    <div style={{ fontSize: "0.72rem", color: "#64748b", marginTop: 8 }}>
                      Supports MP4, AVI, MKV, MOV, DAV, DAT, BIN containers.
                    </div>
                  </div>

                  <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8 }}>
                    <button type="button" onClick={() => setImportStep(1)} className="btn btn-ghost btn-sm">← Back</button>
                    <button
                      type="button"
                      disabled={!importFiles || importFiles.length === 0}
                      onClick={() => setImportStep(3)}
                      className="btn btn-primary btn-sm"
                    >
                      Next: Review & Ingest →
                    </button>
                  </div>
                </div>
              )}

              {/* Step 3: Review & Ingest */}
              {importStep === 3 && (
                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  <div className="text-xs text-amber font-bold">STEP 3: FORENSIC SEALING & INGESTION CONFIRMATION</div>
                  <div style={{ background: "var(--bg-deep)", padding: 12, borderRadius: 6, fontSize: "0.75rem", display: "flex", flexDirection: "column", gap: 6 }}>
                    <div><strong>Dataset Name:</strong> {importName}</div>
                    <div><strong>Category:</strong> {importSourceType}</div>
                    <div><strong>Target Case:</strong> {importCaseId}</div>
                    <div><strong>Files to Ingest:</strong> {importFiles?.length} files</div>
                    <div className="text-green">✓ Automated MD5, SHA-256, SHA3-256 calculation enabled</div>
                    <div className="text-green">✓ Read-only write-blocking store enforcement active</div>
                  </div>

                  <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8 }}>
                    <button type="button" onClick={() => setImportStep(2)} className="btn btn-ghost btn-sm">← Back</button>
                    <button
                      type="button"
                      onClick={handleImportSubmit}
                      disabled={actionLoading}
                      className="btn btn-primary btn-sm"
                    >
                      {actionLoading ? "Sealing & Ingesting..." : "Ingest & Calculate Hashes"}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </main>

      {/* ── IMPORT-TO-CAM MODAL ─────────────────────────────────── */}
      {showCamImportModal && camImportDataset && (
        <div className={styles.modalOverlay} onClick={() => { setShowCamImportModal(false); setCamJob(null); }}>
          <div className={styles.modalContent} onClick={e => e.stopPropagation()} style={{ maxWidth: 680, maxHeight: "88vh", overflowY: "auto" }}>
            <div className={styles.modalHeader}>
              <h3 className={styles.modalTitle}>📹 Import Videos to CAM — {camImportDataset.name.slice(0, 50)}</h3>
              <button onClick={() => { setShowCamImportModal(false); setCamJob(null); }} className={styles.closeBtn}>✕</button>
            </div>

            {/* Provenance notice */}
            <div style={{ background: "rgba(6,182,212,0.07)", border: "1px solid rgba(6,182,212,0.2)", padding: "10px 14px", borderRadius: 6, fontSize: "0.73rem", marginBottom: 14 }}>
              <strong>Forensic Rule:</strong> All videos will be assigned <code>vendor = &quot;Unknown&quot;</code> and <code>source_type = &quot;PUBLIC_RESEARCH_DATASET&quot;</code>.
              Camera IDs will be generated as <code>CAM-KAG-NNN</code>. SHA-256 duplicate detection prevents re-import.
            </div>

            {/* Scan loading */}
            {camScanLoading && (
              <div style={{ padding: "24px 0", textAlign: "center", color: "#64748b" }}>
                <div className="spinner" style={{ width: 24, height: 24, margin: "0 auto 8px" }} />
                Scanning dataset folder for video files...
              </div>
            )}

            {/* Scan results */}
            {camScanResult && !camScanLoading && !camJob && (
              <>
                {/* Stats pills */}
                <div style={{ display: "flex", gap: 10, marginBottom: 14, flexWrap: "wrap" }}>
                  <span style={{ background: "rgba(6,182,212,0.12)", border: "1px solid rgba(6,182,212,0.3)", borderRadius: 6, padding: "4px 12px", fontSize: "0.72rem", color: "#38bdf8", fontWeight: 700 }}>
                    Total: {camScanResult.total}
                  </span>
                  <span style={{ background: "rgba(34,197,94,0.12)", border: "1px solid rgba(34,197,94,0.3)", borderRadius: 6, padding: "4px 12px", fontSize: "0.72rem", color: "#4ade80", fontWeight: 700 }}>
                    Available: {camScanResult.available}
                  </span>
                  <span style={{ background: "rgba(100,116,139,0.15)", border: "1px solid rgba(100,116,139,0.3)", borderRadius: 6, padding: "4px 12px", fontSize: "0.72rem", color: "#94a3b8", fontWeight: 700 }}>
                    Already Imported: {camScanResult.already_imported}
                  </span>
                  <span style={{ background: "rgba(139,92,246,0.12)", border: "1px solid rgba(139,92,246,0.3)", borderRadius: 6, padding: "4px 12px", fontSize: "0.72rem", color: "#a78bfa", fontWeight: 700 }}>
                    Selected: {camSelectedFiles.size}
                  </span>
                </div>

                {/* File table */}
                <div style={{ maxHeight: 280, overflowY: "auto", border: "1px solid rgba(255,255,255,0.07)", borderRadius: 6, marginBottom: 14 }}>
                  <table style={{ width: "100%", fontSize: "0.72rem", borderCollapse: "collapse" }}>
                    <thead>
                      <tr style={{ background: "rgba(2,6,23,0.8)", borderBottom: "1px solid rgba(255,255,255,0.07)" }}>
                        <th style={{ padding: "7px 10px", textAlign: "left", color: "#475569", fontWeight: 700, width: 36 }}>
                          <input type="checkbox"
                            checked={camSelectedFiles.size === camScanResult.files.filter(f => !f.already_imported).length && camSelectedFiles.size > 0}
                            onChange={e => {
                              if (e.target.checked) setCamSelectedFiles(new Set(camScanResult.files.filter(f => !f.already_imported).map(f => f.file_path)));
                              else setCamSelectedFiles(new Set());
                            }}
                          />
                        </th>
                        <th style={{ padding: "7px 10px", textAlign: "left", color: "#475569", fontWeight: 700 }}>Filename</th>
                        <th style={{ padding: "7px 10px", textAlign: "right", color: "#475569", fontWeight: 700 }}>Size</th>
                        <th style={{ padding: "7px 10px", textAlign: "center", color: "#475569", fontWeight: 700 }}>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {camScanResult.files.map((f: DatasetVideoFile) => (
                        <tr key={f.file_path} style={{ borderBottom: "1px solid rgba(255,255,255,0.04)", background: f.already_imported ? "rgba(34,197,94,0.04)" : "transparent" }}>
                          <td style={{ padding: "6px 10px" }}>
                            <input type="checkbox" disabled={f.already_imported} checked={camSelectedFiles.has(f.file_path)} onChange={() => toggleCamFile(f.file_path)} />
                          </td>
                          <td style={{ padding: "6px 10px", color: f.already_imported ? "#475569" : "#e2e8f0", fontFamily: "monospace" }}>{f.filename}</td>
                          <td style={{ padding: "6px 10px", textAlign: "right", color: "#64748b" }}>{(f.file_size_bytes / (1024 * 1024)).toFixed(1)} MB</td>
                          <td style={{ padding: "6px 10px", textAlign: "center" }}>
                            {f.already_imported
                              ? <span style={{ color: "#22c55e", fontSize: "0.62rem", fontWeight: 700 }}>✓ IMPORTED {f.existing_camera_id ? `(${f.existing_camera_id})` : ""}</span>
                              : <span style={{ color: "#94a3b8", fontSize: "0.62rem" }}>—</span>
                            }
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Case selector */}
                <div className={styles.formGroup} style={{ marginBottom: 14 }}>
                  <label className={styles.formLabel}>Target Case</label>
                  <select value={camTargetCase} onChange={e => setCamTargetCase(e.target.value)} className={styles.select}>
                    {cases.map(c => <option key={c.id} value={c.id}>{c.id} — {c.title}</option>)}
                  </select>
                </div>

                <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
                  <button className="btn btn-ghost btn-sm" onClick={() => setShowCamImportModal(false)}>Cancel</button>
                  <button
                    className="btn btn-secondary btn-sm"
                    disabled={camSelectedFiles.size === 0 || actionLoading}
                    onClick={() => {
                      const avail = camScanResult.files.filter(f => !f.already_imported).map(f => f.file_path);
                      setCamSelectedFiles(new Set(avail.slice(0, 5)));
                    }}
                  >
                    Select 5 Samples
                  </button>
                  <button className="btn btn-primary btn-sm" onClick={handleCamImport} disabled={camSelectedFiles.size === 0 || actionLoading}>
                    {actionLoading ? "Launching…" : `Import ${camSelectedFiles.size} Video${camSelectedFiles.size !== 1 ? "s" : ""} to CAM`}
                  </button>
                </div>
              </>
            )}

            {/* Job Progress */}
            {camJob && (camJob.status === "in_progress" || camJob.status === "queued") && (
              <div style={{ padding: "16px 0" }}>
                <div style={{ fontWeight: 700, color: "#f8fafc", marginBottom: 8, fontSize: "0.85rem" }}>⚙️ Importing Videos to CAM / Evidence...</div>
                <div style={{ background: "rgba(2,6,23,0.6)", borderRadius: 6, height: 8, overflow: "hidden", marginBottom: 8 }}>
                  <div style={{ background: "linear-gradient(90deg, #06b6d4, #3b82f6)", height: "100%", width: `${camJob.progress_percent}%`, transition: "width 0.5s" }} />
                </div>
                <div style={{ fontSize: "0.73rem", color: "#94a3b8", marginBottom: 6 }}>
                  {camJob.current_file && <span>📄 {camJob.current_file}</span>}
                </div>
                <div style={{ display: "flex", gap: 16, fontSize: "0.73rem" }}>
                  <span style={{ color: "#22c55e" }}>✓ Imported: {camJob.imported_count}</span>
                  <span style={{ color: "#f59e0b" }}>⊘ Skipped: {camJob.skipped_count}</span>
                  <span style={{ color: "#94a3b8" }}>⟳ Total: {camJob.total_files}</span>
                  {camJob.failed_count > 0 && <span style={{ color: "#ef4444" }}>✕ Failed: {camJob.failed_count}</span>}
                </div>
              </div>
            )}

            {/* Completion */}
            {camJob && camJob.status === "completed" && (
              <div style={{ padding: "16px 0", textAlign: "center" }}>
                <div style={{ fontSize: "1.8rem", marginBottom: 8 }}>✅</div>
                <div style={{ fontWeight: 700, color: "#4ade80", fontSize: "0.95rem", marginBottom: 6 }}>Import Complete</div>
                <div style={{ fontSize: "0.78rem", color: "#94a3b8", marginBottom: 12 }}>
                  {camJob.imported_count} video{camJob.imported_count !== 1 ? "s" : ""} imported ·{" "}
                  {camJob.skipped_count} duplicate{camJob.skipped_count !== 1 ? "s" : ""} skipped ·{" "}
                  {camJob.failed_count} failed
                </div>
                <button onClick={() => { setShowCamImportModal(false); setCamJob(null); router.push("/evidence"); }} className="btn btn-primary">
                  View in CAM / Evidence →
                </button>
              </div>
            )}

            {/* Failed state */}
            {camJob && camJob.status === "failed" && (
              <div style={{ padding: "16px 0", textAlign: "center" }}>
                <div style={{ color: "#f87171", fontWeight: 700, marginBottom: 8 }}>Import Failed</div>
                <div style={{ fontSize: "0.75rem", color: "#64748b", marginBottom: 12 }}>{camJob.error}</div>
                <button onClick={() => setCamJob(null)} className="btn btn-ghost btn-sm">Try Again</button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
