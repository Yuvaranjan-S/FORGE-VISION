"""
FORGE-VISION — Evidence Authenticity & Tamper Detection Engine
Implements:
  - Error Level Analysis (ELA) — REAL, no GPU needed
  - Frame duplication / near-duplicate detection — REAL
  - Scene-change / camera tamper detection — REAL
  - Clone region, encoding inconsistency — SIMULATED (labeled)
"""
import hashlib
import io
import json
import os
import subprocess
import uuid
from datetime import datetime, timezone
from typing import Optional

import numpy as np
from PIL import Image, ImageChops, ImageEnhance


# ─────────────────────────────────────────────────────────────────────────────
# ERROR LEVEL ANALYSIS (ELA)
# ─────────────────────────────────────────────────────────────────────────────

def run_ela(image_path: str, quality: int = 90, scale: float = 15.0) -> dict:
    """
    Real ELA implementation:
    1. Re-compress the image at a known quality level
    2. Compute pixel-wise absolute difference (original vs re-compressed)
    3. Amplify differences for visibility
    4. High-difference regions may indicate prior localized re-compression (edit/splice indicator)
    Returns path to ELA heatmap image + statistics.
    """
    try:
        original = Image.open(image_path).convert("RGB")
        buf = io.BytesIO()
        original.save(buf, format="JPEG", quality=quality)
        buf.seek(0)
        recompressed = Image.open(buf).convert("RGB")

        diff = ImageChops.difference(original, recompressed)
        diff_arr = np.array(diff, dtype=np.float32)

        # Amplify
        diff_arr = diff_arr * scale
        diff_arr = np.clip(diff_arr, 0, 255).astype(np.uint8)

        ela_img = Image.fromarray(diff_arr)

        # Statistics
        flat = diff_arr.flatten().astype(np.float32)
        mean_ela = float(np.mean(flat))
        max_ela = float(np.max(flat))
        std_ela = float(np.std(flat))

        # Heuristic: high mean ELA or localized hot-spots may indicate tampering
        # Threshold tuned empirically
        suspicious = mean_ela > 12.0 or max_ela > 200.0

        # Save ELA image
        ela_path = image_path.replace(".jpg", "_ela.jpg").replace(".png", "_ela.png")
        if ela_path == image_path:
            ela_path = image_path + "_ela.jpg"
        ela_img.save(ela_path, format="JPEG", quality=95)

        # Confidence: 0.0 = definitely not tampered, 1.0 = definitely tampered
        # Very rough heuristic — always labeled as requiring expert review
        confidence = min(1.0, (mean_ela / 25.0))

        return {
            "check_type": "ela",
            "ela_image_path": ela_path,
            "mean_ela": round(mean_ela, 2),
            "max_ela": round(max_ela, 2),
            "std_ela": round(std_ela, 2),
            "suspicious": suspicious,
            "confidence": round(confidence, 3),
            "severity": "high" if mean_ela > 20 else ("medium" if suspicious else "low"),
            "detail": (
                f"ELA mean={mean_ela:.1f} max={max_ela:.1f}. "
                + ("Localized high-ELA regions detected — possible prior editing/splicing."
                   if suspicious else "No significant ELA anomalies detected.")
            ),
            "is_simulated": False,
            "requires_expert_review": True,
            "note": "ELA is a statistical indicator only. Requires expert human review before any forensic conclusion.",
        }
    except Exception as e:
        return {
            "check_type": "ela",
            "error": str(e),
            "suspicious": False,
            "confidence": 0.0,
            "severity": "low",
            "is_simulated": False,
            "requires_expert_review": True,
        }


# ─────────────────────────────────────────────────────────────────────────────
# FRAME DUPLICATION DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def _perceptual_hash(img: Image.Image, size: int = 8) -> int:
    """Simple average-hash perceptual hash."""
    small = img.convert("L").resize((size, size), Image.LANCZOS)
    arr = np.array(small)
    mean = arr.mean()
    bits = (arr > mean).flatten()
    return int(np.packbits(bits).tobytes().hex(), 16)


def _hamming_distance(h1: int, h2: int) -> int:
    return bin(h1 ^ h2).count("1")


def detect_frame_duplicates(file_path: str, sample_interval: int = 30, threshold: int = 5) -> dict:
    """
    Sample frames at `sample_interval`, compute perceptual hash,
    flag near-duplicate sequences (Hamming distance < threshold).
    Duplicated frames may indicate frame insertion or time manipulation.
    """
    hashes = []
    duplicates = []

    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", file_path],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            return {"check_type": "frame_dup", "error": "ffprobe unavailable", "is_simulated": False}

        probe = json.loads(result.stdout)
        video = next((s for s in probe.get("streams", []) if s.get("codec_type") == "video"), {})
        frame_count = int(video.get("nb_frames", 0) or 0)
        if not frame_count:
            return {"check_type": "frame_dup", "error": "Cannot determine frame count", "is_simulated": False}

        sample_frames = range(0, frame_count, sample_interval)
        tmp_dir = os.path.join(os.path.dirname(file_path), "_frame_tmp")
        os.makedirs(tmp_dir, exist_ok=True)

        for frame_n in list(sample_frames)[:50]:  # Cap at 50 samples
            out = os.path.join(tmp_dir, f"frame_{frame_n}.jpg")
            subprocess.run(
                ["ffmpeg", "-y", "-i", file_path,
                 "-vf", f"select=eq(n\\,{frame_n})",
                 "-vframes", "1", out],
                capture_output=True, timeout=10,
            )
            if os.path.exists(out):
                try:
                    img = Image.open(out)
                    h = _perceptual_hash(img)
                    hashes.append((frame_n, h))
                    os.remove(out)
                except Exception:
                    pass

        # Check for near-duplicates
        for i in range(len(hashes)):
            for j in range(i + 1, len(hashes)):
                dist = _hamming_distance(hashes[i][1], hashes[j][1])
                if dist < threshold:
                    duplicates.append({
                        "frame_a": hashes[i][0],
                        "frame_b": hashes[j][0],
                        "hamming_distance": dist,
                    })

        suspicious = len(duplicates) > 0
        confidence = min(1.0, len(duplicates) * 0.15) if suspicious else 0.0

        # Cleanup
        try:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

        return {
            "check_type": "frame_dup",
            "frames_sampled": len(hashes),
            "duplicate_pairs": duplicates[:10],  # Cap for report size
            "duplicate_count": len(duplicates),
            "suspicious": suspicious,
            "confidence": round(confidence, 3),
            "severity": "high" if len(duplicates) > 5 else ("medium" if suspicious else "low"),
            "detail": (
                f"Sampled {len(hashes)} frames. Found {len(duplicates)} near-duplicate pair(s). "
                + ("Possible frame insertion or loop detected." if suspicious else "No frame duplication detected.")
            ),
            "is_simulated": False,
            "requires_expert_review": True,
        }
    except Exception as e:
        return {"check_type": "frame_dup", "error": str(e), "is_simulated": False, "suspicious": False, "confidence": 0.0}


# ─────────────────────────────────────────────────────────────────────────────
# SCENE CHANGE / CAMERA TAMPER DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def detect_scene_changes(file_path: str, threshold: float = 0.4) -> dict:
    """
    Real: use ffmpeg's scene detection filter to find abrupt scene changes.
    High-score cuts may indicate camera covering, angle shift, or spliced footage.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-f", "lavfi",
                f"-i", f"movie={file_path},select='gt(scene,{threshold})',showinfo",
                "-show_frames",
                "-print_format", "json",
            ],
            capture_output=True, text=True, timeout=60,
        )

        # Use ffmpeg scene detection as alternative
        result2 = subprocess.run(
            [
                "ffmpeg", "-i", file_path,
                "-vf", f"select='gt(scene,{threshold})',metadata=print:file=-",
                "-an", "-f", "null", "-",
            ],
            capture_output=True, text=True, timeout=60,
        )

        scene_changes = []
        for line in result2.stderr.splitlines():
            if "lavfi.scene_score" in line:
                parts = line.split("=")
                if len(parts) == 2:
                    try:
                        score = float(parts[1].strip())
                        scene_changes.append({"score": round(score, 4)})
                    except ValueError:
                        pass

        suspicious = len(scene_changes) > 2
        return {
            "check_type": "scene_change",
            "scene_changes_detected": len(scene_changes),
            "scene_change_details": scene_changes[:20],
            "threshold_used": threshold,
            "suspicious": suspicious,
            "confidence": min(1.0, len(scene_changes) * 0.1),
            "severity": "high" if len(scene_changes) > 5 else ("medium" if suspicious else "low"),
            "detail": (
                f"{len(scene_changes)} abrupt scene change(s) detected above threshold {threshold}. "
                + ("May indicate camera covering, repositioning, or spliced footage." if suspicious
                   else "Normal scene change frequency.")
            ),
            "is_simulated": False,
            "requires_expert_review": True,
        }
    except Exception as e:
        return {
            "check_type": "scene_change",
            "error": str(e),
            "suspicious": False,
            "confidence": 0.0,
            "is_simulated": False,
        }


# ─────────────────────────────────────────────────────────────────────────────
# SIMULATED CHECKS (clearly labeled)
# ─────────────────────────────────────────────────────────────────────────────

def simulate_clone_region_detection(evidence_id: str) -> dict:
    import random
    random.seed(hash(evidence_id) % 77777)
    detected = random.choice([True, False, False])  # Rare
    return {
        "check_type": "clone_region",
        "suspicious": detected,
        "confidence": round(random.uniform(0.3, 0.7), 3) if detected else 0.0,
        "severity": "medium" if detected else "low",
        "detail": "[SIMULATED] Copy-paste/clone region detection — GPU-accelerated model required for real implementation.",
        "bounding_boxes": [{"x": 120, "y": 80, "w": 60, "h": 45}] if detected else [],
        "is_simulated": True,
        "requires_expert_review": True,
    }


def simulate_encoding_consistency(evidence_id: str) -> dict:
    import random
    random.seed(hash(evidence_id) % 33333)
    anomaly = random.choice([True, False, False, False])
    return {
        "check_type": "encoding_inconsistency",
        "suspicious": anomaly,
        "confidence": round(random.uniform(0.4, 0.75), 3) if anomaly else 0.05,
        "severity": "high" if anomaly else "low",
        "detail": (
            "[SIMULATED] GOP structure change detected at 00:12:34 — segment may originate from different encoder."
            if anomaly else
            "[SIMULATED] Encoding parameters consistent throughout clip."
        ),
        "is_simulated": True,
        "requires_expert_review": True,
    }


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ANALYSIS RUNNER
# ─────────────────────────────────────────────────────────────────────────────

def run_full_authenticity_analysis(
    file_path: str,
    evidence_id: str,
    thumbnail_dir: str,
    run_ela: bool = True,
    run_frame_dup: bool = True,
    run_scene_change: bool = True,
) -> dict:
    """
    Run all authenticity checks and return aggregated results.
    """
    results = []

    if run_ela:
        # Extract keyframe for ELA
        keyframe_path = os.path.join(thumbnail_dir, f"{evidence_id}_keyframe.jpg")
        frame_ok = False
        try:
            r = subprocess.run(
                ["ffmpeg", "-y", "-i", file_path, "-vf", "select=eq(n\\,30)", "-vframes", "1", keyframe_path],
                capture_output=True, timeout=20,
            )
            frame_ok = r.returncode == 0 and os.path.exists(keyframe_path)
        except Exception:
            pass

        if frame_ok:
            ela_result = run_ela_analysis(keyframe_path)  # renamed to avoid shadowing
            ela_result["frame_number"] = 30
            results.append(ela_result)
        else:
            results.append({
                "check_type": "ela",
                "error": "Could not extract frame for ELA (ffmpeg unavailable or error)",
                "suspicious": False, "confidence": 0.0, "is_simulated": False,
            })

    if run_frame_dup:
        results.append(detect_frame_duplicates(file_path))

    if run_scene_change:
        results.append(detect_scene_changes(file_path))

    # Simulated checks
    results.append(simulate_clone_region_detection(evidence_id))
    results.append(simulate_encoding_consistency(evidence_id))

    # Overall status
    suspicious_results = [r for r in results if r.get("suspicious")]
    high_severity = [r for r in suspicious_results if r.get("severity") == "high"]

    if high_severity:
        overall_status = "suspected_edit"
        overall_confidence = max(r.get("confidence", 0) for r in high_severity)
    elif suspicious_results:
        overall_status = "inconclusive"
        overall_confidence = max(r.get("confidence", 0) for r in suspicious_results)
    else:
        overall_status = "no_tamper_detected"
        overall_confidence = 0.0

    return {
        "authenticity_status": overall_status,
        "overall_confidence": round(overall_confidence, 3),
        "findings": results,
        "finding_count": len(results),
        "suspicious_count": len(suspicious_results),
        "disclaimer": "All authenticity findings require expert human review. This tool flags potential anomalies — it does not reach forensic conclusions.",
    }


# Alias to avoid shadowing the module-level function
run_ela_analysis = run_ela
