# Modular Vendor Adapter System

## Architectural Principle
Surveillance hardware manufacturers (OEMs) often employ proprietary container headers, specialized timestamps, or custom filesystem layouts. FORGE-VISION implements an open, extensible adapter architecture to handle vendor diversity.

---

## Supported Parsers & Adapter Status

| Vendor / Format | Parser Class | Implementation Status | Features |
|---|---|---|---|
| **Generic Video (MP4 / AVI / MKV / MOV / TS)** | `GenericVideoParser` | **REAL (Production)** | FFprobe JSON parsing, NAL unit continuity scanning, OSD OCR fallback, frame extraction |
| **Hikvision** | `HikvisionParser` | **Simulated / Adapter Required** | `HIKV`, `HKVS` magic signature detection, simulated metadata |
| **Dahua** | `DahuaParser` | **Simulated / Adapter Required** | `DAHUA`, `DH-SD` signature detection, ELA keyframe analysis |
| **CP Plus** | `CPPlusParser` | **Simulated / Adapter Required** | `CPPLUS`, `CP-UVR` signature detection, GOP reconstruction |
| **Matrix** | `MatrixParser` | **Simulated / Adapter Required** | Matrix SATATYA stream signature detection |
| **Uniview** | `UniviewParser` | **Simulated / Adapter Required** | UNV container signature identification |
| **Honeywell** | `HoneywellParser` | **Simulated / Adapter Required** | Honeywell HEN container parsing stub |
| **Godrej** | `GodrejParser` | **Simulated / Adapter Required** | Seethru stream parser stub |
| **TP-Link** | `TPLinkParser` | **Simulated / Adapter Required** | Tapo/VIGI RTSP stream container detection |

---

## How to Add a New Vendor Adapter

1. Subclass `VendorParser` from `backend/app/parsers/__init__.py`:
```python
class CustomOEMParser(VendorParser):
    IS_SIMULATED = False  # Set False if fully implemented

    def detect(self, file_path: str) -> bool:
        with open(file_path, "rb") as f:
            header = f.read(16)
        return header.startswith(b"CUSTOM_OEM_SIG")

    def identify_device(self, file_path: str) -> dict:
        return {"source_vendor": "CustomOEM", "device_model": "NVR-9000"}

    def extract_metadata(self, file_path: str) -> dict:
        # Custom container demuxing logic
        ...

    def confidence_score(self) -> float:
        return 0.95
```

2. Register your parser in `PARSER_REGISTRY` in `backend/app/parsers/__init__.py`.
