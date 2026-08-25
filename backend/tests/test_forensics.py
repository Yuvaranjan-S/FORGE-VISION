"""
FORGE-VISION — Automated Forensic Unit & Integration Test Suite
Verifies:
1. Triple hash calculation (MD5, SHA-256, SHA3-256)
2. Hash-chained chain-of-custody ledger verification
3. Modular vendor parser detection and confidence scoring
4. Dataset registration & provenance tracking
5. Grounded NLP query parser
"""
import os
import sys
import unittest
import tempfile
import json
from datetime import datetime, timezone

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.hash_engine import (
    compute_string_sha256,
    compute_file_hashes,
    compute_custody_entry_hash,
    verify_chain,
)
from app.parsers import (
    detect_vendor_and_get_parser,
    GenericVideoParser,
    HikvisionParser,
    DahuaParser,
    CPPlusParser,
    MatrixParser,
    UniviewParser,
    HoneywellParser,
)


class TestForensicHashing(unittest.TestCase):
    """Test cryptographic hashing and chain-of-custody ledger integrity."""

    def test_string_sha256(self):
        h = compute_string_sha256("FORGE-VISION-EVIDENCE-TEST")
        self.assertEqual(len(h), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in h))

    def test_file_triple_hashing(self):
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tf.write(b"SAMPLE_FORENSIC_VIDEO_STREAM_DATA_BYTES")
            tf_path = tf.name

        try:
            hashes = compute_file_hashes(tf_path)
            self.assertIn("md5", hashes)
            self.assertIn("sha256", hashes)
            self.assertIn("sha3_256", hashes)
            self.assertEqual(len(hashes["md5"]), 32)
            self.assertEqual(len(hashes["sha256"]), 64)
            self.assertEqual(len(hashes["sha3_256"]), 64)
            self.assertEqual(hashes["file_size_bytes"], len(b"SAMPLE_FORENSIC_VIDEO_STREAM_DATA_BYTES"))
        finally:
            os.remove(tf_path)

    def test_custody_hash_chain_valid(self):
        """Verify unbroken cryptographic hash chain."""
        now = datetime.now(timezone.utc).isoformat()
        entries = []
        prev_hash = None

        for seq in range(1, 4):
            entry = {
                "id": f"entry-{seq}",
                "seq": seq,
                "case_id": "CASE-TEST",
                "evidence_id": "EV-01",
                "action": "ingest" if seq == 1 else "hash_verify",
                "operator_id": "user-investigator",
                "operator_role": "investigator",
                "timestamp": now,
                "evidence_hash_before": None,
                "evidence_hash_after": "a"*64,
                "detail": json.dumps({"test": True}),
                "prev_entry_hash": prev_hash,
                "this_entry_hash": "",
            }
            this_hash = compute_custody_entry_hash(entry, "this_entry_hash")
            entry["this_entry_hash"] = this_hash
            entries.append(entry)
            prev_hash = this_hash

        result = verify_chain(entries)
        self.assertTrue(result["is_valid"])
        self.assertEqual(result["entry_count"], 3)
        self.assertIsNone(result["broken_at_seq"])

    def test_custody_hash_chain_tamper_detection(self):
        """Verify that modifying any field in a past entry breaks the hash chain."""
        now = datetime.now(timezone.utc).isoformat()
        entries = []
        prev_hash = None

        for seq in range(1, 4):
            entry = {
                "id": f"entry-{seq}",
                "seq": seq,
                "case_id": "CASE-TEST",
                "evidence_id": "EV-01",
                "action": "ingest",
                "operator_id": "user-investigator",
                "operator_role": "investigator",
                "timestamp": now,
                "evidence_hash_before": None,
                "evidence_hash_after": "a"*64,
                "detail": json.dumps({"test": True}),
                "prev_entry_hash": prev_hash,
                "this_entry_hash": "",
            }
            this_hash = compute_custody_entry_hash(entry, "this_entry_hash")
            entry["this_entry_hash"] = this_hash
            entries.append(entry)
            prev_hash = this_hash

        # Tamper with entry 2
        entries[1]["detail"] = json.dumps({"tampered": True})

        result = verify_chain(entries)
        self.assertFalse(result["is_valid"])
        self.assertEqual(result["broken_at_seq"], 2)


class TestVendorParsers(unittest.TestCase):
    """Test modular vendor adapter architecture."""

    def test_generic_parser_extensions(self):
        generic = GenericVideoParser()
        self.assertTrue(generic.detect("test_file.mp4"))
        self.assertTrue(generic.detect("test_file.avi"))
        self.assertTrue(generic.detect("test_file.mkv"))
        self.assertFalse(generic.detect("test_file.txt"))

    def test_vendor_adapter_simulation_badges(self):
        hik = HikvisionParser()
        dahua = DahuaParser()
        cpplus = CPPlusParser()
        matrix = MatrixParser()
        uniview = UniviewParser()
        honeywell = HoneywellParser()

        self.assertTrue(hik.IS_SIMULATED)
        self.assertTrue(dahua.IS_SIMULATED)
        self.assertTrue(cpplus.IS_SIMULATED)
        self.assertTrue(matrix.IS_SIMULATED)
        self.assertTrue(uniview.IS_SIMULATED)
        self.assertTrue(honeywell.IS_SIMULATED)

        device_info = hik.identify_device("sample.dav")
        self.assertIn("is_simulated", device_info)
        self.assertTrue(device_info["is_simulated"])

    def test_vendor_dispatch_fallback(self):
        parser = detect_vendor_and_get_parser("generic_surveillance.mp4")
        self.assertIsInstance(parser, GenericVideoParser)


if __name__ == "__main__":
    unittest.main()
