"""
FORGE-VISION — Automated Test Suite for Kaggle CCTV Ingestion & Multi-Vendor Provenance
"""
import os
import sys
import asyncio
import aiosqlite
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
from app.database import init_db
from app.routers.auth import create_access_token


async def _run_all_tests():
    print("--- 1. Initializing DB ---")
    await init_db()

    token = create_access_token({"sub": "user-investigator-01", "role": "investigator"})
    sup_token = create_access_token({"sub": "user-supervisor-01", "role": "supervisor"})
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Sources Catalog
        print("--- 2. Testing Kaggle Sources Catalog ---")
        res = await client.get("/api/kaggle/sources", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200, f"Failed sources: {res.text}"
        sources = res.json()
        assert len(sources) >= 5
        keys = [s["id"] for s in sources]
        assert "virat-cctv" in keys
        assert "ucf-crime" in keys
        assert "racd-cctv" in keys
        assert "cctv-action" in keys
        assert "traffic-intersection" in keys
        print(f"[OK] Kaggle sources verified: {len(sources)} public research benchmarks loaded.")

        # 2. Auth status
        print("--- 3. Testing Kaggle Auth Status ---")
        res_auth = await client.get("/api/kaggle/auth-status", headers={"Authorization": f"Bearer {token}"})
        assert res_auth.status_code == 200
        auth_data = res_auth.json()
        assert "authenticated" in auth_data
        assert "key" not in auth_data
        print(f"[OK] Auth check safe: authenticated={auth_data['authenticated']}, source={auth_data['auth_source']}")

        # 3. Evidence Explorer Filters
        print("--- 4. Testing Evidence Explorer Filters ---")
        res_pub = await client.get("/api/evidence/?source_type=PUBLIC_RESEARCH_DATASET", headers={"Authorization": f"Bearer {token}"})
        assert res_pub.status_code == 200
        pub_list = res_pub.json()
        assert len(pub_list) > 0, "Expected seeded public research evidence"
        for ev in pub_list:
            assert ev["source_type"] == "PUBLIC_RESEARCH_DATASET"
            assert ev["source_vendor"] == "Unknown"
            assert ev["vendor_classification_status"] == "UNKNOWN"
        print(f"[OK] Public research provenance verified: {len(pub_list)} records with vendor=Unknown.")

        # 4. Multi-Vendor Demo Case
        print("--- 5. Testing Multi-Vendor Demo Case ---")
        res_mv = await client.get("/api/evidence/case/CASE-DEMO-MULTIVENDOR", headers={"Authorization": f"Bearer {token}"})
        assert res_mv.status_code == 200
        mv_list = res_mv.json()
        vendors = {ev["source_vendor"] for ev in mv_list}
        assert "Hikvision" in vendors
        assert "Dahua" in vendors
        assert "CP Plus" in vendors
        assert "Generic" in vendors
        for ev in mv_list:
            assert ev["vendor_classification_status"] == "SIMULATED_DEMO"
            assert "SIMULATED VENDOR" in ev["notes"]
        print(f"[OK] Multi-vendor collections verified across {len(vendors)} OEM vendors.")

        # 5. NLP Query
        print("--- 6. Testing NLP Query Engine ---")
        res_nlp = await client.post(
            "/api/nlp/case/CASE-DEMO001/query",
            json={"query": "Show all imported evidence from the UCF Crime dataset"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res_nlp.status_code == 200
        nlp_data = res_nlp.json()
        assert len(nlp_data["citations"]) > 0
        print(f"[OK] NLP query verified: intent={nlp_data['intent']}, citations={len(nlp_data['citations'])}")

        # 6. Report generation
        print("--- 7. Testing Forensic PDF Reporting ---")
        res_rep = await client.post("/api/reporting/case/CASE-DEMO001/generate", headers={"Authorization": f"Bearer {sup_token}"})
        assert res_rep.status_code == 200
        assert res_rep.headers["content-type"] == "application/pdf"
        assert len(res_rep.content) > 500
        print(f"[OK] PDF report generated successfully: {len(res_rep.content)} bytes.")

    print("\n============================================================")
    print("  ALL 6/6 PIPELINE INTEGRATION TESTS PASSED CLEANLY!")
    print("============================================================")


def test_suite():
    asyncio.run(_run_all_tests())


if __name__ == "__main__":
    test_suite()
