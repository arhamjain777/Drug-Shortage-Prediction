import json, unittest
from ingestion.normalise import normalise_record, plan_upsert, parse_date
from ingestion.fetch_sources import OpenFDAClient, SourceUnavailable

REC = {"generic_name": " Amoxicillin  ", "company_name": "ACME", "status": "Current",
       "initial_posting_date": "03/15/2024", "update_date": "04/01/2024",
       "presentation": "tablet 500 mg", "openfda": {"brand_name": ["X"], "dosage_form": ["TABLET"]}}


class NormaliseTests(unittest.TestCase):
    def test_dates(self):
        self.assertEqual(parse_date("03/15/2024"), "2024-03-15")
        self.assertIsNone(parse_date("garbage"))
        self.assertIsNone(parse_date(None))

    def test_normalise(self):
        n = normalise_record(REC)
        self.assertEqual(n["generic_name"], "Amoxicillin")
        self.assertEqual(n["dosage_form"], "TABLET")
        self.assertEqual(n["initial_posting_date"], "2024-03-15")
        self.assertEqual(n["raw"], REC)

    def test_reject_missing_name(self):
        self.assertIn("rejected", normalise_record({"status": "Current"}))

    def test_idempotent_upsert(self):
        p1 = plan_upsert({}, [REC, REC])
        self.assertEqual((len(p1.inserts), p1.duplicates), (1, 1))
        existing = {n["source_key"]: n["content_hash"] for n in p1.inserts}
        p2 = plan_upsert(existing, [REC])
        self.assertEqual((len(p2.inserts), len(p2.updates), p2.unchanged), (0, 0, 1))

    def test_update_detected_when_status_changes(self):
        p1 = plan_upsert({}, [REC])
        existing = {n["source_key"]: n["content_hash"] for n in p1.inserts}
        changed = dict(REC, status="Resolved")
        p2 = plan_upsert(existing, [changed])
        self.assertEqual((len(p2.inserts), len(p2.updates)), (0, 1))

    def test_rejected_counted(self):
        self.assertEqual(plan_upsert({}, [{"x": 1}, REC]).rejected, ["missing generic_name"])


def page(n, total):
    return 200, json.dumps({"meta": {"results": {"total": total}}, "results": [dict(REC, presentation=str(i)) for i in range(n)]})


class ClientTests(unittest.TestCase):
    def test_pagination(self):
        calls = []
        def tr(url, timeout):
            calls.append(url)
            return page(2, 3) if "skip=0" in url else page(1, 3)
        c = OpenFDAClient(transport=tr)
        self.assertEqual(len(c.fetch_all(page_size=2)), 3)
        self.assertEqual(len(calls), 2)

    def test_retry_then_success(self):
        seq = iter([(503, ""), (429, ""), page(1, 1)])
        sleeps = []
        c = OpenFDAClient(transport=lambda u, t: next(seq), sleep=sleeps.append)
        self.assertEqual(len(c.fetch_all()), 1)
        self.assertEqual(sleeps, [1.0, 2.0])

    def test_404_is_empty_not_error(self):
        c = OpenFDAClient(transport=lambda u, t: (404, "{}"))
        self.assertEqual(c.fetch_all(), [])

    def test_persistent_failure_raises_without_leaking_key(self):
        c = OpenFDAClient(api_key="SECRET123", transport=lambda u, t: (503, ""), sleep=lambda s: None, max_retries=2)
        with self.assertRaises(SourceUnavailable) as cm:
            c.fetch_all()
        self.assertNotIn("SECRET123", str(cm.exception))

    def test_network_error_handled(self):
        def tr(u, t): raise ConnectionError("down")
        c = OpenFDAClient(transport=tr, sleep=lambda s: None, max_retries=1)
        with self.assertRaises(SourceUnavailable):
            c.fetch_all()

    def test_non_retryable_stops_immediately(self):
        n = []
        def tr(u, t): n.append(1); return 400, "bad"
        with self.assertRaises(SourceUnavailable):
            OpenFDAClient(transport=tr, sleep=lambda s: None).fetch_all()
        self.assertEqual(len(n), 1)

if __name__ == "__main__":
    unittest.main()
