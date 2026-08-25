"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import {
  getCameraTopology, getCases, getTimeline,
  loadStoredAuth, getUser,
  type CameraNode, type Case, type ReidHop,
} from "@/lib/api";
import styles from "./map.module.css";

export default function CameraMapPage() {
  const router = useRouter();
  const [cases, setCases] = useState<Case[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState("CASE-DEMO001");
  const [nodes, setNodes] = useState<CameraNode[]>([]);
  const [selectedNode, setSelectedNode] = useState<CameraNode | null>(null);
  const [hops, setHops] = useState<ReidHop[]>([]);
  const [_loading, setLoading] = useState(true);

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
      const topData = await getCameraTopology(selectedCaseId);
      setNodes(topData.nodes || []);
      if (topData.nodes && topData.nodes.length > 0) {
        setSelectedNode(topData.nodes[0]);
      }
      const tlData = await getTimeline(selectedCaseId);
      setHops(tlData.reid_hops || []);
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
              <span>🗺️</span> CAMERA TOPOLOGY & SPATIAL CORRELATION
            </h1>
            <p className={styles.subtitle}>
              Physical camera network visualization · Spatial proximity transitions · Cross-camera movement tracking.
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

        {/* WORKSPACE */}
        <div className={styles.mapWorkspace}>
          {/* MAP CANVAS */}
          <div className={styles.canvasWrap}>
            <div className={styles.gridOverlay} />

            {/* SVG Connecting Lines */}
            <svg style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none", zIndex: 5 }}>
              <defs>
                <marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                  <path d="M 0 0 L 10 5 L 0 10 z" fill="#f59e0b" />
                </marker>
              </defs>
              {nodes.map((n) => {
                const conns = n.connected_camera_ids || [];
                return conns.map((targetId) => {
                  const targetNode = nodes.find((tn) => tn.camera_id === targetId);
                  if (!targetNode) return null;
                  return (
                    <line
                      key={`${n.camera_id}-${targetId}`}
                      x1={n.x_pos + 65}
                      y1={n.y_pos + 30}
                      x2={targetNode.x_pos + 65}
                      y2={targetNode.y_pos + 30}
                      stroke="rgba(245, 158, 11, 0.4)"
                      strokeWidth="2"
                      strokeDasharray="4 4"
                      markerEnd="url(#arrow)"
                    />
                  );
                });
              })}
            </svg>

            {/* NODES */}
            {nodes.map((node) => (
              <div
                key={node.camera_id}
                onClick={() => setSelectedNode(node)}
                className={`${styles.node} ${selectedNode?.camera_id === node.camera_id ? styles.nodeActive : ""}`}
                style={{ left: node.x_pos, top: node.y_pos }}
              >
                <div className={styles.nodeHeader}>
                  <span className={styles.nodeCamId}>{node.camera_id}</span>
                  <span style={{ fontSize: "0.6rem", color: "#22c55e" }}>● ONLINE</span>
                </div>
                <div className={styles.nodeLoc}>{node.location_label}</div>
              </div>
            ))}
          </div>

          {/* SIDEBAR DETAIL */}
          <aside className={styles.sidebar}>
            {selectedNode ? (
              <>
                <div style={{ paddingBottom: 10, borderBottom: "1px solid var(--border-dim)" }}>
                  <div className="text-xs text-amber font-bold">{selectedNode.camera_id}</div>
                  <h3 style={{ fontSize: "1rem", color: "#f8fafc", margin: "4px 0" }}>{selectedNode.location_label}</h3>
                  <div className="text-xs text-muted">{selectedNode.camera_name}</div>
                </div>

                <div style={{ background: "var(--bg-deep)", padding: 10, borderRadius: 6, fontSize: "0.75rem", display: "flex", flexDirection: "column", gap: 4 }}>
                  <div className="text-muted font-bold">CONNECTED NODES ({selectedNode.connected_camera_ids?.length || 0}):</div>
                  {selectedNode.connected_camera_ids && selectedNode.connected_camera_ids.length > 0 ? (
                    selectedNode.connected_camera_ids.map((cid) => (
                      <div key={cid} className="mono-sm text-cyan">• {cid}</div>
                    ))
                  ) : (
                    <div className="text-muted">No direct neighbor nodes configured.</div>
                  )}
                </div>

                {/* CORRELATED HOPS */}
                <div>
                  <div className="text-xs text-muted font-bold mb-2">SUSPECT CORRELATION HOPS ({hops.length})</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    {hops.map((hop, i) => (
                      <div key={i} className={styles.hopItem}>
                        <div>
                          <div style={{ fontWeight: 600, color: "#f8fafc" }}>{hop.subject_label}</div>
                          <div style={{ fontSize: "0.65rem", color: "#64748b" }}>
                            Frame #{hop.from_frame} → #{hop.to_frame}
                          </div>
                        </div>
                        <span className="mono-sm text-amber font-bold">
                          {(hop.similarity_score * 100).toFixed(0)}% Match
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                <div style={{ marginTop: "auto", fontSize: "0.68rem", color: "#64748b", fontStyle: "italic" }}>
                  * Node graph represents spatial topology. Transitions do not assume biometric identity without independent investigator verification.
                </div>
              </>
            ) : (
              <div style={{ textAlign: "center", color: "#64748b", margin: "auto" }}>
                Select a camera node to inspect connections and correlation paths.
              </div>
            )}
          </aside>
        </div>
      </main>
    </div>
  );
}
