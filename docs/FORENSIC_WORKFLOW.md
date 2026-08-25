# FORGE-VISION Standard Operating Forensic Workflow

```
ACQUIRE  ──►  PRESERVE  ──►  HASH  ──►  VALIDATE  ──►  IDENTIFY VENDOR
   │
   ▼
EXTRACT METADATA  ──►  NORMALIZE  ──►  RECOVER  ──►  DETECT TAMPERING
   │
   ▼
ANALYZE (YOLO)  ──►  CORRELATE CAMERAS  ──►  INVESTIGATE  ──►  REPORT (65B/BSA)
```

---

## 18-Step Standard Operating Procedure

1. **Case Creation**: An investigator or supervisor opens a formal forensic case record.
2. **Dataset / Evidence Ingestion**: Multi-vendor surveillance footage is uploaded via the Guided Import Wizard.
3. **Provenance Documentation**: Source type (Authorized Export, Research Benchmark, Vendor Sample, Synthetic Demo) is recorded with provider and licensing citations.
4. **Triple-Hash Sealing**: MD5, SHA-256, and SHA3-256 are computed immediately upon ingestion.
5. **Chain-of-Custody Logging**: An immutable entry is appended to the hash-chained ledger.
6. **Automated Vendor Detection**: Magic signatures identify OEM container format (Hikvision, Dahua, CP Plus, Matrix, Uniview, Honeywell, Generic).
7. **Metadata Normalization**: Timestamps, frame rates, resolutions, and codecs are standardized into the Common Evidence Model.
8. **Dual-Timestamp Verification**: Container metadata timestamps are cross-referenced with OSD burned-in timestamps.
9. **Multi-Camera Timeline Indexing**: Synchronized multi-track visual timeline is constructed.
10. **Recording Gap Detection**: Time skips and missing GOP sequences are detected and visually flagged.
11. **Stream Reconstruction / Carving**: H.264/H.265 NAL unit continuity scans extract recoverable fragments from unallocated space.
12. **Authenticity / ELA Analysis**: Keyframe Error Level Analysis (ELA) and frame duplicate detection flag potential splicing.
13. **Camera-Side Tamper Checks**: Scene changes, camera blackouts, and angle shifts are detected.
14. **Assistive AI Object Triage**: YOLOv8 detects persons, vehicles, and objects for rapid evidence prioritization.
15. **Cross-Camera Spatial Correlation**: Spatial topology tracks suspect appearance paths between camera locations.
16. **Natural Language Query**: Grounded query engine filters evidence with exact citation references.
17. **Evidence Bookmarking**: Key frames and timestamps are tagged with investigator notes.
18. **Forensic PDF Export**: Formal court-ready report generated with Section 65B / BSA-2023 Electronic Record Certificate template.
