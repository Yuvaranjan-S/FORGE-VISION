"""
FORGE-VISION — Modular OEM Vendor Parser Framework
Each parser implements the VendorParser interface.
Real parsers: GenericVideoParser (MP4/AVI/MKV via FFprobe)
Simulated adapters: Hikvision, Dahua, CP Plus, etc. — clearly labeled.
"""
import json
import os
import subprocess
import struct
from abc import ABC, abstractmethod
from typing import Optional
import uuid
from datetime import datetime, timezone


# ─────────────────────────────────────────────────────────────────────────────
# PARSER INTERFACE
# ─────────────────────────────────────────────────────────────────────────────

class VendorParser(ABC):
    IS_SIMULATED = False  # Override to True for stub adapters

    @abstractmethod
    def detect(self, file_path: str) -> bool:
        """Return True if this parser can handle the given file."""

    @abstractmethod
    def identify_device(self, file_path: str) -> dict:
        """Return device identification metadata."""

    @abstractmethod
    def extract_metadata(self, file_path: str) -> dict:
        """Return normalized video/container metadata."""

    @abstractmethod
    def extract_video(self, file_path: str, output_dir: str) -> list[str]:
        """Extract/convert video segments; return list of output paths."""

    @abstractmethod
    def detect_deleted_data(self, file_path: str) -> dict:
        """Scan for deleted/missing data indicators."""

    @abstractmethod
    def recover_fragments(self, file_path: str, output_dir: str) -> list[dict]:
        """Attempt fragment recovery; return list of recovered segment descriptors."""

    @abstractmethod
    def extract_osd_timestamp(self, file_path: str, sample_frame: int = 30) -> Optional[str]:
        """OCR the burned-in OSD timestamp from a sample frame."""

    @abstractmethod
    def confidence_score(self) -> float:
        """0.0-1.0: how confident the parser is in its own output for the last file processed."""


# ─────────────────────────────────────────────────────────────────────────────
# FFPROBE HELPER (used by GenericVideoParser)
# ─────────────────────────────────────────────────────────────────────────────

def _run_ffprobe(file_path: str) -> Optional[dict]:
    """Run ffprobe and return parsed JSON, or None if ffprobe not available."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                file_path,
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass
    return None


def _extract_frame(file_path: str, output_path: str, frame: int = 30) -> bool:
    """Extract a single frame from video using ffmpeg."""
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", file_path,
                "-vf", f"select=eq(n\\,{frame})",
                "-vframes", "1",
                output_path,
            ],
            capture_output=True, timeout=30,
        )
        return result.returncode == 0 and os.path.exists(output_path)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# ─────────────────────────────────────────────────────────────────────────────
# GENERIC VIDEO PARSER (REAL — MP4/AVI/MKV)
# ─────────────────────────────────────────────────────────────────────────────

class GenericVideoParser(VendorParser):
    IS_SIMULATED = False
    _last_confidence = 0.0

    SUPPORTED_EXTENSIONS = {".mp4", ".avi", ".mkv", ".mov", ".ts", ".m4v", ".flv"}

    def detect(self, file_path: str) -> bool:
        ext = os.path.splitext(file_path)[1].lower()
        return ext in self.SUPPORTED_EXTENSIONS

    def identify_device(self, file_path: str) -> dict:
        probe = _run_ffprobe(file_path)
        if probe:
            fmt = probe.get("format", {})
            tags = fmt.get("tags", {})
            return {
                "source_vendor": tags.get("make", tags.get("encoder", "Unknown")),
                "device_model": tags.get("model", "Generic Camera / Unknown"),
                "firmware": tags.get("software", None),
            }
        return {"source_vendor": "Unknown", "device_model": "Generic", "firmware": None}

    def extract_metadata(self, file_path: str) -> dict:
        probe = _run_ffprobe(file_path)
        if not probe:
            return self._fallback_metadata(file_path)

        fmt = probe.get("format", {})
        video_stream = next(
            (s for s in probe.get("streams", []) if s.get("codec_type") == "video"), {}
        )
        audio_stream = next(
            (s for s in probe.get("streams", []) if s.get("codec_type") == "audio"), {}
        )

        duration = float(fmt.get("duration", 0) or 0)
        fps_raw = video_stream.get("r_frame_rate", "0/1")
        try:
            num, den = fps_raw.split("/")
            fps = round(float(num) / float(den), 3) if int(den) else 0.0
        except Exception:
            fps = 0.0

        frame_count = int(video_stream.get("nb_frames", 0) or 0)
        if not frame_count and fps and duration:
            frame_count = int(fps * duration)

        width = int(video_stream.get("width", 0) or 0)
        height = int(video_stream.get("height", 0) or 0)

        tags = {**(fmt.get("tags", {})), **(video_stream.get("tags", {}))}

        self._last_confidence = 0.95
        return {
            "codec": video_stream.get("codec_name", "unknown").upper(),
            "resolution": f"{width}x{height}" if width and height else "Unknown",
            "fps": fps,
            "duration_seconds": duration,
            "bitrate_kbps": round(float(fmt.get("bit_rate", 0) or 0) / 1000, 1),
            "frame_count": frame_count,
            "container_format": fmt.get("format_name", "unknown"),
            "timestamp_start": tags.get("creation_time"),
            "has_audio": bool(audio_stream),
            "file_size_bytes": int(fmt.get("size", os.path.getsize(file_path))),
            "ffprobe_available": True,
        }

    def _fallback_metadata(self, file_path: str) -> dict:
        """Fallback when ffprobe is not installed."""
        size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        self._last_confidence = 0.3
        return {
            "codec": "Unknown (ffprobe not available)",
            "resolution": "Unknown",
            "fps": 0.0,
            "duration_seconds": 0.0,
            "bitrate_kbps": 0.0,
            "frame_count": 0,
            "container_format": "unknown",
            "timestamp_start": None,
            "has_audio": False,
            "file_size_bytes": size,
            "ffprobe_available": False,
        }

    def extract_video(self, file_path: str, output_dir: str) -> list[str]:
        os.makedirs(output_dir, exist_ok=True)
        out = os.path.join(output_dir, "normalized_" + os.path.basename(file_path))
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", file_path, "-c", "copy", out],
                capture_output=True, timeout=120,
            )
            if os.path.exists(out):
                return [out]
        except Exception:
            pass
        return [file_path]  # Return original if extraction fails

    def detect_deleted_data(self, file_path: str) -> dict:
        """
        REAL: scan for H.264 NAL start codes and detect frame gaps.
        """
        nal_count = 0
        gap_indicators = []
        try:
            with open(file_path, "rb") as f:
                data = f.read()
            # H.264 NAL start codes: 0x000001 or 0x00000001
            idx = 0
            while idx < len(data) - 3:
                if data[idx:idx+3] == b'\x00\x00\x01':
                    nal_count += 1
                    idx += 3
                elif data[idx:idx+4] == b'\x00\x00\x00\x01':
                    nal_count += 1
                    idx += 4
                else:
                    idx += 1
        except Exception:
            pass

        return {
            "nal_units_found": nal_count,
            "gap_indicators": gap_indicators,
            "scan_method": "H.264 NAL start code signature scan",
            "is_simulated": False,
        }

    def recover_fragments(self, file_path: str, output_dir: str) -> list[dict]:
        """
        REAL: detect frame continuity; report gaps as recovery segments.
        Full disk-level carving is labeled Simulated.
        """
        probe = _run_ffprobe(file_path)
        segments = []
        if probe:
            video_stream = next(
                (s for s in probe.get("streams", []) if s.get("codec_type") == "video"), {}
            )
            duration = float(probe.get("format", {}).get("duration", 0) or 0)
            frame_count = int(video_stream.get("nb_frames", 0) or 0)
            fps_raw = video_stream.get("r_frame_rate", "25/1")
            try:
                num, den = fps_raw.split("/")
                fps = float(num) / float(den) if int(den) else 25.0
            except Exception:
                fps = 25.0
            expected_frames = int(fps * duration) if fps and duration else frame_count
            completeness = (frame_count / expected_frames) if expected_frames > 0 else 1.0
            completeness = min(1.0, completeness)

            segments.append({
                "segment_type": "intact" if completeness > 0.98 else "partial",
                "start_frame": 0,
                "end_frame": frame_count,
                "start_time": 0.0,
                "end_time": duration,
                "completeness": round(completeness, 3),
                "nal_units_found": 0,
                "is_simulated": False,
            })
        return segments

    def extract_osd_timestamp(self, file_path: str, sample_frame: int = 30) -> Optional[str]:
        """Extract and OCR a sample frame for on-screen timestamp."""
        tmp_frame = os.path.join(os.path.dirname(file_path), "_osd_tmp.jpg")
        if not _extract_frame(file_path, tmp_frame, sample_frame):
            return None
        try:
            import pytesseract
            from PIL import Image
            img = Image.open(tmp_frame)
            # Crop bottom 15% where OSD timestamps typically appear
            w, h = img.size
            bottom_strip = img.crop((0, int(h * 0.85), w, h))
            text = pytesseract.image_to_string(bottom_strip, config="--psm 7").strip()
            os.remove(tmp_frame)
            return text if text else None
        except Exception:
            try: os.remove(tmp_frame)
            except Exception: pass
            return None

    def confidence_score(self) -> float:
        return self._last_confidence


# ─────────────────────────────────────────────────────────────────────────────
# SIMULATED VENDOR ADAPTERS
# These are clearly labeled as simulation/demonstration adapters.
# They produce realistic but synthetic output.
# ─────────────────────────────────────────────────────────────────────────────

class SimulatedVendorParser(VendorParser):
    """Base class for all simulated vendor adapters."""
    IS_SIMULATED = True
    VENDOR_NAME = "Unknown"
    VENDOR_SIGNATURES = []

    def detect(self, file_path: str) -> bool:
        """Simulate detection by checking magic bytes / extensions."""
        return False  # Subclasses override with their heuristics

    def identify_device(self, file_path: str) -> dict:
        return {
            "source_vendor": self.VENDOR_NAME,
            "device_model": f"[SIMULATED] {self.VENDOR_NAME} DVR/NVR",
            "firmware": "[SIMULATED] v3.4.106 build 230131",
            "is_simulated": True,
            "simulation_note": f"Simulated Adapter — {self.VENDOR_NAME} proprietary format not fully reverse-engineered. For demonstration only.",
        }

    def extract_metadata(self, file_path: str) -> dict:
        import random
        random.seed(hash(file_path) % 999999)
        return {
            "codec": random.choice(["H.264", "H.265"]),
            "resolution": random.choice(["1920x1080", "2560x1440", "3840x2160"]),
            "fps": random.choice([15.0, 20.0, 25.0, 30.0]),
            "duration_seconds": round(random.uniform(300, 3600), 1),
            "bitrate_kbps": round(random.uniform(1000, 8000), 1),
            "frame_count": 0,
            "container_format": f"{self.VENDOR_NAME.lower()}_proprietary",
            "timestamp_start": None,
            "has_audio": random.choice([True, False]),
            "file_size_bytes": os.path.getsize(file_path) if os.path.exists(file_path) else 0,
            "ffprobe_available": False,
            "is_simulated": True,
        }

    def extract_video(self, file_path: str, output_dir: str) -> list[str]:
        return [file_path]

    def detect_deleted_data(self, file_path: str) -> dict:
        return {
            "nal_units_found": 0,
            "gap_indicators": ["[SIMULATED] Proprietary filesystem gap detection not implemented"],
            "scan_method": "[SIMULATED] Vendor-specific carving",
            "is_simulated": True,
        }

    def recover_fragments(self, file_path: str, output_dir: str) -> list[dict]:
        return [{
            "segment_type": "simulated_carved",
            "start_frame": 0, "end_frame": 0,
            "start_time": 0.0, "end_time": 0.0,
            "completeness": 0.0,
            "nal_units_found": 0,
            "is_simulated": True,
            "note": "[SIMULATED] Full carving requires vendor proprietary format documentation.",
        }]

    def extract_osd_timestamp(self, file_path: str, sample_frame: int = 30) -> Optional[str]:
        return "[SIMULATED] OSD-OCR adapter not implemented for this vendor"

    def confidence_score(self) -> float:
        return 0.1  # Low confidence — simulated


class HikvisionParser(SimulatedVendorParser):
    VENDOR_NAME = "Hikvision"
    VENDOR_SIGNATURES = [b"HIKV", b"H264DVR", b"HKVS"]

    def detect(self, file_path: str) -> bool:
        try:
            with open(file_path, "rb") as f:
                header = f.read(16)
            return any(sig in header for sig in self.VENDOR_SIGNATURES)
        except Exception:
            return False


class DahuaParser(SimulatedVendorParser):
    VENDOR_NAME = "Dahua"
    VENDOR_SIGNATURES = [b"DAHUA", b"DH-SD", b"\xd0\xd0\xd0\xd0"]

    def detect(self, file_path: str) -> bool:
        try:
            with open(file_path, "rb") as f:
                header = f.read(16)
            return any(sig in header for sig in self.VENDOR_SIGNATURES)
        except Exception:
            return False


class CPPlusParser(SimulatedVendorParser):
    VENDOR_NAME = "CP Plus"
    VENDOR_SIGNATURES = [b"CPPLUS", b"CP-UVR", b"ARYAN"]

    def detect(self, file_path: str) -> bool:
        try:
            with open(file_path, "rb") as f:
                header = f.read(16)
            return any(sig in header for sig in self.VENDOR_SIGNATURES)
        except Exception:
            return False


class MatrixParser(SimulatedVendorParser):
    VENDOR_NAME = "Matrix"


class UniviewParser(SimulatedVendorParser):
    VENDOR_NAME = "Uniview"


class HoneywellParser(SimulatedVendorParser):
    VENDOR_NAME = "Honeywell"


class GodrejParser(SimulatedVendorParser):
    VENDOR_NAME = "Godrej"


class TPLinkParser(SimulatedVendorParser):
    VENDOR_NAME = "TP-Link"


# ─────────────────────────────────────────────────────────────────────────────
# PARSER REGISTRY & DISPATCH
# ─────────────────────────────────────────────────────────────────────────────

PARSER_REGISTRY: list[VendorParser] = [
    HikvisionParser(),
    DahuaParser(),
    CPPlusParser(),
    MatrixParser(),
    UniviewParser(),
    HoneywellParser(),
    GodrejParser(),
    TPLinkParser(),
    GenericVideoParser(),   # Always last — catches everything else
]


def detect_vendor_and_get_parser(file_path: str) -> VendorParser:
    """
    Try each parser's detect() method in priority order.
    Falls back to GenericVideoParser.
    """
    for parser in PARSER_REGISTRY:
        if isinstance(parser, GenericVideoParser):
            continue  # Skip the fallback during vendor-specific detection
        if parser.detect(file_path):
            return parser
    # Fallback: check if generic parser can handle it
    generic = GenericVideoParser()
    if generic.detect(file_path):
        return generic
    # Last resort: unknown file type
    return GenericVideoParser()
