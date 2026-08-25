"""
FORGE-VISION — Simulated AI Analysis Engine
All outputs are clearly labeled as simulated — architecture ready for real model drop-in.
Provides: object/person/vehicle detection, cross-camera re-ID, motion heatmap, camera tamper.
"""
import json
import os
import random
import uuid
from datetime import datetime, timezone
from typing import Optional

import numpy as np
from PIL import Image


# ─────────────────────────────────────────────────────────────────────────────
# OBJECT / PERSON / VEHICLE DETECTION (SIMULATED)
# Real implementation: swap in YOLO v8/v9 model
# ─────────────────────────────────────────────────────────────────────────────

DETECTION_CLASSES = [
    "person", "car", "motorcycle", "truck", "bus", "bicycle",
    "van", "auto-rickshaw", "pedestrian",
]

def simulate_object_detection(evidence_id: str, frame_count: int, fps: float = 25.0) -> list[dict]:
    """
    Produce realistic-looking simulated detections tied to real frame numbers.
    Seed is deterministic per evidence_id so re-runs produce same results.
    """
    rng = random.Random(hash(evidence_id) % 999999)
    findings = []

    if frame_count <= 0:
        frame_count = 750  # 30 seconds at 25fps default

    # Generate 5-15 detection events
    n_events = rng.randint(5, 15)
    for _ in range(n_events):
        frame = rng.randint(1, frame_count)
        timestamp = f"00:{int(frame / fps / 60):02d}:{int(frame / fps) % 60:02d}.{int((frame / fps % 1) * 100):02d}"
        cls = rng.choice(DETECTION_CLASSES)
        conf = round(rng.uniform(0.52, 0.97), 3)
        w = rng.randint(40, 300)
        h = rng.randint(40, 280)
        x = rng.randint(0, max(1, 1280 - w))
        y = rng.randint(0, max(1, 720 - h))

        findings.append({
            "id": str(uuid.uuid4()),
            "finding_type": "vehicle" if cls in {"car","truck","bus","van","motorcycle"} else "object" if cls != "person" else "person",
            "frame_number": frame,
            "timestamp_in_video": timestamp,
            "confidence": conf,
            "bounding_box": [x, y, w, h],
            "label": cls,
            "description": f"[SIMULATED] {cls.title()} detected at frame {frame} with confidence {conf:.0%}.",
            "is_simulated": True,
            "requires_review": True,
            "generator": "SimulatedYOLOv8 [Real: swap in YOLO model weights]",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        })

    return sorted(findings, key=lambda x: x["frame_number"])


# ─────────────────────────────────────────────────────────────────────────────
# CROSS-CAMERA RE-IDENTIFICATION (SIMULATED)
# Real implementation: ReID model (e.g., fast-reid, torchreid)
# ─────────────────────────────────────────────────────────────────────────────

def simulate_reid_hops(
    case_id: str,
    evidence_items: list[dict],  # list of {evidence_id, camera_id, timestamp_start}
    subject_label: str = "Suspect A",
) -> list[dict]:
    """
    Simulate cross-camera re-identification hops for a suspect/vehicle.
    Explicit disclaimer: appearance-based similarity, not biometric identity.
    """
    rng = random.Random(hash(case_id + subject_label) % 444444)
    hops = []

    if len(evidence_items) < 2:
        return hops

    # Create a realistic path through cameras
    path = rng.sample(evidence_items, min(len(evidence_items), rng.randint(2, 4)))

    for i in range(len(path) - 1):
        src = path[i]
        dst = path[i + 1]
        similarity = round(rng.uniform(0.61, 0.89), 3)
        hops.append({
            "id": str(uuid.uuid4()),
            "case_id": case_id,
            "subject_label": subject_label,
            "from_evidence_id": src["evidence_id"],
            "from_frame": rng.randint(50, 500),
            "from_timestamp": src.get("timestamp_start", ""),
            "to_evidence_id": dst["evidence_id"],
            "to_frame": rng.randint(50, 500),
            "to_timestamp": dst.get("timestamp_start", ""),
            "similarity_score": similarity,
            "match_basis": rng.choice([
                "clothing color + build",
                "vehicle color + type",
                "gait pattern + clothing",
                "vehicle make + color",
            ]),
            "is_simulated": True,
            "disclaimer": "APPEARANCE-BASED SIMILARITY ONLY. Not biometric identification. Requires investigator verification.",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    return hops


# ─────────────────────────────────────────────────────────────────────────────
# MOTION HEATMAP (REAL — frame differencing, no GPU)
# ─────────────────────────────────────────────────────────────────────────────

def generate_motion_heatmap(file_path: str, output_path: str, max_frames: int = 200) -> dict:
    """
    Real motion heatmap via frame differencing using ffmpeg + PIL/numpy.
    Extracts frames at 1fps, computes pixel-wise absolute difference accumulation.
    """
    import subprocess
    import tempfile
    import shutil

    tmp_dir = tempfile.mkdtemp(prefix="forge_heatmap_")
    try:
        # Extract 1 frame per second
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", file_path,
             "-vf", f"fps=1,scale=320:180",
             "-vframes", str(max_frames),
             os.path.join(tmp_dir, "frame_%04d.jpg")],
            capture_output=True, timeout=60,
        )

        frames = sorted([
            os.path.join(tmp_dir, f) for f in os.listdir(tmp_dir) if f.endswith(".jpg")
        ])

        if len(frames) < 2:
            return {"error": "Not enough frames for heatmap", "is_simulated": False}

        # Accumulate differences
        prev = np.array(Image.open(frames[0]).convert("L"), dtype=np.float32)
        accumulated = np.zeros_like(prev)

        for frame_path in frames[1:]:
            curr = np.array(Image.open(frame_path).convert("L"), dtype=np.float32)
            diff = np.abs(curr - prev)
            accumulated += diff
            prev = curr

        # Normalize and colorize
        if accumulated.max() > 0:
            normalized = (accumulated / accumulated.max() * 255).astype(np.uint8)
        else:
            normalized = accumulated.astype(np.uint8)

        # Apply colormap (blue→green→red) via manual LUT
        h, w = normalized.shape
        heatmap = np.zeros((h, w, 3), dtype=np.uint8)
        heatmap[:, :, 0] = np.clip(normalized * 2 - 255, 0, 255)  # Red
        heatmap[:, :, 1] = np.clip(255 - np.abs(normalized - 128) * 2, 0, 255)  # Green
        heatmap[:, :, 2] = np.clip(255 - normalized * 2, 0, 255)  # Blue

        heatmap_img = Image.fromarray(heatmap)
        heatmap_img.save(output_path, format="JPEG", quality=90)

        return {
            "heatmap_path": output_path,
            "frames_analyzed": len(frames),
            "resolution": f"{w}x{h}",
            "is_simulated": False,
            "description": "Motion accumulation heatmap (frame-differencing). Red = high motion concentration.",
        }

    except Exception as e:
        return {"error": str(e), "is_simulated": False}
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────
# CAMERA-SIDE TAMPER DETECTION (mix of real + simulated)
# ─────────────────────────────────────────────────────────────────────────────

def detect_camera_tampering(file_path: str, evidence_id: str) -> dict:
    """
    Real: scene-change frequency analysis (proxy for blackout/spray events).
    Simulated: defocus, specific coverage detection (labeled).
    """
    import subprocess

    rng = random.Random(hash(evidence_id) % 11111)
    findings = []

    # Real: detect prolonged black frames (camera blackout / unplugging)
    try:
        result = subprocess.run(
            ["ffmpeg", "-i", file_path,
             "-vf", "blackdetect=d=0.5:pix_th=0.10",
             "-an", "-f", "null", "-"],
            capture_output=True, text=True, timeout=60,
        )
        blackout_count = result.stderr.count("black_start")
        if blackout_count > 0:
            findings.append({
                "tamper_type": "blackout",
                "count": blackout_count,
                "confidence": min(0.95, 0.5 + blackout_count * 0.1),
                "severity": "high" if blackout_count > 2 else "medium",
                "detail": f"{blackout_count} blackout segment(s) detected — possible camera disconnection or deliberate covering.",
                "is_simulated": False,
            })
    except Exception:
        pass

    # Simulated: defocus, spray, angle shift
    for tamper_type, label in [
        ("defocus", "Gradual focus degradation"),
        ("spray", "Lens spray/covering"),
        ("angle_shift", "Sudden camera angle change"),
    ]:
        if rng.random() < 0.25:  # 25% chance for demo realism
            findings.append({
                "tamper_type": tamper_type,
                "confidence": round(rng.uniform(0.45, 0.80), 3),
                "severity": "medium",
                "detail": f"[SIMULATED] {label} detected. GPU-based optical flow model required for real implementation.",
                "is_simulated": True,
            })

    suspicious = any(f["severity"] in {"high", "medium"} for f in findings)
    return {
        "camera_tamper_findings": findings,
        "tamper_detected": suspicious,
        "total_findings": len(findings),
        "disclaimer": "Camera tamper detection is indicative only. All findings require investigator review.",
    }
