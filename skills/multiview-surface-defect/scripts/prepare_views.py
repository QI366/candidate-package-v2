"""Create source-linked previews/crops. Generation does not imply inspection."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

from PIL import Image

SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


def map_crop_box(box, crop, size):
    """Map a normalized crop-relative box back to source-image coordinates."""
    if not isinstance(box, (list, tuple)) or len(box) != 4 or not all(type(v) in (int, float) and 0 <= v <= 1000 for v in box) or not (box[0] < box[2] and box[1] < box[3]):
        raise ValueError("Invalid crop-relative bbox")
    if not isinstance(size, (list, tuple)) or len(size) != 2 or any(type(v) is not int or v <= 0 for v in size):
        raise ValueError("Source size must contain positive integer width and height")
    if not isinstance(crop, (list, tuple)) or len(crop) != 4 or any(type(v) is not int for v in crop):
        raise ValueError("Crop must contain four integer source pixel coordinates")
    width, height = size
    x0, y0, x1, y1 = crop
    if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
        raise ValueError("Crop lies outside source image")
    return [round((x0 + box[0] / 1000 * (x1 - x0)) / width * 1000, 4),
            round((y0 + box[1] / 1000 * (y1 - y0)) / height * 1000, 4),
            round((x0 + box[2] / 1000 * (x1 - x0)) / width * 1000, 4),
            round((y0 + box[3] / 1000 * (y1 - y0)) / height * 1000, 4)]


def prepare(images, output, region_file=None, preview_max=1024, objects=None):
    images, output = Path(images).resolve(), Path(output).resolve()
    if not images.is_dir():
        raise ValueError("Input image directory does not exist")
    if preview_max < 64:
        raise ValueError("preview-max must be at least 64")
    if output == images or images in output.parents:
        raise ValueError("Output must be outside the input image directory")
    output.mkdir(parents=True, exist_ok=True)
    regions = [] if region_file is None else json.loads(Path(region_file).read_text(encoding="utf-8-sig"))["regions"]
    if not isinstance(regions, list):
        raise ValueError("regions must be an array")
    requested = {}
    for region in regions:
        if not isinstance(region, dict) or not isinstance(region.get("object_id"), str) or not isinstance(region.get("view"), str):
            raise ValueError("Each region requires object_id, view, and box_pixel")
        box = region.get("box_pixel")
        if not isinstance(box, list) or len(box) != 4 or any(type(v) is not int for v in box):
            raise ValueError("box_pixel must contain four integers")
        requested.setdefault((region["object_id"], region["view"]), []).append(box)
    folders = [p for p in sorted(images.iterdir()) if p.is_dir() and not p.name.startswith(".")]
    if objects:
        unknown = set(objects) - {p.name for p in folders}
        if unknown:
            raise ValueError("Unknown object IDs: " + ", ".join(sorted(unknown)))
        folders = [p for p in folders if p.name in objects]
    if not folders:
        raise ValueError("No object folders found")
    manifest = {"manifest_version": "1.0", "input_root": str(images), "coordinate_frame": "source_file_pixels_without_exif_rotation", "generation_is_inspection": False, "objects": [p.name for p in folders], "views": []}
    remaining = set(requested)
    for folder in folders:
        target = output / folder.name
        target.mkdir(exist_ok=True)
        for source in sorted(folder.iterdir()):
            if not source.is_file() or source.name.startswith(".") or source.suffix.lower() not in SUFFIXES:
                continue
            entry = {"object_id": folder.name, "view": source.name, "source_sha256": None, "size": None, "overview": None, "regions": [], "decode_error": None}
            try:
                entry["source_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
                with Image.open(source) as opened:
                    image = opened.convert("RGB")
                entry["size"] = list(image.size)
                preview = image.copy()
                preview.thumbnail((preview_max, preview_max), Image.Resampling.LANCZOS)
                destination = target / (source.name + ".overview.png")
                preview.save(destination)
                entry["overview"] = {"path": destination.relative_to(output).as_posix(), "size": list(preview.size), "role": "navigation"}
                for index, box in enumerate(requested.get((folder.name, source.name), [])):
                    if not (0 <= box[0] < box[2] <= image.width and 0 <= box[1] < box[3] <= image.height):
                        raise ValueError("Invalid region for " + folder.name + "/" + source.name)
                    destination = target / (source.name + ".region-{:02d}.png".format(index + 1))
                    image.crop(box).save(destination)
                    entry["regions"].append({"path": destination.relative_to(output).as_posix(), "box_pixel": box, "size": [box[2] - box[0], box[3] - box[1]], "scale": 1, "role": "detail"})
                remaining.discard((folder.name, source.name))
            except (OSError, Image.DecompressionBombError) as exc:
                entry["decode_error"] = str(exc)
            manifest["views"].append(entry)
    if remaining:
        raise ValueError("Regions reference views outside selected input: " + str(sorted(remaining)))
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--regions", help="JSON with regions: object_id, view, box_pixel")
    parser.add_argument("--objects", nargs="+", help="Optional explicit object scope")
    parser.add_argument("--preview-max", type=int, default=1024)
    args = parser.parse_args()
    try:
        manifest = prepare(args.images, args.out, args.regions, args.preview_max, args.objects)
        failed = sum(v["decode_error"] is not None for v in manifest["views"])
        print(json.dumps({"objects": len(manifest["objects"]), "views": len(manifest["views"]), "decode_errors": failed, "manifest": str(Path(args.out).resolve() / "manifest.json"), "generation_is_inspection": False}, indent=2))
        return int(bool(failed))
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
