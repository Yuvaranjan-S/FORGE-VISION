// FORGE-VISION — API client & Unified Forensic Protocol
const rawApiUrl = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+$/, "");
export const API_ROOT = rawApiUrl.endsWith("/api") ? rawApiUrl.slice(0, -4) : rawApiUrl;
export const API_BASE = rawApiUrl.endsWith("/api") ? rawApiUrl : `${rawApiUrl}/api`;

let _token: string | null = null;
let _user: { username: string; role: string; full_name: string; user_id: string } | null = null;

export function setToken(token: string, user: typeof _user) {
  _token = token;
  _user = user;
  if (typeof window !== "undefined") {
    localStorage.setItem("forge_token", token);
    localStorage.setItem("forge_user", JSON.stringify(user));
  }
}

export function loadStoredAuth() {
  if (typeof window === "undefined") return;
  const t = localStorage.getItem("forge_token");
  const u = localStorage.getItem("forge_user");
  if (t && u) {
    _token = t;
    _user = JSON.parse(u);
  }
}

export function getUser() { return _user; }
export function getToken() { return _token; }

export function logout() {
  _token = null; _user = null;
  if (typeof window !== "undefined") {
    localStorage.removeItem("forge_token");
    localStorage.removeItem("forge_user");
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };
  if (_token) headers["Authorization"] = `Bearer ${_token}`;
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  try {
    const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `API request failed (${res.status})`);
    }
    return res.json();
  } catch (error: unknown) {
    if (error instanceof TypeError && error.message.includes("fetch")) {
      throw new Error("Backend service unavailable. Please verify the backend is running and CORS is configured.");
    }
    throw error;
  }
}

// ── AUTH ─────────────────────────────────────────────────────
export async function login(username: string, password: string) {
  const form = new FormData();
  form.append("username", username);
  form.append("password", password);
  const data = await fetch(`${API_BASE}/auth/token`, {
    method: "POST", body: form,
  }).then(async r => { if (!r.ok) throw new Error((await r.json()).detail); return r.json(); });
  setToken(data.access_token, {
    username: data.username, role: data.role,
    full_name: data.full_name, user_id: data.user_id,
  });
  return data;
}

export async function register(username: string, fullName: string, password: string, role = "investigator") {
  return request("/auth/register", {
    method: "POST",
    body: JSON.stringify({ username, full_name: fullName, password, role }),
  });
}

// ── CASES ─────────────────────────────────────────────────────
export const getCases = () => request<Case[]>("/cases/");
export const getCase = (id: string) => request<Case>(`/cases/${id}`);
export const createCase = (title: string, description = "", reference_timezone = "Asia/Kolkata") =>
  request("/cases/", { method: "POST", body: JSON.stringify({ title, description, reference_timezone }) });
export const updateCase = (id: string, data: { status?: string; title?: string; description?: string }) =>
  request(`/cases/${id}`, { method: "PATCH", body: JSON.stringify(data) });

// ── DATASETS ─────────────────────────────────────────────────
export const getDatasets = (caseId?: string, sourceType?: string, vendor?: string) => {
  const params = new URLSearchParams();
  if (caseId) params.append("case_id", caseId);
  if (sourceType) params.append("source_type", sourceType);
  if (vendor) params.append("vendor", vendor);
  const query = params.toString() ? `?${params.toString()}` : "";
  return request<Dataset[]>(`/datasets/${query}`);
};

export const getDataset = (id: string) => request<Dataset>(`/datasets/${id}`);

export const registerDataset = (data: Partial<Dataset>) =>
  request("/datasets/register", { method: "POST", body: JSON.stringify(data) });

export async function importDataset(formData: FormData) {
  const headers: Record<string, string> = {};
  if (_token) headers["Authorization"] = `Bearer ${_token}`;
  const res = await fetch(`${API_BASE}/datasets/import`, {
    method: "POST", body: formData, headers,
  });
  if (!res.ok) throw new Error((await res.json()).detail || "Dataset import failed");
  return res.json();
}

export const generateSyntheticDataset = (caseId = "CASE-DEMO001", scenario = "Warehouse", cameraCount = 8) =>
  request<{ dataset_id: string; name: string; cameras_created: number; sha256: string; message: string }>("/datasets/generate-synthetic", {
    method: "POST",
    body: JSON.stringify({ case_id: caseId, scenario, camera_count: cameraCount }),
  });

export const deleteDataset = (id: string) =>
  request(`/datasets/${id}`, { method: "DELETE" });

export const scanDatasetVideos = (datasetId: string) =>
  request<DatasetVideoScanResult>(`/datasets/${datasetId}/scan-videos`, { method: "POST" });

export const importDatasetVideos = (
  datasetId: string,
  data: { case_id: string; selected_files?: string[]; max_count?: number }
) =>
  request<{ job_id: string; dataset_id: string; dataset_name: string; case_id: string; status: string; message: string }>(
    `/datasets/${datasetId}/import-videos`,
    { method: "POST", body: JSON.stringify(data) }
  );

// ── KAGGLE PIPELINE ──────────────────────────────────────────
export interface KaggleSource {
  id: string;
  name: string;
  provider: string;
  kaggle_dataset_identifier: string;
  source_reference: string;
  source_type: string;
  platform: string;
  license: string;
  description: string;
  categories: string[];
  subfolder: string;
  default_sample_count: number;
  citation: string;
  is_authenticated: boolean;
  status: "IMPORTED" | "AVAILABLE" | "SAMPLE_READY" | "AUTHENTICATION_REQUIRED";
  imported_dataset_id?: string;
  imported_file_count?: number;
  imported_at?: string;
}

export interface KaggleAuthStatus {
  authenticated: boolean;
  username: string | null;
  auth_source: string;
  instructions: string;
}

export interface DirectoryScanResult {
  valid: boolean;
  directory_path: string;
  total_files: number;
  total_size_bytes: number;
  video_count: number;
  image_count: number;
  annotation_count: number;
  videos: { filename: string; relative_path: string; full_path: string; file_size_bytes: number; extension: string }[];
  images: { filename: string; relative_path: string; full_path: string; file_size_bytes: number; extension: string }[];
  annotations: { filename: string; relative_path: string; full_path: string; file_size_bytes: number; extension: string }[];
  error?: string;
}

export interface KaggleJobStatus {
  job_id: string;
  dataset_key: string;
  case_id: string;
  status: "queued" | "in_progress" | "completed" | "failed";
  stage: string;
  progress_percent: number;
  total_files: number;
  processed_files: number;
  imported_count: number;
  skipped_count: number;
  failed_count: number;
  failed_files: { filename: string; error: string }[];
  skipped_files: { filename: string; reason: string; existing_evidence_id: string }[];
  evidence_ids: string[];
  dataset_id: string | null;
  current_file: string;
  created_at: string;
  completed_at: string | null;
  error: string | null;
}

export const getKaggleSources = () => request<KaggleSource[]>("/kaggle/sources");
export const getKaggleAuthStatus = () => request<KaggleAuthStatus>("/kaggle/auth-status");
export const scanKaggleLocal = (directory_path: string) =>
  request<DirectoryScanResult>("/kaggle/scan-local", { method: "POST", body: JSON.stringify({ directory_path }) });

export const importKaggleSample = (dataset_key: string, case_id = "CASE-DEMO001", sample_count = 5, category = "ALL") =>
  request<{ job_id: string; dataset_key: string; case_id: string; status: string; message: string }>("/kaggle/import-sample", {
    method: "POST",
    body: JSON.stringify({ dataset_key, case_id, sample_count, category }),
  });

export const importKaggleDirectory = (dataset_key: string, directory_path: string, case_id = "CASE-DEMO001", selected_files?: string[]) =>
  request<{ job_id: string; dataset_key: string; directory_path: string; status: string; message: string }>("/kaggle/import-local-directory", {
    method: "POST",
    body: JSON.stringify({ dataset_key, directory_path, case_id, selected_files }),
  });

export const getKaggleJobStatus = (job_id: string) =>
  request<KaggleJobStatus>(`/kaggle/jobs/${job_id}`);

// ── EVIDENCE ─────────────────────────────────────────────────
export interface EvidenceQueryParams {
  case_id?: string;
  source_type?: string;
  source_platform?: string;
  vendor?: string;
  vendor_classification_status?: string;
  camera_id?: string;
  integrity_status?: string;
  recovery_status?: string;
  search?: string;
  limit?: number;
  offset?: number;
}

export const listAllEvidence = (params?: EvidenceQueryParams) => {
  const sp = new URLSearchParams();
  if (params?.case_id) sp.append("case_id", params.case_id);
  if (params?.source_type) sp.append("source_type", params.source_type);
  if (params?.source_platform) sp.append("source_platform", params.source_platform);
  if (params?.vendor) sp.append("vendor", params.vendor);
  if (params?.vendor_classification_status) sp.append("vendor_classification_status", params.vendor_classification_status);
  if (params?.camera_id) sp.append("camera_id", params.camera_id);
  if (params?.integrity_status) sp.append("integrity_status", params.integrity_status);
  if (params?.recovery_status) sp.append("recovery_status", params.recovery_status);
  if (params?.search) sp.append("search", params.search);
  if (params?.limit) sp.append("limit", params.limit.toString());
  if (params?.offset) sp.append("offset", params.offset.toString());
  const q = sp.toString() ? `?${sp.toString()}` : "";
  return request<Evidence[]>(`/evidence/${q}`);
};

export const getEvidence = (caseId: string) => request<Evidence[]>(`/evidence/case/${caseId}`);
export const getEvidenceItem = (id: string) => request<Evidence>(`/evidence/${id}`);
export const getFindings = (id: string) => request<AIFinding[]>(`/evidence/${id}/findings`);

export async function ingestEvidence(caseId: string, file: File, cameraId = "CAM-01", channel = "CH-1", notes = "") {
  const form = new FormData();
  form.append("file", file);
  form.append("camera_id", cameraId);
  form.append("channel", channel);
  form.append("notes", notes);
  const headers: Record<string, string> = {};
  if (_token) headers["Authorization"] = `Bearer ${_token}`;
  const res = await fetch(`${API_BASE}/acquisition/ingest/${caseId}`, {
    method: "POST", body: form, headers,
  });
  if (!res.ok) throw new Error((await res.json()).detail);
  return res.json();
}

export const verifyEvidence = (id: string) =>
  request(`/acquisition/evidence/${id}/verify`, { method: "GET" });

// ── ANALYSIS ─────────────────────────────────────────────────
export const runAuthenticity = (id: string) =>
  request(`/analysis/${id}/authenticity`, { method: "POST" });
export const runAIDetection = (id: string) =>
  request(`/analysis/${id}/ai-detection`, { method: "POST" });
export const runMotionHeatmap = (id: string) =>
  request(`/analysis/${id}/motion-heatmap`, { method: "POST" });
export const runCameraTamper = (id: string) =>
  request(`/analysis/${id}/camera-tamper`, { method: "POST" });
export const runCrossReID = (caseId: string, subjectLabel = "Suspect A") =>
  request(`/analysis/case/${caseId}/cross-camera-reid?subject_label=${encodeURIComponent(subjectLabel)}`, { method: "POST" });

// ── BOOKMARKS ────────────────────────────────────────────────
export const getBookmarks = (caseId: string) =>
  request<Bookmark[]>(`/bookmarks/case/${caseId}`);

export const createBookmark = (data: { case_id: string; evidence_id: string; camera_id?: string; frame_number?: number; timestamp_in_video?: string; title: string; notes?: string; tag?: string }) =>
  request<Bookmark>("/bookmarks/", { method: "POST", body: JSON.stringify(data) });

export const deleteBookmark = (id: string) =>
  request(`/bookmarks/${id}`, { method: "DELETE" });

// ── CAMERA TOPOLOGY ──────────────────────────────────────────
export const getCameraTopology = (caseId: string) =>
  request<CameraTopologyResponse>(`/cameras/case/${caseId}/topology`);

export const saveCameraTopology = (caseId: string, nodes: CameraNode[]) =>
  request("/cameras/topology", { method: "POST", body: JSON.stringify({ case_id: caseId, nodes }) });

// ── AUDIT LOGS ───────────────────────────────────────────────
export const getAuditLogs = (userId?: string, action?: string, limit = 100) => {
  const params = new URLSearchParams();
  if (userId) params.append("user_id", userId);
  if (action) params.append("action", action);
  params.append("limit", limit.toString());
  return request<AuditLogResponse>(`/audit/logs?${params.toString()}`);
};

// ── CUSTODY ──────────────────────────────────────────────────
export const getCustody = (caseId: string) =>
  request<CustodyResponse>(`/custody/case/${caseId}`);
export const verifyCustodyChain = (caseId: string) =>
  request<ChainVerification>(`/custody/case/${caseId}/verify`);

// ── TIMELINE ─────────────────────────────────────────────────
export const getTimeline = (caseId: string) =>
  request<TimelineData>(`/timeline/case/${caseId}`);

// ── NLP ──────────────────────────────────────────────────────
export const queryEvidence = (caseId: string, query: string) =>
  request<NLPResponse>(`/nlp/case/${caseId}/query`, {
    method: "POST",
    body: JSON.stringify({ query }),
  });

// ── REPORTING ────────────────────────────────────────────────
export async function generateReport(caseId: string) {
  const headers: Record<string, string> = {};
  if (_token) headers["Authorization"] = `Bearer ${_token}`;
  const res = await fetch(`${API_BASE}/reporting/case/${caseId}/generate`, {
    method: "POST", headers,
  });
  if (!res.ok) throw new Error("Report generation failed");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = `FORGE-VISION-${caseId}.pdf`;
  a.click();
  URL.revokeObjectURL(url);
}

// ── TYPES ─────────────────────────────────────────────────────
export interface Case {
  id: string; title: string; description: string; status: string;
  created_at: string; updated_at: string; created_by: string;
  reference_timezone: string; evidence_count: number;
  ai_finding_count?: number; custody_entry_count?: number;
}

export interface Dataset {
  id: string; case_id?: string; name: string; source_type: string;
  source_provider: string; description: string; vendor: string;
  device_model?: string; camera_count: number; file_count: number;
  total_size_bytes: number; license: string; source_reference?: string;
  collection_method?: string; collector_name?: string; collection_date?: string;
  is_synthetic: number; forensic_status: string; platform?: string;
  kaggle_dataset_identifier?: string; sha256: string; created_at: string;
  files?: DatasetFile[]; evidence_items?: Evidence[];
}

export interface DatasetFile {
  id: string; dataset_id: string; file_name: string; file_path: string;
  file_size_bytes: number; sha256: string; detected_vendor: string;
  file_type: string; status: string; created_at: string;
}

export interface Evidence {
  id: string; case_id: string; dataset_id?: string;
  source_type?: string; source_platform?: string; source_name?: string;
  source_provider?: string; source_reference?: string;
  source_vendor: string; vendor_classification_status?: string;
  parser_used: string; parser_confidence: number;
  is_simulated_adapter: number; device_model: string; device_serial?: string;
  firmware: string; camera_id: string; original_camera_id?: string;
  normalized_camera_id?: string; channel: string; original_filename?: string;
  timestamp_start: string; timestamp_end: string; original_timestamp?: string;
  normalized_timestamp?: string; container_timestamp?: string; osd_timestamp?: string;
  timestamp_status?: string; timezone: string; clock_drift_seconds: number;
  codec: string; resolution: string; fps: number; duration_seconds: number;
  bitrate_kbps: number; frame_count: number; has_audio?: number;
  recovery_status: string; integrity_status: string; authenticity_status: string;
  analysis_status?: string; priority?: string; completeness_score: number;
  md5: string; sha256: string; sha512?: string; sha3_256: string;
  thumbnail_path?: string; file_path: string;
  file_size_bytes: number; ingested_at: string; ingested_by: string;
  import_date?: string; notes: string;
  findings_summary?: Record<string, number>;
  recovery_segments?: RecoverySegment[];
  authenticity_findings?: AuthenticityFinding[];
}

export interface AIFinding {
  id: string; evidence_id: string; case_id: string; finding_type: string;
  frame_number: number; timestamp_in_video: string; confidence: number;
  bounding_box: number[]; label: string; description: string;
  is_simulated: number; requires_review: number; generated_at: string; generator: string;
}

export interface AuthenticityFinding {
  id: string; evidence_id: string; check_type: string; frame_number: number;
  severity: string; confidence: number; detail: string; is_simulated: number;
}

export interface RecoverySegment {
  id: string; evidence_id: string; segment_type: string;
  start_frame: number; end_frame: number; start_time: number; end_time: number;
  completeness: number; nal_units_found: number; is_simulated: number; notes: string;
}

export interface Bookmark {
  id: string; case_id: string; evidence_id: string; camera_id: string;
  frame_number: number; timestamp_in_video: string; title: string;
  notes: string; tag: string; created_by: string; created_at: string;
  source_vendor?: string; file_path?: string; is_simulated_adapter?: number;
}

export interface CameraNode {
  id?: string; case_id?: string; camera_id: string; camera_name: string;
  location_label: string; x_pos: number; y_pos: number;
  connected_camera_ids: string[]; notes?: string;
}

export interface CameraTopologyResponse {
  case_id: string; nodes: CameraNode[];
}

export interface AuditLog {
  id: string; user_id: string; action: string; resource?: string;
  detail?: string; ip_address?: string; timestamp: string;
  username?: string; full_name?: string; role?: string;
}

export interface AuditLogResponse {
  total: number; logs: AuditLog[];
}

export interface CustodyEntry {
  id: string; seq: number; case_id: string; evidence_id: string;
  action: string; operator_id: string; operator_role: string; timestamp: string;
  evidence_hash_before: string; evidence_hash_after: string; detail: string;
  prev_entry_hash: string; this_entry_hash: string;
}

export interface ChainVerification {
  is_valid: boolean; broken_at_seq: number | null; entry_count: number; details: unknown[];
}

export interface CustodyResponse {
  entries: CustodyEntry[]; chain_verification: ChainVerification;
}

export interface TimelineData {
  case_id: string; tracks: TimelineTrack[]; ai_events: AIFinding[];
  authenticity_events: AuthenticityFinding[]; reid_hops: ReidHop[];
  track_count: number; event_count: number;
}

export interface TimelineTrack {
  evidence_id: string; camera_id: string; channel: string;
  source_vendor: string; is_simulated: boolean; duration_seconds: number;
  timestamp_start: string; integrity_status: string; authenticity_status: string;
  recovery_status: string; completeness_score: number;
  segments: RecoverySegment[];
}

export interface ReidHop {
  id: string; subject_label: string; from_evidence_id: string; from_frame: number;
  to_evidence_id: string; to_frame: number; similarity_score: number;
  match_basis: string; is_simulated: number; disclaimer: string;
}

export interface NLPResponse {
  query: string; intent: string; answer: string; citations: unknown[];
  confidence: number; grounding_rule: string; timestamp: string;
}

// ── DATASET VIDEO SCAN ────────────────────────────────────────
export interface DatasetVideoFile {
  filename: string;
  file_path: string;
  file_size_bytes: number;
  extension: string;
  relative_path: string;
  already_imported: boolean;
  existing_evidence_id: string | null;
  existing_camera_id: string | null;
}

export interface DatasetVideoScanResult {
  dataset_id: string;
  dataset_name: string;
  source_folder: string;
  total: number;
  already_imported: number;
  available: number;
  files: DatasetVideoFile[];
}
