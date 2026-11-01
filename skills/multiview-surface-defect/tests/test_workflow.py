"""Behavioral regression tests; synthetic fixtures are not recognition benchmarks."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


validator = module("validate_results")
preparer = module("prepare_views")


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.images = self.root / "images"
        folder = self.images / "part-a"
        folder.mkdir(parents=True)
        for view in ("front.png", "oblique.png"):
            image = Image.new("RGB", (120, 80), "white")
            image.putpixel((30, 20), (12, 34, 56))
            image.save(folder / view)
        self.data = validator.load_json(ROOT / "templates" / "inspection-results.json")
        self.data["objects"][0]["object_id"] = "part-a"
        self.log = {
            "log_version": "1.0", "scope": ["part-a"],
            "views": [
                {"object_id": "part-a", "view": p.name,
                 "source_sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                 "stage": "detail", "artifacts_seen": [str(p)],
                 "checks": {"linear_mark": "complete", "material_loss": "complete"},
                 "note": "Synthetic fixture viewed for validator testing only."}
                for p in sorted(folder.glob("*.png"))
            ],
        }
        self.log_file = self.root / "inspection_log.json"
        self.write_log()

    def tearDown(self):
        self.temp.cleanup()

    def write_log(self):
        self.log_file.write_text(json.dumps(self.log), encoding="utf-8")

    def report(self, strict=True):
        return validator.validate(self.data, str(self.images), inspection_log=str(self.log_file),
                                  strict_evidence=strict, object_scope=["part-a"])

    def assert_rejected(self, fragment):
        report = self.report()
        self.assertFalse(report["valid"], report)
        self.assertTrue(any(fragment in item for item in report["errors"]), report)

    def test_valid_single_object_run_with_source_hashes(self):
        self.assertTrue(self.report()["valid"])

    def test_missing_log_rejected_only_in_strict_mode(self):
        self.assertTrue(validator.validate(self.data)["valid"])
        self.assertFalse(validator.validate(self.data, strict_evidence=True)["valid"])

    def test_source_changed_after_inspection(self):
        (self.images / "part-a" / "front.png").write_bytes(b"changed source")
        self.assert_rejected("source hash mismatch")

    def test_confirmation_from_navigation_only_is_not_evidence(self):
        row = next(r for r in self.log["views"] if r["view"] == "oblique.png")
        row["stage"] = "navigation"
        row["checks"] = {"linear_mark": "limited", "material_loss": "limited"}
        self.write_log()
        self.assert_rejected("confirmation requires detail inspection")

    def test_claim_of_negative_after_limited_category_check(self):
        self.data["objects"][0]["defects"] = []
        self.data["objects"][0]["status"] = "no_visible_defect"
        self.data["summary"]["objects_with_defects"] = 0
        self.data["summary"]["linear_mark_count"] = 0
        self.log["views"][0]["checks"]["material_loss"] = "limited"
        self.write_log()
        self.assert_rejected("negative conclusion lacks complete two-class")

    def test_review_allowed_after_limited_category_check(self):
        self.data["objects"][0]["status"] = "review"
        self.data["objects"][0]["review_reason"] = "Incomplete surface check"
        self.data["summary"]["objects_for_review"] = 1
        self.log["views"][0]["checks"]["material_loss"] = "limited"
        self.write_log()
        self.assertTrue(self.report()["valid"])

    def test_single_view_candidate_does_not_require_confirmation(self):
        self.data["objects"][0]["defects"][0]["other_views"] = []
        self.assertTrue(self.report()["valid"])

    def test_duplicate_source_view_and_missing_artifact(self):
        self.log["views"].append(copy.deepcopy(self.log["views"][0]))
        self.log["views"][0]["artifacts_seen"] = ["does-not-exist.png"]
        self.write_log()
        report = self.report()
        self.assertFalse(report["valid"])
        self.assertTrue(any("duplicate view" in x for x in report["errors"]))
        self.assertTrue(any("artifact does not exist" in x for x in report["errors"]))

    def test_bbox_degenerate_nonfinite_bool_and_extreme_number(self):
        for box in ([10, 20, 10, 40], [True, 20, 40, 60], [0, float("nan"), 40, 60],
                    [0, 0, 40, float("inf")], [0, 0, 40, 10 ** 1000]):
            with self.subTest(box=repr(box)[:60]):
                self.data["objects"][0]["defects"][0]["bbox_1000"] = box
                self.assert_rejected("invalid bbox")

    def test_parser_rejects_ambiguous_or_nonstandard_json(self):
        for text in ('{"status":"review","status":"no_visible_defect"}',
                     '{"value":NaN}', '{"value":Infinity}'):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    validator.parse_json(text)

    def test_partial_scope_must_be_explicit_and_cover_exact_objects(self):
        (self.images / "part-b").mkdir()
        self.assertFalse(validator.validate(self.data, str(self.images))["valid"])
        self.assertTrue(self.report()["valid"])
        self.assertFalse(validator.validate(self.data, str(self.images), object_scope=["absent"])["valid"])

    def test_jsonl_record_mismatch_is_detected(self):
        jsonl = self.root / "results.jsonl"
        jsonl.write_text('{"object_id":"another-part"}\n', encoding="utf-8")
        report = validator.validate(self.data, str(self.images), jsonl=str(jsonl), object_scope=["part-a"])
        self.assertFalse(report["valid"])

    def test_crop_preserves_pixels_coordinates_and_source_hash(self):
        region_file = self.root / "regions.json"
        region_file.write_text(json.dumps({"regions": [
            {"object_id": "part-a", "view": "front.png", "box_pixel": [20, 10, 60, 50]}
        ]}), encoding="utf-8")
        out = self.root / "prepared"
        manifest = preparer.prepare(self.images, out, region_file)
        record = next(r for r in manifest["views"] if r["view"] == "front.png")
        with Image.open(out / record["regions"][0]["path"]) as crop:
            self.assertEqual(crop.size, (40, 40))
            self.assertEqual(crop.getpixel((10, 10)), (12, 34, 56))
        self.assertEqual(record["source_sha256"], hashlib.sha256((self.images / "part-a" / "front.png").read_bytes()).hexdigest())
        self.assertFalse(manifest["generation_is_inspection"])
        self.assertEqual(preparer.map_crop_box([0, 0, 1000, 1000], [20, 10, 60, 50], [120, 80]),
                         [166.6667, 125.0, 500.0, 625.0])

    def test_bad_region_is_rejected_and_unreadable_image_reported(self):
        region_file = self.root / "regions.json"
        region_file.write_text(json.dumps({"regions": [
            {"object_id": "part-a", "view": "front.png", "box_pixel": [0, 0, 999, 999]}
        ]}), encoding="utf-8")
        with self.assertRaises(ValueError):
            preparer.prepare(self.images, self.root / "bad-region", region_file)
        (self.images / "part-a" / "broken.png").write_bytes(b"not an image")
        manifest = preparer.prepare(self.images, self.root / "has-error")
        broken = next(r for r in manifest["views"] if r["view"] == "broken.png")
        self.assertTrue(broken["decode_error"])

    def test_cli_invalid_input_exits_one_without_traceback(self):
        bad = self.root / "bad.json"
        bad.write_text('{"summary": NaN}', encoding="utf-8")
        proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "validate_results.py"), "--results", str(bad)],
                              text=True, capture_output=True)
        self.assertEqual(proc.returncode, 1)
        self.assertFalse(json.loads(proc.stdout)["valid"])
        self.assertNotIn("Traceback", proc.stderr)


if __name__ == "__main__":
    unittest.main()
