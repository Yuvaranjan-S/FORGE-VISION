"""FORGE-VISION — Comprehensive Demo Data Seeder
Populates cases, datasets (provenance), multi-vendor evidence, camera topology,
bookmarks, recovery segments, AI findings, and hash-chained custody ledger.
Run: py -3.12 seed.py
"""
import asyncio
import json
import os
import sys
import uuid
import random
from datetime import datetime, timezone

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import aiosqlite
from app.database import init_db, DB_PATH, safe_hash_password
from app.hash_engine import compute_string_sha256, compute_custody_entry_hash
from app.kaggle_pipeline.kaggle_service import ensure_sample_kaggle_files, KAGGLE_SOURCES_CATALOG


DEMO_USERS = [
    {"id": "user-investigator-01", "username": "investigator", "full_name": "Arjun Sharma", "role": "investigator", "password": "forensiq2024"},
    {"id": "user-supervisor-01", "username": "supervisor", "full_name": "Dr. Priya Mehta", "role": "supervisor", "password": "supervisor2024"},
    {"id": "user-auditor-01", "username": "auditor", "full_name": "Rahul Verma", "role": "auditor", "password": "auditor2024"},
]

DEMO_CASES = [
    {
        "id": "CASE-DEMO001",
        "title": "Operation Kite — Bank Robbery Investigation",
        "description": "Multi-vendor DVR footage and public research benchmarks. Suspect vehicle and entry trail under investigation.",
        "status": "active",
        "reference_timezone": "Asia/Kolkata",
    },
    {
        "id": "CASE-DEMO002",
        "title": "Commercial Complex Fire — Evidence Recovery",
        "description": "Partial NVR data recovery after storage device thermal damage. Authenticity of recovered streams under review.",
        "status": "active",
        "reference_timezone": "Asia/Kolkata",
    },
    {
        "id": "CASE-DEMO-MULTIVENDOR",
        "title": "Multi-Vendor DVR/NVR Architecture Evaluation",
        "description": "Controlled SIH multi-vendor demonstration case featuring separate Hikvision, Dahua, CP Plus, and Generic OEM collections. Labeled [SIMULATED VENDOR FORMAT].",
        "status": "active",
        "reference_timezone": "Asia/Kolkata",
    },
]

DEMO_DATASETS = [
    {
        "id": "DS-DEMO-001",
        "case_id": "CASE-DEMO001",
        "name": "FORGE-VISION Warehouse Investigation",
        "source_type": "SYNTHETIC_DEMO",
        "source_provider": "FORGE-VISION Synthetic Generator",
        "description": "Multi-vendor multi-camera CCTV scenario featuring recording gaps, tamper events, and cross-camera transitions. Labeled [SYNTHETIC DEMO].",
        "vendor": "Multi-Vendor (Hikvision, Dahua, CP Plus, Generic)",
        "device_model": "Multi-OEM Surveillance Array",
        "camera_count": 4,
        "file_count": 4,
        "total_size_bytes": 3145728000,
        "license": "SIH 2024 Evaluation License",
        "source_reference": "SIH-150-BENCHMARK",
        "collection_method": "Synthetic Scenario Engine",
        "collector_name": "SIH Evaluation Team",
        "collection_date": "2024-03-15",
        "is_synthetic": 1,
        "forensic_status": "DEMO_ONLY",
        "platform": "Synthetic",
        "kaggle_dataset_identifier": None,
        "sha256": "4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a",
    },
    {
        "id": "DS-KAG-UCF-01",
        "case_id": "CASE-DEMO001",
        "name": "UCF Crime Surveillance Benchmark (Kaggle Ingestion)",
        "source_type": "PUBLIC_RESEARCH_DATASET",
        "source_provider": "University of Central Florida Center for Research in Computer Vision",
        "description": "Public research benchmark dataset for anomaly detection in CCTV surveillance videos (Burglary, Robbery, Road Accident, Normal).",
        "vendor": "Unknown",
        "device_model": "Research Dataset Camera",
        "camera_count": 6,
        "file_count": 6,
        "total_size_bytes": 48234496,
        "license": "Research / Academic Evaluation License",
        "source_reference": "https://www.kaggle.com/datasets/mission-ai/cctv-surveillance-dataset",
        "collection_method": "Kaggle Public Dataset Pipeline",
        "collector_name": "UCF CRCV / Kaggle Mirror",
        "collection_date": "2024-02-10",
        "is_synthetic": 0,
        "forensic_status": "RESEARCH_DATA",
        "platform": "Kaggle",
        "kaggle_dataset_identifier": "mission-ai/cctv-surveillance-dataset",
        "sha256": "8a3359d9c34a2e5c123456789abcdef0123456789abcdef0123456789abcdef0",
    },
    {
        "id": "DS-KAG-VIRAT-01",
        "case_id": "CASE-DEMO002",
        "name": "VIRAT CCTV Ground Video Benchmark",
        "source_type": "PUBLIC_RESEARCH_DATASET",
        "source_provider": "DARPA / UCF / VIRAT Video Consortium",
        "description": "High-resolution multi-camera ground surveillance dataset covering facility perimeters and parking.",
        "vendor": "Unknown",
        "device_model": "Research Dataset Camera",
        "camera_count": 5,
        "file_count": 5,
        "total_size_bytes": 35651584,
        "license": "Academic / Non-Commercial Research Evaluation Use Only",
        "source_reference": "https://www.kaggle.com/datasets/hasibalhaq/virat-video-dataset",
        "collection_method": "Kaggle Public Dataset Pipeline",
        "collector_name": "VIRAT Video Consortium",
        "collection_date": "2024-01-15",
        "is_synthetic": 0,
        "forensic_status": "RESEARCH_DATA",
        "platform": "Kaggle",
        "kaggle_dataset_identifier": "hasibalhaq/virat-video-dataset",
        "sha256": "f3b92c4298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    },
    {
        "id": "DS-VENDOR-DEMO",
        "case_id": "CASE-DEMO-MULTIVENDOR",
        "name": "Multi-Vendor OEM Demonstration Suite",
        "source_type": "SYNTHETIC_DEMO",
        "source_provider": "FORGE-VISION Multi-OEM Simulation",
        "description": "Controlled demonstration suite showcasing parser dispatch across Hikvision, Dahua, CP Plus, and Generic DVR/NVR formats.",
        "vendor": "Multi-Vendor (Hikvision, Dahua, CP Plus, Generic)",
        "device_model": "Multi-Vendor DVR/NVR Suite",
        "camera_count": 4,
        "file_count": 4,
        "total_size_bytes": 2605728000,
        "license": "SIH Evaluation Demo License",
        "source_reference": "SIH-150-MULTIVENDOR-DEMO",
        "collection_method": "Vendor Format Simulation Engine",
        "collector_name": "Digital Forensics Evaluation Lab",
        "collection_date": "2024-03-01",
        "is_synthetic": 1,
        "forensic_status": "DEMO_DATA",
        "platform": "Synthetic",
        "kaggle_dataset_identifier": None,
        "sha256": "c8e1a30489dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a",
    },
]

DEMO_EVIDENCE = [
    # ── CASE-DEMO001: SYNTHETIC & KAGGLE SURVEILLANCE
    {
        "id": "EV-DEMO-001",
        "case_id": "CASE-DEMO001",
        "dataset_id": "DS-DEMO-001",
        "source_type": "SYNTHETIC_DEMO",
        "source_platform": "Direct",
        "source_vendor": "Hikvision",
        "vendor_classification_status": "SIMULATED_DEMO",
        "parser_used": "HikvisionParser",
        "parser_confidence": 0.15,
        "is_simulated_adapter": 1,
        "device_model": "[SIMULATED] Hikvision DS-7208HQHI-K2",
        "firmware": "[SIMULATED] v4.30.085 build 220105",
        "camera_id": "CAM-01",
        "original_camera_id": "CAM-01",
        "normalized_camera_id": "CAM-01",
        "channel": "CH-1",
        "original_filename": "MainGate_Entry.mp4",
        "timestamp_start": "2024-03-15T09:00:00+05:30",
        "timestamp_end": "2024-03-15T11:00:00+05:30",
        "timezone": "Asia/Kolkata",
        "clock_drift_seconds": 47.0,
        "codec": "H.265",
        "resolution": "1920x1080",
        "fps": 25.0,
        "duration_seconds": 7200.0,
        "bitrate_kbps": 4096.0,
        "frame_count": 180000,
        "file_path": "DEMO_STORE/CAM-01.mp4",
        "file_size_bytes": 1073741824,
        "recovery_status": "intact",
        "integrity_status": "verified",
        "authenticity_status": "no_tamper_detected",
        "priority": "MEDIUM",
        "completeness_score": 1.0,
        "md5": "a3f8b2c14e9d6071f8c3d5a7b9e21043",
        "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "sha512": "cf83e1357eefb8bdf1542850d66d8007d620e4050b5715dc83f4a921d36ce9ce47d0d13c5d85f2b0ff8318d2877eec2f63b931bd47417a81a538327af927da3e",
        "sha3_256": "a7ffc6f8bf1ed76651c14756a061d662f580ff4de43b49fa82d80a4b80f8434a",
        "ingested_at": "2024-03-15T14:30:00Z",
        "ingested_by": "user-investigator-01",
        "notes": "SIMULATED ADAPTER — Hikvision proprietary format. Location: Main Gate Entry Barrier.",
    },
    {
        "id": "EV-DEMO-002",
        "case_id": "CASE-DEMO001",
        "dataset_id": "DS-DEMO-001",
        "source_type": "SYNTHETIC_DEMO",
        "source_platform": "Direct",
        "source_vendor": "Dahua",
        "vendor_classification_status": "SIMULATED_DEMO",
        "parser_used": "DahuaParser",
        "parser_confidence": 0.15,
        "is_simulated_adapter": 1,
        "device_model": "[SIMULATED] Dahua DHI-NVR2208-4KS2",
        "firmware": "[SIMULATED] v3.218.0000000.7",
        "camera_id": "CAM-02",
        "original_camera_id": "CAM-02",
        "normalized_camera_id": "CAM-02",
        "channel": "CH-2",
        "original_filename": "Perimeter_South.mp4",
        "timestamp_start": "2024-03-15T09:12:00+05:30",
        "timestamp_end": "2024-03-15T11:12:00+05:30",
        "timezone": "Asia/Kolkata",
        "clock_drift_seconds": -23.0,
        "codec": "H.264",
        "resolution": "2560x1440",
        "fps": 20.0,
        "duration_seconds": 7200.0,
        "bitrate_kbps": 6144.0,
        "frame_count": 144000,
        "file_path": "DEMO_STORE/CAM-02.mp4",
        "file_size_bytes": 734003200,
        "recovery_status": "partial",
        "integrity_status": "verified",
        "authenticity_status": "suspected_edit",
        "priority": "HIGH",
        "completeness_score": 0.73,
        "md5": "b7e23ec29af22b0b4e41da31e868d57f",
        "sha256": "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824",
        "sha512": "89b7b80a42a0b167c29be19f187313010b9918204d8f8a1a3d90615e45a2784531be4d896173a5a7bb296a84d4ecbcfad7678519e913a48e89f81648a1c97a55",
        "sha3_256": "d4ea21722ef3f857e3c4bba6c4ba0b6a26cf4e6e3d5e2f4b1c3a8d9e7f6b5a4c3",
        "ingested_at": "2024-03-15T14:45:00Z",
        "ingested_by": "user-investigator-01",
        "notes": "SIMULATED ADAPTER — Dahua format. Partial data: 27% frame gap detected. Authenticity: ELA flagged possible splicing at 01:23:45.",
    },
    # ── KAGGLE IMPORTED RESEARCH FOOTAGE (UCF CRIME)
    {
        "id": "EVD-KAG-001",
        "case_id": "CASE-DEMO001",
        "dataset_id": "DS-KAG-UCF-01",
        "source_type": "PUBLIC_RESEARCH_DATASET",
        "source_platform": "Kaggle",
        "source_vendor": "Unknown",
        "vendor_classification_status": "UNKNOWN",
        "parser_used": "GenericVideoParser",
        "parser_confidence": 0.95,
        "is_simulated_adapter": 0,
        "device_model": "Research Dataset Camera",
        "firmware": None,
        "camera_id": "DATASET_CAM_01",
        "original_camera_id": "UCF_CAM_01",
        "normalized_camera_id": "DATASET_CAM_01",
        "channel": "CH-1",
        "original_filename": "Burglary001_x264.mp4",
        "timestamp_start": "2026-08-25T22:15:00Z",
        "timestamp_end": "2026-08-25T22:15:10Z",
        "original_timestamp": "RELATIVE_TO_START",
        "normalized_timestamp": "RELATIVE TO VIDEO START",
        "timezone": "UTC",
        "clock_drift_seconds": 0.0,
        "codec": "H.264",
        "resolution": "1280x720",
        "fps": 25.0,
        "duration_seconds": 10.0,
        "bitrate_kbps": 2048.0,
        "frame_count": 250,
        "file_path": "data/kaggle/ucf_crime/Burglary001_x264.mp4",
        "file_size_bytes": 1048576,
        "recovery_status": "intact",
        "integrity_status": "verified",
        "authenticity_status": "no_tamper_detected",
        "priority": "HIGH",
        "completeness_score": 1.0,
        "md5": "5d41402abc4b2a76b9719d911017c592",
        "sha256": "4c944f76b803512330a40f3fb5a66b357f1d696b30d124b4913277d5d4c4373f",
        "sha512": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        "sha3_256": "69217a3079908094e11121d042354a7c1f55b6482ca1a51e1b250dfd1ed0eef9",
        "ingested_at": "2026-08-25T15:00:00Z",
        "ingested_by": "user-investigator-01",
        "import_date": "2026-08-25",
        "notes": "Imported from UCF Crime Surveillance Benchmark via Kaggle CCTV Ingestion Pipeline. Public research dataset — not original case-acquired DVR evidence.",
    },
    {
        "id": "EVD-KAG-002",
        "case_id": "CASE-DEMO001",
        "dataset_id": "DS-KAG-UCF-01",
        "source_type": "PUBLIC_RESEARCH_DATASET",
        "source_platform": "Kaggle",
        "source_vendor": "Unknown",
        "vendor_classification_status": "UNKNOWN",
        "parser_used": "GenericVideoParser",
        "parser_confidence": 0.95,
        "is_simulated_adapter": 0,
        "device_model": "Research Dataset Camera",
        "firmware": None,
        "camera_id": "DATASET_CAM_02",
        "original_camera_id": "UCF_CAM_02",
        "normalized_camera_id": "DATASET_CAM_02",
        "channel": "CH-2",
        "original_filename": "Robbery001_x264.mp4",
        "timestamp_start": "2026-08-25T22:20:00Z",
        "timestamp_end": "2026-08-25T22:20:08Z",
        "original_timestamp": "RELATIVE_TO_START",
        "normalized_timestamp": "RELATIVE TO VIDEO START",
        "timezone": "UTC",
        "clock_drift_seconds": 0.0,
        "codec": "H.264",
        "resolution": "1280x720",
        "fps": 25.0,
        "duration_seconds": 8.0,
        "bitrate_kbps": 2048.0,
        "frame_count": 200,
        "file_path": "data/kaggle/ucf_crime/Robbery001_x264.mp4",
        "file_size_bytes": 948576,
        "recovery_status": "intact",
        "integrity_status": "verified",
        "authenticity_status": "no_tamper_detected",
        "priority": "HIGH",
        "completeness_score": 1.0,
        "md5": "098f6bcd4621d373cade4e832627b4f6",
        "sha256": "5994471abb01112afcc18159f6cc74b4f511b99806da59b3caf5a9c173cacfc5",
        "sha512": "89b7b80a42a0b167c29be19f187313010b9918204d8f8a1a3d90615e45a27845",
        "sha3_256": "2c624232cdd221771294dfbb310acbc8f8369ef20da67cbf4d6f9d638f6e4928",
        "ingested_at": "2026-08-25T15:05:00Z",
        "ingested_by": "user-investigator-01",
        "import_date": "2026-08-25",
        "notes": "Imported from UCF Crime Surveillance Benchmark via Kaggle CCTV Ingestion Pipeline. Public research dataset — not original case-acquired DVR evidence.",
    },
    # ── CASE-DEMO-MULTIVENDOR: FOUR SEPARATED DEMO COLLECTIONS
    {
        "id": "EVD-MV-HIK-01",
        "case_id": "CASE-DEMO-MULTIVENDOR",
        "dataset_id": "DS-VENDOR-DEMO",
        "source_type": "SYNTHETIC_DEMO",
        "source_platform": "Synthetic",
        "source_vendor": "Hikvision",
        "vendor_classification_status": "SIMULATED_DEMO",
        "parser_used": "HikvisionParser",
        "parser_confidence": 0.20,
        "is_simulated_adapter": 1,
        "device_model": "[SIMULATED] Hikvision DS-7616NI-I2/16P NVR",
        "firmware": "[SIMULATED] v4.61.025 build 220905",
        "camera_id": "HIK-CAM-01",
        "original_camera_id": "HIK_CH1_MAIN",
        "normalized_camera_id": "HIK-CAM-01",
        "channel": "CH-1",
        "original_filename": "Hikvision_Vault_Corridor_Sim.mp4",
        "timestamp_start": "2026-08-25T10:00:00+05:30",
        "timestamp_end": "2026-08-25T10:30:00+05:30",
        "timezone": "Asia/Kolkata",
        "clock_drift_seconds": 12.0,
        "codec": "H.265",
        "resolution": "2560x1440",
        "fps": 25.0,
        "duration_seconds": 1800.0,
        "bitrate_kbps": 4096.0,
        "frame_count": 45000,
        "file_path": "DEMO_STORE/HIK_CAM01.mp4",
        "file_size_bytes": 524288000,
        "recovery_status": "intact",
        "integrity_status": "verified",
        "authenticity_status": "no_tamper_detected",
        "priority": "HIGH",
        "completeness_score": 1.0,
        "md5": "7b8b965ad4bca0e41ab51de7b31363a1",
        "sha256": "a1b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef0",
        "sha512": "1a2b3c4d5e6f708192a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0123456789a",
        "sha3_256": "f0e1d2c3b4a5968778695a4b3c2d1e0f0e1d2c3b4a5968778695a4b3c2d1e0f",
        "ingested_at": "2026-08-25T15:10:00Z",
        "ingested_by": "user-supervisor-01",
        "import_date": "2026-08-25",
        "notes": "* SIMULATED VENDOR DATA — NOT ORIGINAL VENDOR EVIDENCE. Demonstrated with HikvisionParser adapter.",
    },
    {
        "id": "EVD-MV-DAH-01",
        "case_id": "CASE-DEMO-MULTIVENDOR",
        "dataset_id": "DS-VENDOR-DEMO",
        "source_type": "SYNTHETIC_DEMO",
        "source_platform": "Synthetic",
        "source_vendor": "Dahua",
        "vendor_classification_status": "SIMULATED_DEMO",
        "parser_used": "DahuaParser",
        "parser_confidence": 0.20,
        "is_simulated_adapter": 1,
        "device_model": "[SIMULATED] Dahua DHI-XVR5108HS-4KL-I3",
        "firmware": "[SIMULATED] v4.001.0000000.1",
        "camera_id": "DAH-CAM-01",
        "original_camera_id": "DAH_CH1_ENTRANCE",
        "normalized_camera_id": "DAH-CAM-01",
        "channel": "CH-1",
        "original_filename": "Dahua_MainEntrance_Sim.mp4",
        "timestamp_start": "2026-08-25T10:05:00+05:30",
        "timestamp_end": "2026-08-25T10:35:00+05:30",
        "timezone": "Asia/Kolkata",
        "clock_drift_seconds": -8.0,
        "codec": "H.264",
        "resolution": "1920x1080",
        "fps": 20.0,
        "duration_seconds": 1800.0,
        "bitrate_kbps": 3072.0,
        "frame_count": 36000,
        "file_path": "DEMO_STORE/DAH_CAM01.mp4",
        "file_size_bytes": 419430400,
        "recovery_status": "partial",
        "integrity_status": "verified",
        "authenticity_status": "inconclusive",
        "priority": "HIGH",
        "completeness_score": 0.88,
        "md5": "9e107d9d372bb6826bd81d3542a419d6",
        "sha256": "b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef01a",
        "sha512": "2b3c4d5e6f708192a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0123456789a1b",
        "sha3_256": "0e1d2c3b4a5968778695a4b3c2d1e0f0e1d2c3b4a5968778695a4b3c2d1e0ff0",
        "ingested_at": "2026-08-25T15:12:00Z",
        "ingested_by": "user-supervisor-01",
        "import_date": "2026-08-25",
        "notes": "* SIMULATED VENDOR DATA — NOT ORIGINAL VENDOR EVIDENCE. Demonstrated with DahuaParser adapter.",
    },
    {
        "id": "EVD-MV-CP-01",
        "case_id": "CASE-DEMO-MULTIVENDOR",
        "dataset_id": "DS-VENDOR-DEMO",
        "source_type": "SYNTHETIC_DEMO",
        "source_platform": "Synthetic",
        "source_vendor": "CP Plus",
        "vendor_classification_status": "SIMULATED_DEMO",
        "parser_used": "CPPlusParser",
        "parser_confidence": 0.20,
        "is_simulated_adapter": 1,
        "device_model": "[SIMULATED] CP Plus CP-UVR-0801E1-CS",
        "firmware": "[SIMULATED] v3.200.0000000.3",
        "camera_id": "CP-CAM-01",
        "original_camera_id": "CP_CH1_GATE",
        "normalized_camera_id": "CP-CAM-01",
        "channel": "CH-1",
        "original_filename": "CPPlus_PerimeterGate_Sim.mp4",
        "timestamp_start": "2026-08-25T09:58:00+05:30",
        "timestamp_end": "2026-08-25T10:28:00+05:30",
        "timezone": "Asia/Kolkata",
        "clock_drift_seconds": 65.0,
        "codec": "H.264",
        "resolution": "1920x1080",
        "fps": 15.0,
        "duration_seconds": 1800.0,
        "bitrate_kbps": 2048.0,
        "frame_count": 27000,
        "file_path": "DEMO_STORE/CP_CAM01.mp4",
        "file_size_bytes": 272629760,
        "recovery_status": "reconstructed",
        "integrity_status": "verified",
        "authenticity_status": "no_tamper_detected",
        "priority": "MEDIUM",
        "completeness_score": 0.94,
        "md5": "c4ca4238a0b923820dcc509a6f75849b",
        "sha256": "c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef01a2b",
        "sha512": "3c4d5e6f708192a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0123456789a1b2c",
        "sha3_256": "1d2c3b4a5968778695a4b3c2d1e0f0e1d2c3b4a5968778695a4b3c2d1e0ff0e",
        "ingested_at": "2026-08-25T15:15:00Z",
        "ingested_by": "user-supervisor-01",
        "import_date": "2026-08-25",
        "notes": "* SIMULATED VENDOR DATA — NOT ORIGINAL VENDOR EVIDENCE. Demonstrated with CPPlusParser adapter.",
    },
    {
        "id": "EVD-MV-GEN-01",
        "case_id": "CASE-DEMO-MULTIVENDOR",
        "dataset_id": "DS-VENDOR-DEMO",
        "source_type": "SYNTHETIC_DEMO",
        "source_platform": "Synthetic",
        "source_vendor": "Generic",
        "vendor_classification_status": "SIMULATED_DEMO",
        "parser_used": "GenericVideoParser",
        "parser_confidence": 0.95,
        "is_simulated_adapter": 0,
        "device_model": "Generic RTSP IP Camera Stream",
        "firmware": "ONVIF Profile S",
        "camera_id": "GEN-CAM-01",
        "original_camera_id": "GEN_STREAM_01",
        "normalized_camera_id": "GEN-CAM-01",
        "channel": "CH-1",
        "original_filename": "Generic_RTSP_Stream_Sim.mp4",
        "timestamp_start": "2026-08-25T10:00:00+05:30",
        "timestamp_end": "2026-08-25T10:30:00+05:30",
        "timezone": "Asia/Kolkata",
        "clock_drift_seconds": 0.0,
        "codec": "H.264",
        "resolution": "1280x720",
        "fps": 30.0,
        "duration_seconds": 1800.0,
        "bitrate_kbps": 1500.0,
        "frame_count": 54000,
        "file_path": "DEMO_STORE/GEN_CAM01.mp4",
        "file_size_bytes": 209715200,
        "recovery_status": "intact",
        "integrity_status": "verified",
        "authenticity_status": "no_tamper_detected",
        "priority": "LOW",
        "completeness_score": 1.0,
        "md5": "eccbc87e4b5ce2fe28308fd9f2a7baf3",
        "sha256": "d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef01a2b3c",
        "sha512": "4d5e6f708192a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0123456789a1b2c3d",
        "sha3_256": "2c3b4a5968778695a4b3c2d1e0f0e1d2c3b4a5968778695a4b3c2d1e0ff0e1d",
        "ingested_at": "2026-08-25T15:18:00Z",
        "ingested_by": "user-supervisor-01",
        "import_date": "2026-08-25",
        "notes": "* SIMULATED VENDOR DATA — Standard Generic MP4 Stream via GenericVideoParser.",
    },
]

DEMO_TOPOLOGY = [
    ("CAM-01", "North Gate Entry", "North Perimeter", 120, 80, ["CAM-02", "CAM-04"]),
    ("CAM-02", "South Perimeter Fence", "South Yard", 420, 260, ["CAM-01", "CAM-03"]),
    ("CAM-03", "Vault Corridor Interior", "Secure Vault", 280, 180, ["CAM-02", "CAM-04"]),
    ("CAM-04", "East Loading Dock", "Loading Bay East", 180, 320, ["CAM-01", "CAM-03"]),
]

DEMO_BOOKMARKS = [
    {
        "id": "BM-001",
        "case_id": "CASE-DEMO001",
        "evidence_id": "EV-DEMO-001",
        "camera_id": "CAM-01",
        "frame_number": 2400,
        "timestamp_in_video": "00:16:00",
        "title": "Suspect Vehicle Approach",
        "notes": "Silver sedan matching dispatch report entered barrier gate.",
        "tag": "VEHICLE",
    },
    {
        "id": "BM-002",
        "case_id": "CASE-DEMO001",
        "evidence_id": "EV-DEMO-002",
        "camera_id": "CAM-02",
        "frame_number": 3600,
        "timestamp_in_video": "00:24:00",
        "title": "Recording Frame Gap Detected",
        "notes": "Stream dropped for 150 seconds. Recovery engine reconstructed trailing GOP.",
        "tag": "ANOMALY",
    },
]


async def seed(db_conn=None):
    print("[FORGE-VISION] Initializing database schema...")
    await init_db()

    # Pre-generate sample files for Kaggle benchmarks
    print("[FORGE-VISION] Ensuring local Kaggle CCTV sample benchmarks...")
    for key in ["ucf-crime", "virat-cctv", "racd-cctv", "cctv-action", "traffic-intersection"]:
        try:
            ensure_sample_kaggle_files(key)
        except Exception:
            pass

    if db_conn is not None:
        await _seed_with_db(db_conn)
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await _seed_with_db(db)

async def _seed_with_db(db: aiosqlite.Connection):
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys=OFF")
    now = datetime.now(timezone.utc).isoformat()

    # ── USERS ──────────────────────────────────────────────
    print("[FORGE-VISION] Seeding users...")
    for u in DEMO_USERS:
            try:
                async with db.execute("SELECT id FROM users WHERE username = ?", (u["username"],)) as cur:
                    if not await cur.fetchone():
                        hashed = safe_hash_password(u["password"])
                        await db.execute(
                            "INSERT INTO users (id, username, full_name, role, hashed_password, is_active, created_at) VALUES (?,?,?,?,?,1,?)",
                            (u["id"], u["username"], u["full_name"], u["role"], hashed, now)
                        )
            except Exception as e:
                print(f"[SEED USERS ERR]: {e}")
    await db.commit()

    # ── CASES ──────────────────────────────────────────────
    print("[FORGE-VISION] Seeding cases...")
    for case in DEMO_CASES:
        async with db.execute("SELECT id FROM cases WHERE id = ?", (case["id"],)) as cur:
            if not await cur.fetchone():
                await db.execute(
                    """INSERT INTO cases (id, title, description, status, created_at, updated_at, created_by, reference_timezone)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (case["id"], case["title"], case["description"], case["status"],
                     now, now, "user-supervisor-01", case["reference_timezone"])
                )
    await db.commit()

    # ── DATASETS ───────────────────────────────────────────
    print("[FORGE-VISION] Seeding datasets...")
    for ds in DEMO_DATASETS:
        async with db.execute("SELECT id FROM datasets WHERE id = ?", (ds["id"],)) as cur:
            if not await cur.fetchone():
                await db.execute(
                    """INSERT INTO datasets (
                        id, case_id, name, source_type, source_provider, description,
                        vendor, device_model, camera_count, file_count, total_size_bytes,
                        license, source_reference, collection_method, collector_name,
                        collection_date, is_synthetic, forensic_status, platform,
                        kaggle_dataset_identifier, sha256, created_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        ds["id"], ds["case_id"], ds["name"], ds["source_type"], ds["source_provider"],
                        ds["description"], ds["vendor"], ds["device_model"], ds["camera_count"],
                        ds["file_count"], ds["total_size_bytes"], ds["license"], ds["source_reference"],
                        ds["collection_method"], ds["collector_name"], ds["collection_date"],
                        ds["is_synthetic"], ds["forensic_status"], ds.get("platform", "Local"),
                        ds.get("kaggle_dataset_identifier"), ds["sha256"], now
                    )
                )
    await db.commit()

    # ── EVIDENCE ───────────────────────────────────────────
    print("[FORGE-VISION] Seeding evidence...")
    for ev in DEMO_EVIDENCE:
        async with db.execute("SELECT id FROM evidence WHERE id = ?", (ev["id"],)) as cur:
            if not await cur.fetchone():
                await db.execute(
                    """INSERT INTO evidence (
                        id, case_id, dataset_id, source_type, source_platform, source_vendor, vendor_classification_status,
                        parser_used, parser_confidence, is_simulated_adapter, device_model, firmware,
                        camera_id, original_camera_id, normalized_camera_id, channel, original_filename,
                        timestamp_start, timestamp_end, original_timestamp, normalized_timestamp, timezone, clock_drift_seconds,
                        codec, resolution, fps, duration_seconds, bitrate_kbps, frame_count,
                        file_path, file_size_bytes, recovery_status, integrity_status,
                        authenticity_status, priority, completeness_score,
                        md5, sha256, sha512, sha3_256, ingested_at, ingested_by, import_date, notes
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        ev["id"], ev["case_id"], ev.get("dataset_id"), ev.get("source_type", "SYNTHETIC_DEMO"),
                        ev.get("source_platform", "Direct"), ev["source_vendor"], ev.get("vendor_classification_status", "UNKNOWN"),
                        ev["parser_used"], ev["parser_confidence"], ev["is_simulated_adapter"],
                        ev["device_model"], ev.get("firmware"), ev["camera_id"], ev.get("original_camera_id", ev["camera_id"]),
                        ev.get("normalized_camera_id", ev["camera_id"]), ev["channel"], ev.get("original_filename", ev["camera_id"] + ".mp4"),
                        ev.get("timestamp_start"), ev.get("timestamp_end", now), ev.get("original_timestamp", "RELATIVE_TO_START"),
                        ev.get("normalized_timestamp", "RELATIVE TO VIDEO START"), ev.get("timezone", "Asia/Kolkata"), ev.get("clock_drift_seconds", 0),
                        ev["codec"], ev["resolution"], ev["fps"], ev["duration_seconds"],
                        ev["bitrate_kbps"], ev["frame_count"],
                        ev["file_path"], ev["file_size_bytes"],
                        ev["recovery_status"], ev["integrity_status"],
                        ev["authenticity_status"], ev.get("priority", "MEDIUM"), ev["completeness_score"],
                        ev["md5"], ev["sha256"], ev.get("sha512"), ev["sha3_256"],
                        ev["ingested_at"], ev["ingested_by"], ev.get("import_date", now[:10]), ev.get("notes"),
                    )
                )

        # Recovery Segments
        if ev["recovery_status"] == "partial":
            await db.execute("DELETE FROM recovery_segments WHERE evidence_id = ?", (ev["id"],))
            await db.execute(
                """INSERT INTO recovery_segments (id, evidence_id, segment_type, start_frame, end_frame, start_time, end_time, completeness, nal_units_found, is_simulated, notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (str(uuid.uuid4()), ev["id"], "intact", 0, 50000, 0.0, 2500.0, 1.0, 18400, 1, "[SYNTHETIC] Initial recording block intact")
            )
            await db.execute(
                """INSERT INTO recovery_segments (id, evidence_id, segment_type, start_frame, end_frame, start_time, end_time, completeness, nal_units_found, is_simulated, notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (str(uuid.uuid4()), ev["id"], "gap", 50000, 70000, 2500.0, 3500.0, 0.0, 0, 1, "[SYNTHETIC] Unrecorded gap: 1000s missing")
            )
            await db.execute(
                """INSERT INTO recovery_segments (id, evidence_id, segment_type, start_frame, end_frame, start_time, end_time, completeness, nal_units_found, is_simulated, notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (str(uuid.uuid4()), ev["id"], "recovered", 70000, 144000, 3500.0, 7200.0, 0.85, 14200, 1, "[SYNTHETIC] Recovered stream fragments from unallocated sectors")
            )

    await db.commit()

    # ── CAMERA TOPOLOGY ────────────────────────────────────
    print("[FORGE-VISION] Seeding camera topology...")
    for (cam_id, cam_name, loc, x, y, conn) in DEMO_TOPOLOGY:
        async with db.execute("SELECT id FROM camera_topology WHERE case_id = 'CASE-DEMO001' AND camera_id = ?", (cam_id,)) as cur:
            if not await cur.fetchone():
                await db.execute(
                    """INSERT INTO camera_topology (id, case_id, camera_id, camera_name, location_label, x_pos, y_pos, connected_camera_ids, notes, created_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (str(uuid.uuid4()), "CASE-DEMO001", cam_id, cam_name, loc, x, y, json.dumps(conn), f"Spatial node for {loc}", now)
                )
    await db.commit()

    # ── BOOKMARKS ──────────────────────────────────────────
    print("[FORGE-VISION] Seeding bookmarks...")
    for bm in DEMO_BOOKMARKS:
        async with db.execute("SELECT id FROM bookmarks WHERE id = ?", (bm["id"],)) as cur:
            if not await cur.fetchone():
                await db.execute(
                    """INSERT INTO bookmarks (id, case_id, evidence_id, camera_id, frame_number, timestamp_in_video, title, notes, tag, created_by, created_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (bm["id"], bm["case_id"], bm["evidence_id"], bm["camera_id"], bm["frame_number"], bm["timestamp_in_video"], bm["title"], bm["notes"], bm["tag"], "Arjun Sharma (Investigator)", now)
                )
    await db.commit()

    # ── AI FINDINGS & REID HOPS ────────────────────────────
    print("[FORGE-VISION] Seeding AI findings & ReID hops...")
    for ev in DEMO_EVIDENCE:
        try:
            async with db.execute("SELECT COUNT(*) as cnt FROM ai_findings WHERE evidence_id = ?", (ev["id"],)) as cur:
                if (await cur.fetchone())["cnt"] == 0:
                    for obj in ["person", "car", "anomaly"]:
                        await db.execute(
                            """INSERT INTO ai_findings (id, evidence_id, case_id, finding_type, frame_number, timestamp_in_video, confidence, bounding_box, label, description, is_simulated, requires_review, generated_at, generator)
                               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (
                                str(uuid.uuid4()), ev["id"], ev["case_id"],
                                obj if obj != "car" else "vehicle", 1500, "00:10:00",
                                0.88, json.dumps([120, 80, 200, 300]),
                                obj.capitalize(), f"AI Detection: {obj} identified in field of view.",
                                0 if ev.get("source_type") == "PUBLIC_RESEARCH_DATASET" else 1,
                                1, now, "YOLOv8-Surveillance"
                            )
                        )
        except Exception as e:
            print(f"[SEED AI FINDINGS ERR]: {e}")
    await db.commit()

    # ── CUSTODY LEDGER ─────────────────────────────────────
    print("[FORGE-VISION] Seeding chain of custody ledger...")
    try:
        for idx, ev in enumerate(DEMO_EVIDENCE, 1):
            async with db.execute("SELECT COUNT(*) as cnt FROM custody_ledger WHERE evidence_id = ?", (ev["id"],)) as cur:
                if (await cur.fetchone())["cnt"] == 0:
                    entry_id = str(uuid.uuid4())
                    ts = ev.get("ingested_at", now)
                    detail_str = json.dumps({"action": "Forensic Ingestion", "source": ev.get("source_platform", "Direct"), "vendor": ev.get("source_vendor", "Generic"), "sha256": ev["sha256"]})
                    this_hash = compute_custody_entry_hash(
                        seq=idx, case_id=ev["case_id"], evidence_id=ev["id"],
                        action="ingest" if ev.get("source_type") != "PUBLIC_RESEARCH_DATASET" else "dataset_imported",
                        operator_id="user-investigator-01",
                        operator_role="investigator", timestamp=ts,
                        evidence_hash_before=None, evidence_hash_after=ev["sha256"],
                        detail=detail_str, prev_entry_hash="0" * 64
                    )
                    await db.execute(
                        """INSERT INTO custody_ledger (id, seq, case_id, evidence_id, action, operator_id, operator_role, timestamp, evidence_hash_before, evidence_hash_after, detail, prev_entry_hash, this_entry_hash)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (entry_id, idx, ev["case_id"], ev["id"], "ingest", "user-investigator-01", "investigator", ts, None, ev["sha256"], detail_str, "0" * 64, this_hash)
                    )
    except Exception as e:
        print(f"[SEED CUSTODY ERR]: {e}")
    await db.commit()
    print("[FORGE-VISION] Database seeded successfully!")


if __name__ == "__main__":
    asyncio.run(seed())
