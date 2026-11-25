"""端到端编校规则测试，使用标准库 unittest。"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from exhibition.facts import trial_independence
from exhibition.geometry import cell_width
from exhibition.metrics import rate_change
from exhibition.service import EditorialService
from pack_check import DEFAULT_DATA


class GeometryTest(unittest.TestCase):
    def test_ascii_han_and_fullwidth_punctuation(self):
        self.assertEqual(cell_width("abc123"), 6)
        self.assertEqual(cell_width("汉字"), 4)
        self.assertEqual(cell_width("，"), 2)
        self.assertEqual(cell_width("良率:10%"), 4 + 1 + 3)
        self.assertEqual(cell_width("a\nb"), 2)


class ExtractionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service = EditorialService(DEFAULT_DATA)

    def test_v1_line_baseline_and_comparator(self):
        claim = next(c for c in self.service.ledger.source_claims["V1"] if c.claim_type == "measurement")
        self.assertEqual((claim.baseline, claim.current), (70.0, 80.0))
        self.assertEqual(claim.delta, 10.0)
        self.assertEqual(claim.delta_unit, "percentage_point")
        self.assertEqual(claim.scope["line"], "L1")
        self.assertIn("prior_month_same_line", claim.comparator)

    def test_v2_night_subgroup_has_pp_and_relative_values(self):
        claim = next(c for c in self.service.ledger.source_claims["V2"] if c.claim_type == "measurement")
        self.assertEqual((claim.baseline, claim.current), (60.0, 66.0))
        self.assertEqual(claim.delta, 6.0)
        self.assertEqual(claim.scope["shift"], "night")
        self.assertAlmostEqual(claim.relative_pct, 10.0)

    def test_v3_is_forecast_not_observed(self):
        claim = next(c for c in self.service.ledger.source_claims["V3"] if c.claim_type == "measurement")
        self.assertEqual(claim.modality, "expected")
        self.assertFalse(claim.measured)
        self.assertEqual(claim.direction, "down")

    def test_exhibit_scope_and_unit_claims(self):
        e2 = self.service.ledger.exhibit_claims["E2"]
        measurement = next(c for c in e2 if c.claim_type == "measurement")
        self.assertEqual(measurement.scope["scale"], "plant")
        self.assertEqual(measurement.delta_unit, "percent")

        e5 = self.service.ledger.exhibit_claims["E5"]
        measurement = next(c for c in e5 if c.claim_type == "measurement")
        self.assertEqual(measurement.scope.get("aggregation"), "day_night_total")
        self.assertEqual(measurement.scope.get("phase"), "after_changeover")

    def test_chinese_phrase_baifenzhi_shi_is_relative_percent(self):
        from exhibition.extract import extract_record

        row = {"id": "X1", "lang": "zh", "draft": "设备良率提升百分之十。", "refs": ""}
        claim = extract_record(row, "exhibit")[0]
        self.assertEqual(claim.delta, 10.0)
        self.assertEqual(claim.delta_unit, "percent")
        self.assertNotEqual(claim.delta_unit, "percentage_point")

    def test_ten_percentage_points_is_not_ten_relative_percent(self):
        change = rate_change(70, 80)
        self.assertEqual(change["percentage_points"], 10)
        self.assertAlmostEqual(change["relative_percent"], 14.2857142857)
        night = rate_change(60, 66)
        self.assertEqual(night["percentage_points"], 6)
        self.assertAlmostEqual(night["relative_percent"], 10.0)

    def test_anaphoric_comparators_are_extracted(self):
        from exhibition.extract import extract_record

        row = {"id": "X2", "trial": "T1", "plan": "观察", "text": "该线良率为95%，较上期提升2个百分点。同期对照稳定。"}
        claim = next(c for c in extract_record(row, "source") if c.claim_type == "measurement")
        self.assertIn("prior_period", claim.comparator)
        self.assertTrue(any("该线" in item["phrase"] for item in claim.anaphora))
        self.assertTrue(any("同期" in item["phrase"] for item in claim.anaphora))


class PolicyAndReplacementTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service = EditorialService(DEFAULT_DATA)

    def test_channel_entitlements(self):
        ledger = self.service.ledger
        self.assertFalse(ledger.usable("V1", "现场中文")[0])
        self.assertTrue(ledger.usable("V4", "现场中文")[0])
        self.assertTrue(ledger.usable("V4", "现场英文")[0])
        self.assertTrue(ledger.usable("V4", "扫码内页")[0])
        self.assertFalse(ledger.usable("V2", "现场英文")[0])
        self.assertTrue(ledger.usable("V3", "扫码内页")[0])
        self.assertFalse(ledger.usable("V3", "现场中文")[0])

    def test_v4_is_same_boundary_replacement_for_v1(self):
        equivalents = [x for x in self.service.replacements["V1"] if x["equivalent"]]
        self.assertEqual([x["candidate_source_id"] for x in equivalents], ["V4"])

    def test_v5_cannot_replace_night_subgroup(self):
        v5 = next(x for x in self.service.replacements["V2"] if x["candidate_source_id"] == "V5")
        self.assertFalse(v5["equivalent"])
        self.assertFalse(v5["exact_boundary"])
        self.assertTrue(any("班次" in issue or "线别" in issue for issue in v5["match"]["scope_issues"]))

    def test_v1_v4_count_one_independent_trial(self):
        result = trial_independence(self.service.facts, ["V1", "V4"])
        self.assertEqual(result["independent_trial_count"], 1)
        self.assertFalse(result["is_independent_validation"])


class PublicationPlanTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service = EditorialService(DEFAULT_DATA)
        cls.report = cls.service.build_report()
        cls.boards = {board["surface_id"]: board for board in cls.report["plan"]["boards"]}

    def test_every_registered_board_fits(self):
        for board in self.report["plan"]["boards"]:
            self.assertLessEqual(board["used_cells"], board["limit"], board)

    def test_chinese_board_is_standalone_accurate_short_write(self):
        p1 = self.boards["P1"]
        entry = p1["entries"][0]
        self.assertEqual(entry["theme_ids"], ["T1"])
        self.assertLessEqual(entry["width"], 55)
        for fragment in ["一号线", "70%", "80%", "十个百分点", "比上月同线", "V4"]:
            self.assertIn(fragment, entry["text"])
        self.assertNotIn("全车间", entry["text"])
        self.assertNotIn("夜班", entry["text"])
        self.assertEqual(entry["source_ids"], ["V4"])

    def test_english_board_corrects_scope_unit_and_independence(self):
        p2 = self.boards["P2"]
        entry = p2["entries"][0]
        self.assertLessEqual(entry["width"], 105)
        for fragment in ["Line1", "70-80%", "+10 percentage points", "prior-month same line", "1 trial", "V1 withdrawn"]:
            self.assertIn(fragment, entry["text"])
        self.assertNotIn("plant-wide", entry["text"].lower())
        self.assertNotIn("Two independent", entry["text"])

    def test_rework_is_forecast_and_scan_only(self):
        p3 = self.boards["P3"]
        inner = p3["entries"][0]
        self.assertLessEqual(inner["width"], 260)
        self.assertIn("预计总体-10%", inner["text"])
        self.assertIn("forecast overall -10%", inner["text"])
        self.assertIn("未测", inner["text"])
        self.assertTrue(
            all(
                "T2" not in entry["theme_ids"]
                for board in self.report["plan"]["boards"]
                if board["surface_id"] in {"P1", "P2"}
                for entry in board["entries"]
            )
        )

    def test_night_theme_is_uncovered_and_requests_specific_material(self):
        for surface_id in ("P1", "P2"):
            board = self.boards[surface_id]
            self.assertTrue(any(item["theme_id"] == "T3" for item in board["omitted_themes"]))
            self.assertFalse(any("T3" in entry["theme_ids"] for entry in board["entries"]))
        trace = next(t for t in self.report["editor_audit"]["theme_to_surface_facts"] if t["theme_id"] == "T3")
        self.assertFalse(trace["covered"])
        self.assertIn("MR-E4-NIGHT-AUTH", trace["material_request_ids"])
        request = next(r for r in self.report["material_requests"] if r["request_id"] == "MR-E4-NIGHT-AUTH")
        self.assertIn("60%", request["needed_scope"])
        self.assertTrue(any(c["source_id"] == "V5" for c in request["rejected_candidates"]))

    def test_shared_two_theme_sentence_requires_both_languages(self):
        check = self.report["plan"]["shared_sentence_check"]
        self.assertTrue(check["evaluated"])
        self.assertFalse(check["one_sentence_may_cover_two_themes"])
        self.assertEqual(check["language_support"], {"zh": False, "en": False})
        self.assertFalse(check["duplicate_typesetting_counts_as_coverage"])

    def test_report_is_json_serializable(self):
        json.dumps(self.report, ensure_ascii=False)

    def test_unsupported_workshop_validation_is_pending_not_fact(self):
        pending = self.report["zones"]["pending_zone"]
        self.assertTrue(any(item["exhibit_id"] == "E1" and "范围" in item["message"] for item in pending))
        fact_text = json.dumps(self.report["plan"], ensure_ascii=False)
        self.assertNotIn("全车间验证成功", fact_text)

    def test_editor_cannot_override_missing_authorization(self):
        with self.assertRaises(PermissionError):
            self.service.decide_merge("MRG-T8-LINE-NIGHT", "publish_separate", editor="test-editor")


class QrAndPhysicalEditionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service = EditorialService(DEFAULT_DATA)
        cls.zh = cls.service.scan_response("N17-zh-r1")
        cls.en = cls.service.scan_response("N17-en-r1")
        cls.web = cls.service.scan_response("N17-web-r1")

    def test_qr_shows_issue_time_and_bound_edition(self):
        self.assertEqual(self.zh["issued_at"], "2026-10-21T09:00")
        self.assertEqual(self.en["issued_at"], "2026-10-21T10:00")
        self.assertIn("N17-zh-r1", self.zh["applicability_notice"])
        self.assertIn("N17-en-r1", self.en["applicability_notice"])

    def test_synchronized_correction_but_different_physical_actions(self):
        self.assertEqual(self.zh["current_correction_id"], self.en["current_correction_id"])
        self.assertEqual(self.zh["correction_issued_at"], self.en["correction_issued_at"])
        self.assertEqual(self.zh["correction_issued_at"], "2026-10-21T11:35")
        self.assertIn("闭馆", self.zh["physical_replacement_action"])
        self.assertIn("不得上墙", self.en["physical_replacement_action"])
        self.assertNotEqual(self.zh["physical_replacement_action"], self.en["physical_replacement_action"])

    def test_old_wall_edition_has_explicit_correction(self):
        self.assertEqual(self.zh["revision_status"], "wall_edition_r1_visible_pending_closure_replacement")
        for fragment in ["V1", "全车间", "夜班", "一号线"]:
            self.assertIn(fragment, self.zh["old_board_correction_notice"])
        self.assertEqual(self.zh["still_credentialed_content"], self.service.plan()["boards"][0]["entries"][0]["text"])

    def test_printed_not_posted_edition_is_withheld(self):
        self.assertEqual(self.en["revision_status"], "printed_r1_withheld_replace_before_install")
        self.assertIn("Two independent", self.en["old_board_correction_notice"])

    def test_web_edition_has_bilingual_current_content(self):
        self.assertEqual(self.web["revision_status"], "scan_edition_revised_with_history")
        self.assertIn("中：", self.web["still_credentialed_content"])
        self.assertIn("EN:", self.web["still_credentialed_content"])

    def test_public_qr_payload_does_not_leak_internal_numbers_or_raw_findings(self):
        payload = json.dumps(self.zh, ensure_ascii=False)
        self.assertNotIn("V2", payload)
        self.assertNotIn("60%", payload)
        self.assertNotIn("66%", payload)
        self.assertNotIn("findings_for_visible_items", self.zh)
        self.assertTrue(self.zh["public_corrections"])
        self.assertTrue(all("quote" not in item for item in self.zh["public_findings"]))


class DeadlineAndTempPackTest(unittest.TestCase):
    def test_tiny_board_drops_required_theme_instead_of_unsafe_truncation(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "materials"
            shutil.copytree(DEFAULT_DATA, target)
            releases = target / "releases.tsv"
            text = releases.read_text(encoding="utf-8")
            lines = text.splitlines()
            lines[1] = "\t".join(["P1", "现场中文", "10", "上墙", ""])
            releases.write_text("\n".join(lines) + "\n", encoding="utf-8")
            service = EditorialService(target)
            plan = service.plan(["T1"])
            p1 = next(b for b in plan["boards"] if b["surface_id"] == "P1")
            self.assertEqual(p1["entries"], [])
            self.assertTrue(any(o["theme_id"] == "T1" for o in p1["omitted_themes"]))
            self.assertFalse(p1["feasible"])


if __name__ == "__main__":
    unittest.main()
