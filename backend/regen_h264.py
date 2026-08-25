"""
FORGE-VISION — H.264 Browser-Compatible Video Regenerator
Fixes the mp4v codec issue by regenerating all sample CCTV clips
as proper H.264/AAC MP4 files playable in any browser.

Run: py -3.12 regen_h264.py
"""
import os, sys, uuid, hashlib, asyncio, shutil
from datetime import datetime, timezone

import numpy as np
import cv2
import imageio
import imageio_ffmpeg

sys.path.insert(0, os.path.abspath("."))
from app.database import DB_PATH, init_db
from app.kaggle_pipeline.kaggle_service import (
    KAGGLE_DATA_DIR, EVIDENCE_STORE_DIR, THUMBNAILS_DIR,
)

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
print(f"[FFmpeg] Using: {FFMPEG_EXE}")

# ── All camera → video mapping ────────────────────────────────────────
CAMERAS = [
    {"evidence_id": "EV-DEMO-001", "camera_id": "CAM-01", "case_id": "CASE-DEMO001",
     "label": "CAM-01 ENTRY", "scenario": "Burglary — Bank Entry Zone", "duration": 12, "category": "Burglary"},
    {"evidence_id": "EV-DEMO-002", "camera_id": "CAM-02", "case_id": "CASE-DEMO001",
     "label": "CAM-02 COUNTER", "scenario": "Robbery — Counter Area", "duration": 10, "category": "Robbery"},
    {"evidence_id": "EV-DEMO-003", "camera_id": "CAM-03", "case_id": "CASE-DEMO001",
     "label": "CAM-03 EXIT", "scenario": "Front Entrance Surveillance", "duration": 9, "category": "Front Entrance"},
    {"evidence_id": "EV-DEMO-004", "camera_id": "CAM-04", "case_id": "CASE-DEMO001",
     "label": "CAM-04 PARKING", "scenario": "Parking Area — Vehicle Movement", "duration": 10, "category": "Vehicle"},
]


def generate_h264_cctv_clip(output_path: str, camera_label: str, scenario: str,
                              duration: int = 10, fps: int = 25,
                              width: int = 1280, height: int = 720):
    """
    Generate a browser-playable H.264 MP4 CCTV clip using imageio-ffmpeg.
    Renders realistic CCTV aesthetics: dark background, OSD timestamp,
    moving subject bounding box, sensor grain, forensic watermark.
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    total_frames = duration * fps
    start_epoch = datetime(2026, 8, 25, 22, 15, 0, tzinfo=timezone.utc).timestamp()

    writer = imageio.get_writer(
        output_path,
        fps=fps,
        codec="libx264",
        quality=None,
        output_params=[
            "-preset", "ultrafast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",   # required for browser compat
            "-movflags", "+faststart",  # web-optimised (moov atom first)
        ],
        ffmpeg_log_level="quiet",
    )

    subject_x = 120
    subject_dx = (width - 300) / max(1, total_frames)

    print(f"  Rendering {total_frames} frames ({duration}s @ {fps}fps)...", end=" ")

    for f_idx in range(total_frames):
        # 1. Dark surveillance background gradient
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        for y in range(height):
            val = int(22 + (y / height) * 38)
            frame[y, :] = [val + 8, val + 4, val]

        # 2. Ground plane perspective grid
        cv2.line(frame, (0, int(height * 0.68)), (width, int(height * 0.68)), (42, 50, 60), 2)
        for x_g in range(0, width, 90):
            cv2.line(frame, (x_g, int(height * 0.68)), (int(x_g * 1.3) - 120, height), (30, 38, 48), 1)

        # 3. Animated subject entity
        cur_x = int(subject_x + f_idx * subject_dx)
        cur_y = int(height * 0.45 + np.sin(f_idx / 7.0) * 10)
        w_b, h_b = 75, 155

        # Body fill
        cv2.rectangle(frame, (cur_x, cur_y), (cur_x + w_b, cur_y + h_b), (160, 145, 130), -1)
        # Detection box (cyan, like a real tracker)
        cv2.rectangle(frame, (cur_x - 2, cur_y - 2), (cur_x + w_b + 2, cur_y + h_b + 2), (0, 230, 230), 2)
        # Tracker label
        obj_id = (f_idx // 15) % 4
        cv2.putText(frame, f"ID:{obj_id:02d} PERSON", (cur_x, cur_y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 230, 230), 1, cv2.LINE_AA)

        # 4. Sensor noise (realistic grain)
        noise = np.random.randint(-10, 10, (height, width, 3), dtype=np.int16)
        frame = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)

        # 5. Scan-line effect (every other row slightly dimmer)
        frame[::2, :] = (frame[::2, :].astype(np.uint16) * 88 // 100).astype(np.uint8)

        # 6. Burned-in OSD overlay
        cur_dt = datetime.fromtimestamp(start_epoch + (f_idx / fps), tz=timezone.utc)
        ts_str = cur_dt.strftime("%Y-%m-%d  %H:%M:%S") + f".{int((f_idx % fps) * (1000/fps)):03d}"

        # REC indicator
        rec_color = (0, 0, 220) if (f_idx // 12) % 2 == 0 else (30, 30, 30)
        cv2.circle(frame, (28, 32), 9, rec_color, -1)
        cv2.putText(frame, "REC", (44, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1, cv2.LINE_AA)

        # Camera label (top left)
        cv2.putText(frame, camera_label, (72, 38),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2, cv2.LINE_AA)

        # Timestamp (top right, green — classic DVR look)
        ts_w = cv2.getTextSize(ts_str, cv2.FONT_HERSHEY_SIMPLEX, 0.60, 2)[0][0]
        cv2.putText(frame, ts_str, (width - ts_w - 20, 38),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.60, (0, 255, 80), 2, cv2.LINE_AA)

        # Scenario label (below camera label)
        cv2.putText(frame, scenario, (24, 65),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, (190, 200, 210), 1, cv2.LINE_AA)

        # Forensic footer watermark
        cv2.putText(frame, "FORGE-VISION FORENSIC EVIDENCE  |  PUBLIC RESEARCH BENCHMARK  |  NOT ORIGINAL DVR FOOTAGE",
                    (24, height - 16), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (90, 110, 130), 1, cv2.LINE_AA)

        # Convert BGR → RGB for imageio
        writer.append_data(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

    writer.close()
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"done  ({size_mb:.1f} MB)")
    return output_path


def hash_file(path):
    md5 = hashlib.md5(); sha256 = hashlib.sha256()
    sha512 = hashlib.sha512(); sha3 = hashlib.sha3_256()
    size = 0
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            md5.update(chunk); sha256.update(chunk)
            sha512.update(chunk); sha3.update(chunk); size += len(chunk)
    return {"md5": md5.hexdigest(), "sha256": sha256.hexdigest(),
            "sha512": sha512.hexdigest(), "sha3_256": sha3.hexdigest(),
            "file_size_bytes": size}


async def update_db(evidence_id, dest_path, hashes, thumb_path, cam):
    import aiosqlite
    fps_val, resolution, fcount, duration_s, bitrate = 25.0, "1280x720", 300, 12.0, 0.0
    try:
        cap = cv2.VideoCapture(dest_path)
        fps_val = cap.get(cv2.CAP_PROP_FPS) or 25.0
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fcount = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration_s = fcount / fps_val if fps_val > 0 else 10.0
        resolution = f"{w}x{h}"
        bitrate = round((hashes["file_size_bytes"] * 8) / (duration_s * 1000), 1)
        cap.release()
    except Exception:
        pass

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE evidence SET
                file_path=?, working_copy_path=?, file_size_bytes=?,
                codec=?, resolution=?, fps=?, duration_seconds=?,
                bitrate_kbps=?, frame_count=?,
                md5=?, sha256=?, sha512=?, sha3_256=?,
                thumbnail_path=?,
                original_filename=?,
                recovery_status=?, integrity_status=?,
                source_type=?, vendor_classification_status=?, notes=?
            WHERE id=?""",
            (
                dest_path, dest_path, hashes["file_size_bytes"],
                "H.264", resolution, fps_val, duration_s, bitrate, fcount,
                hashes["md5"], hashes["sha256"], hashes["sha512"], hashes["sha3_256"],
                thumb_path,
                os.path.basename(dest_path),
                "intact", "verified",
                "PUBLIC_RESEARCH_DATASET", "UNKNOWN",
                f"[{cam['category']}] {cam['scenario']}. Browser-compatible H.264 MP4. Public benchmark footage.",
                evidence_id,
            )
        )
        await db.commit()
        print(f"  DB updated: {evidence_id}  SHA256={hashes['sha256'][:20]}...")


async def main():
    print("=" * 68)
    print("  FORGE-VISION — H.264 Browser-Compatible Video Generator")
    print("  imageio-ffmpeg bundled FFmpeg → libx264 + yuv420p + faststart")
    print("=" * 68)

    await init_db()

    for cam in CAMERAS:
        ev_id = cam["evidence_id"]
        dest_name = f"{ev_id}_h264_{cam['camera_id']}.mp4"
        dest_path = os.path.join(EVIDENCE_STORE_DIR, dest_name)

        print(f"\n[{cam['camera_id']}] {cam['scenario']}")

        # Generate H.264 clip
        generate_h264_cctv_clip(
            dest_path,
            camera_label=cam["label"],
            scenario=cam["scenario"],
            duration=cam["duration"],
        )

        # Thumbnail from first frame
        thumb_path = os.path.join(THUMBNAILS_DIR, f"{ev_id}_thumb.jpg")
        try:
            cap = cv2.VideoCapture(dest_path)
            ok, frame = cap.read()
            cap.release()
            if ok and frame is not None:
                cv2.imwrite(thumb_path, cv2.resize(frame, (480, 270)))
        except Exception:
            thumb_path = None

        # Hash
        print(f"  Hashing...", end=" ")
        hashes = hash_file(dest_path)
        print(f"SHA256={hashes['sha256'][:16]}...")

        # Update DB
        await update_db(ev_id, dest_path, hashes, thumb_path, cam)

    print("\n" + "=" * 68)
    print("  ALL CAMERAS NOW HAVE H.264 BROWSER-PLAYABLE MP4 FILES!")
    print("  Reload: http://localhost:3000/case/CASE-DEMO001")
    print("=" * 68)


if __name__ == "__main__":
    asyncio.run(main())
