"""Validate result records; this tool does not inspect images or measure accuracy."""

import argparse
import hashlib
import json
from pathlib import Path
import sys


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
OBJECT_FIELDS = {"object_id", "views_received", "views_inspected", "status", "defects", "review_reason"}
DEFECT_FIELDS = {"defect_id", "type", "confidence", "evidence_view", "bbox_1000", "relative_location", "visual_evidence", "other_views", "uncertainty"}


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def parse_json(text):
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key: " + key)
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError("Non-finite JSON number: " + value)

    return json.loads(text, object_pairs_hook=unique_keys, parse_constant=reject_constant)


def load_json(path):
    return parse_json(Path(path).read_text(encoding="utf-8-sig"))


def validate(data, images=None, jsonl=None, inspection_log=None, strict_evidence=False, object_scope=None):
    errors = []
    warnings = []
    if object_scope is not None and (images is None or not object_scope or any(not nonempty(x) for x in object_scope) or len(object_scope) != len(set(object_scope))):
        errors.append("Explicit object scope requires --images and unique, nonempty object IDs")

    def check(condition, message):
        if not condition:
            errors.append(message)

    def view_list(value, where):
        if not isinstance(value, list) or any(not nonempty(v) for v in value):
            errors.append(where + ": expected a list of nonempty filenames")
            return []
        check(len(value) == len(set(value)), where + ": duplicate filenames")
        check(all("/" not in v and "\\" not in v and v not in {".", ".."} for v in value), where + ": use filenames, not paths")
        return value

    check(isinstance(data, dict), "root: expected an object")
    if not isinstance(data, dict):
        return {"valid": False, "errors": errors}
    check(data.get("schema_version") == "1.0", "schema_version: expected 1.0")
    objects = data.get("objects")
    check(isinstance(objects, list), "objects: expected an array")
    if not isinstance(objects, list):
        return {"valid": False, "errors": errors}

    ids = []
    received_total = inspected_total = candidates_total = confirmed_total = 0
    counts = {"objects_total": len(objects), "objects_with_defects": 0, "objects_for_review": 0, "linear_mark_count": 0, "material_loss_count": 0}
    input_groups = None
    if images is not None:
        root = Path(images)
        if not root.is_dir():
            errors.append("images: input directory does not exist")
        else:
            input_groups = {
                folder.name: {p.name for p in folder.iterdir() if p.is_file() and not p.name.startswith((".", "._")) and p.suffix.lower() in IMAGE_SUFFIXES}
                for folder in root.iterdir() if folder.is_dir() and not folder.name.startswith(".")
            }
            check(bool(input_groups), "images: no object directories found")
            if object_scope is not None:
                check(set(object_scope) <= set(input_groups), "objects scope contains unknown input directories")
                input_groups = {k: v for k, v in input_groups.items() if k in object_scope}

    for index, obj in enumerate(objects):
        where = "objects[{}]".format(index)
        check(isinstance(obj, dict), where + ": expected an object")
        if not isinstance(obj, dict):
            continue
        check(OBJECT_FIELDS <= obj.keys(), where + ": missing required object fields")
        oid = obj.get("object_id")
        check(nonempty(oid), where + ".object_id: expected a nonempty string")
        if nonempty(oid):
            check("/" not in oid and "\\" not in oid and oid not in {".", ".."}, where + ".object_id: expected a directory name, not a path")
        if nonempty(oid):
            ids.append(oid)
        received = view_list(obj.get("views_received"), where + ".views_received")
        inspected = view_list(obj.get("views_inspected"), where + ".views_inspected")
        received_total += len(received)
        inspected_total += len(inspected)
        check(set(inspected) <= set(received), where + ": inspected views must be received")
        if input_groups is not None and nonempty(oid):
            check(oid in input_groups, where + ": object_id not found in input")
            if oid in input_groups:
                check(set(received) == input_groups[oid], where + ": received views differ from input files")
        status = obj.get("status")
        check(status in ("defects_found", "no_visible_defect", "review"), where + ": invalid status")
        if status == "review":
            counts["objects_for_review"] += 1
            check(nonempty(obj.get("review_reason")), where + ": review requires review_reason")
        else:
            check(obj.get("review_reason") is None, where + ": non-review status requires null review_reason")
        if not received or set(inspected) != set(received):
            check(status == "review", where + ": empty or incomplete inspection requires review")
        defects = obj.get("defects")
        check(isinstance(defects, list), where + ".defects: expected an array")
        if not isinstance(defects, list):
            continue
        counts["objects_with_defects"] += int(bool(defects))
        check(status != "defects_found" or bool(defects), where + ": defects_found requires candidates")
        check(status != "no_visible_defect" or not defects, where + ": no_visible_defect cannot have candidates")
        defect_ids = []
        for number, defect in enumerate(defects):
            loc = where + ".defects[{}]".format(number)
            check(isinstance(defect, dict), loc + ": expected an object")
            if not isinstance(defect, dict):
                continue
            candidates_total += 1
            check(DEFECT_FIELDS <= defect.keys(), loc + ": missing required defect fields")
            for key in ("defect_id", "relative_location", "visual_evidence"):
                check(nonempty(defect.get(key)), loc + "." + key + ": expected nonempty text")
            if nonempty(defect.get("defect_id")):
                defect_ids.append(defect["defect_id"])
            kind = defect.get("type")
            check(kind in ("linear_mark", "material_loss"), loc + ": invalid defect type")
            if kind in ("linear_mark", "material_loss"):
                counts[kind + "_count"] += 1
            confidence = defect.get("confidence")
            check(confidence in ("high", "medium", "low"), loc + ": invalid confidence")
            uncertainty = defect.get("uncertainty")
            check(uncertainty is None or nonempty(uncertainty), loc + ": uncertainty must be null or nonempty text")
            if confidence == "low":
                check(status == "review" and nonempty(uncertainty), loc + ": low confidence requires review and uncertainty")
            evidence = defect.get("evidence_view")
            check(isinstance(evidence, str) and evidence in inspected, loc + ": evidence_view must have been inspected")
            box = defect.get("bbox_1000")
            valid_box = isinstance(box, list) and len(box) == 4 and all(type(v) in (int, float) and 0 <= v <= 1000 for v in box)
            check(valid_box and box[0] < box[2] and box[1] < box[3], loc + ": invalid bbox_1000")
            others = defect.get("other_views")
            check(isinstance(others, list), loc + ".other_views: expected an array")
            if not isinstance(others, list):
                continue
            other_ids = []
            confirmed = False
            for relation in others:
                check(isinstance(relation, dict), loc + ": invalid other_views entry")
                if not isinstance(relation, dict):
                    continue
                view = relation.get("view")
                check(isinstance(view, str) and view in inspected and view != evidence, loc + ": invalid corroborating view")
                if isinstance(view, str):
                    other_ids.append(view)
                check(relation.get("relation") in ("confirms", "contradicts", "not_visible"), loc + ": invalid view relation")
                check(nonempty(relation.get("note")), loc + ": view relation requires note")
                confirmed = confirmed or relation.get("relation") == "confirms"
                if relation.get("relation") == "contradicts":
                    check(status == "review", loc + ": contradictory evidence requires review")
            check(len(other_ids) == len(set(other_ids)), loc + ": duplicate corroborating views")
            confirming_notes = [v.get("note") for v in others if isinstance(v, dict) and v.get("relation") == "confirms" and isinstance(v.get("note"), str)]
            if len(confirming_notes) > len(set(confirming_notes)):
                warnings.append(loc + ": repeated confirmation notes; verify each view against a concrete landmark")
            if valid_box and (box[2] - box[0]) * (box[3] - box[1]) > 200000:
                warnings.append(loc + ": bbox covers over 20% of source frame; verify region-cluster granularity")
            confirmed_total += int(confirmed)
        check(len(defect_ids) == len(set(defect_ids)), where + ": duplicate defect_id")

    check(len(ids) == len(set(ids)), "objects: duplicate object_id")
    if input_groups is not None:
        check(set(ids) == set(input_groups), "objects: object set differs from input directories")
    summary = data.get("summary")
    check(isinstance(summary, dict), "summary: expected an object")
    if isinstance(summary, dict):
        for key, expected in counts.items():
            check(type(summary.get(key)) is int and summary[key] == expected, "summary." + key + ": expected " + str(expected))
    if jsonl is not None:
        lines = Path(jsonl).read_text(encoding="utf-8-sig").splitlines()
        check(all(line.strip() for line in lines), "jsonl: blank lines are not allowed")
        records = [parse_json(line) for line in lines if line.strip()]
        check(records == objects, "jsonl: records or order differ from JSON objects")
    evidence_metrics = check_evidence_log(data, inspection_log, images, strict_evidence, errors, warnings)
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "computed_summary": counts,
        "declared_views_received": received_total,
        "declared_views_inspected": inspected_total,
        "declared_view_inspection_coverage": inspected_total / received_total if received_total else None,
        "candidates_with_other_view_confirmation": confirmed_total,
        "candidate_other_view_confirmation_ratio": confirmed_total / candidates_total if candidates_total else None,
        "evidence_metrics": evidence_metrics,
        "limitations": "Record validation only; coverage is self-reported. This does not prove image inspection or recognition accuracy."
    }


def check_evidence_log(data, log_file, images, strict, errors, warnings):
    if log_file is None:
        message = "No inspection log: actual detail coverage and per-class checks cannot be established"
        (errors if strict else warnings).append(message)
        return None
    if strict and images is None:
        errors.append("Strict evidence validation requires --images to verify source hashes")
    log_path = Path(log_file).resolve()
    log = load_json(log_path)
    if not isinstance(log, dict) or log.get("log_version") != "1.0" or not isinstance(log.get("views"), list):
        errors.append("inspection_log: invalid header or views")
        return None
    objects = [o for o in data["objects"] if isinstance(o, dict)]
    expected = {(o.get("object_id"), view) for o in objects if isinstance(o.get("object_id"), str) and isinstance(o.get("views_received"), list) for view in o["views_received"] if isinstance(view, str)}
    scope = log.get("scope")
    if not isinstance(scope, list) or any(not isinstance(x, str) for x in scope) or len(scope) != len(set(scope)) or set(scope) != {o.get("object_id") for o in objects if isinstance(o.get("object_id"), str)}:
        errors.append("inspection_log: scope must exactly match result object IDs")
    indexed = {}
    detail_count = dual_count = 0
    for record in log["views"]:
        if not isinstance(record, dict) or not isinstance(record.get("object_id"), str) or not isinstance(record.get("view"), str):
            errors.append("inspection_log: each view needs string object_id and view")
            continue
        key = (record["object_id"], record["view"])
        if key in indexed:
            errors.append("inspection_log: duplicate view " + str(key))
        indexed[key] = record
        if key not in expected:
            errors.append("inspection_log: view not present in result scope " + str(key))
            continue
        if any("/" in part or "\\" in part or part in {".", ".."} for part in key):
            errors.append("inspection_log: object/view names must not contain paths")
            continue
        where = "inspection_log " + "/".join(key)
        stage = record.get("stage")
        if stage not in ("navigation", "detail", "unreadable"):
            errors.append(where + ": invalid stage")
        checks = record.get("checks")
        if not isinstance(checks, dict) or any(checks.get(c) not in ("complete", "limited", "not_checked") for c in ("linear_mark", "material_loss")):
            errors.append(where + ": invalid category checks")
            checks = {}
        if stage != "detail" and "complete" in checks.values():
            errors.append(where + ": only detail inspection can claim complete category checks")
        if not nonempty(record.get("note")):
            errors.append(where + ": missing inspection note")
        artifacts = record.get("artifacts_seen")
        if not isinstance(artifacts, list) or any(not nonempty(x) for x in artifacts) or (stage != "unreadable" and not artifacts):
            errors.append(where + ": missing or invalid artifacts_seen")
        else:
            for artifact in artifacts:
                path = Path(artifact)
                if not path.is_absolute():
                    path = log_path.parent / path
                if not path.is_file():
                    errors.append(where + ": artifact does not exist: " + artifact)
        digest = record.get("source_sha256")
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            errors.append(where + ": invalid source_sha256")
        elif images is not None:
            source = Path(images) / key[0] / key[1]
            if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != digest:
                errors.append(where + ": source hash mismatch")
        detail_count += int(stage == "detail")
        dual_count += int(stage == "detail" and all(checks.get(c) == "complete" for c in ("linear_mark", "material_loss")))
    if set(indexed) != expected:
        errors.append("inspection_log: view set differs from result views_received")
    for obj in objects:
        oid = obj.get("object_id")
        received = obj.get("views_received")
        if not isinstance(oid, str) or not isinstance(received, list):
            continue
        records = [indexed.get((oid, v), {}) for v in received if isinstance(v, str)]
        complete = bool(records) and all(r.get("stage") == "detail" and isinstance(r.get("checks"), dict) and all(r["checks"].get(c) == "complete" for c in ("linear_mark", "material_loss")) for r in records)
        if obj.get("status") == "no_visible_defect" and not complete:
            (errors if strict else warnings).append(oid + ": negative conclusion lacks complete two-class detail checks; use review")
        for defect in obj.get("defects", []) if isinstance(obj.get("defects"), list) else []:
            if isinstance(defect, dict) and isinstance(defect.get("evidence_view"), str) and indexed.get((oid, defect["evidence_view"]), {}).get("stage") != "detail":
                (errors if strict else warnings).append(oid + ": candidate evidence needs detail inspection")
            if isinstance(defect, dict) and isinstance(defect.get("other_views"), list):
                for relation in defect["other_views"]:
                    if isinstance(relation, dict) and isinstance(relation.get("view"), str) and relation.get("relation") == "confirms" and indexed.get((oid, relation["view"]), {}).get("stage") != "detail":
                        (errors if strict else warnings).append(oid + ": confirmation requires detail inspection of the supporting view")
    return {"views_logged": len(indexed), "detail_views": detail_count, "two_class_complete_views": dual_count, "declared_detail_coverage": detail_count / len(expected) if expected else None, "self_reported_not_independent_truth": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True, help="inspection_results.json")
    parser.add_argument("--images", help="Optional input directory with one child folder per object")
    parser.add_argument("--jsonl", help="Optional JSONL counterpart to compare")
    parser.add_argument("--inspection-log", help="Optional source-linked visual inspection log")
    parser.add_argument("--strict-evidence", action="store_true", help="Require evidence log and detail-backed negative conclusions")
    parser.add_argument("--objects", nargs="+", help="Explicit object scope for a partial regression, checked against --images")
    args = parser.parse_args()
    try:
        report = validate(load_json(args.results), args.images, args.jsonl, args.inspection_log, args.strict_evidence, args.objects)
    except (OSError, ValueError) as exc:
        report = {"valid": False, "errors": [str(exc)]}
    print(json.dumps(report, ensure_ascii=True, indent=2, allow_nan=False))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
