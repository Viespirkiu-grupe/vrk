"""The web portraits (issue #187) and the `ph` flag that gates them (#185).

`scripts/build_web_portraits.py` turns the 5.2 GB portrait archive into one
192x256 WebP per person. Pinned here on synthetic images, built with Pillow
so every container the corpus holds can be made on a clone: which candidacy
a person's portrait comes from, that a file which does not decode falls back
to an older one, that the output carries no metadata however much the
source did, that a re-run with nothing changed writes nothing, and that
`ph: 1` follows the file and nothing else.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tarfile
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from PIL import Image, ImageCms

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


portraits = _load("build_web_portraits")


def image_bytes(fmt: str, size=(300, 450), colour=(200, 40, 40), **save) -> bytes:
    out = io.BytesIO()
    mode = "RGBA" if fmt == "PNG" and save.pop("alpha", False) else "RGB"
    Image.new(mode, size, colour + ((128,) if mode == "RGBA" else ())).save(out, fmt, **save)
    return out.getvalue()


def exif_with_gps() -> bytes:
    exif = Image.Exif()
    exif[0x010F] = "Camera maker"  # Make
    exif[0x0131] = "Editor 1.0"  # Software
    exif.get_ifd(0x8825)[0x0002] = (54.0, 26.0, 59.4)  # GPSLatitude
    return exif.tobytes()


def jpeg_with_everything() -> bytes:
    """A JPEG carrying EXIF with a GPS position, an ICC profile and an XMP packet."""
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    return image_bytes(
        "JPEG",
        exif=exif_with_gps(),
        icc_profile=icc,
        xmp=b'<x:xmpmeta xmlns:x="adobe:ns:meta/">GPS here</x:xmpmeta>',
    )


def person(pid: str, *candidacies: tuple[str, str]) -> dict:
    """A people.json entry: candidacies oldest first, as the index writes them."""
    return {"pid": pid, "n": pid, "e": [{"id": eid, "c": cid} for eid, cid in candidacies]}


class Corpus:
    """A temporary repo root with `data/<election>/photos/` and `portraits/`."""

    def __init__(self, test: unittest.TestCase) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="vrk-portraits-test-"))
        test.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.data = self.root / "data"
        self.out = self.root / "portraits"
        self.data.mkdir()

    def photo(self, election: str, candidate: str, raw: bytes, ext: str = "jpg") -> Path:
        path = self.data / election / "photos" / f"{candidate}.{ext}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return path

    def build(self, people: list[dict]) -> dict:
        return portraits.build(people, self.data, self.out, jobs=1, log=lambda *_: None)

    def manifest(self) -> dict:
        return json.loads((self.out / portraits.MANIFEST_NAME).read_text(encoding="utf-8"))


class SelectionTests(unittest.TestCase):
    def test_the_newest_candidacy_with_a_file_wins(self):
        corpus = Corpus(self)
        corpus.photo("2016-seimo", "ona-1", image_bytes("JPEG", colour=(0, 0, 255)))
        newest = corpus.photo("2020-seimo", "ona-2", image_bytes("JPEG", colour=(255, 0, 0)))
        # The 2024 candidacy has no portrait file; 2020 is the newest that does.
        people = [person("pona", ("2016-seimo", "ona-1"), ("2020-seimo", "ona-2"), ("2024-seimo", "ona-3"))]
        self.assertEqual(
            portraits.candidate_sources(people[0], portraits.photo_files(corpus.data))[0], newest
        )
        counts = corpus.build(people)
        self.assertEqual(counts["portraits"], 1)
        self.assertEqual(corpus.manifest()["portraits"]["pona"]["src"], "data/2020-seimo/photos/ona-2.jpg")
        with Image.open(corpus.out / "pona.webp") as image:
            red, _, blue = image.convert("RGB").getpixel((96, 128))
        self.assertGreater(red, 200)
        self.assertLess(blue, 50)

    def test_an_undecodable_newest_file_falls_back_to_the_older_one(self):
        # What VRK published once: a Word document saved as a portrait.
        corpus = Corpus(self)
        corpus.photo("2016-seimo", "ona-1", image_bytes("JPEG"))
        corpus.photo("2020-seimo", "ona-2", b"PK\x03\x04 a docx, not a photo", ext="zip")
        counts = corpus.build([person("pona", ("2016-seimo", "ona-1"), ("2020-seimo", "ona-2"))])
        self.assertEqual((counts["portraits"], counts["fallbacks"], counts["failed"]), (1, 1, 1))
        manifest = corpus.manifest()
        self.assertEqual(manifest["portraits"]["pona"]["src"], "data/2016-seimo/photos/ona-1.jpg")
        self.assertIn("data/2020-seimo/photos/ona-2.zip", manifest["failed"])
        self.assertNotIn(" at 0x", manifest["failed"]["data/2020-seimo/photos/ona-2.zip"]["error"])

    def test_nobody_without_a_file_gets_a_portrait(self):
        corpus = Corpus(self)
        corpus.photo("2016-seimo", "ona-1", b"not an image")
        counts = corpus.build([person("pona", ("2016-seimo", "ona-1")), person("pjonas", ("2016-seimo", "jonas-1"))])
        self.assertEqual((counts["with_source"], counts["portraits"]), (1, 0))
        self.assertEqual(list(corpus.out.glob("*.webp")), [])

    def test_decoded_by_content_not_by_extension(self):
        # The 2012 tree served BMP, TIFF and PNG as image/jpeg under .jpg (#118).
        corpus = Corpus(self)
        people = []
        for i, fmt in enumerate(("PNG", "BMP", "TIFF", "GIF")):
            corpus.photo("2012-seimo", f"c{i}", image_bytes(fmt), ext="jpg")
            people.append(person(f"p{i}", ("2012-seimo", f"c{i}")))
        counts = corpus.build(people)
        self.assertEqual((counts["portraits"], counts["failed"]), (4, 0))


class ShapeTests(unittest.TestCase):
    def test_a_tall_source_is_cropped_from_the_top(self):
        self.assertEqual(portraits.crop_box(300, 600), (0, 0, 300, 400))

    def test_a_wide_source_is_cropped_across_the_middle(self):
        self.assertEqual(portraits.crop_box(800, 400), (250, 0, 550, 400))

    def test_an_exact_three_by_four_is_left_whole(self):
        self.assertEqual(portraits.crop_box(192, 256), (0, 0, 192, 256))

    def test_the_top_of_the_frame_is_what_survives(self):
        # Red top third, blue below: a top-anchored crop of a 1:2 frame keeps
        # the red head and loses the bottom.
        image = Image.new("RGB", (300, 600), (0, 0, 255))
        image.paste((255, 0, 0), (0, 0, 300, 200))
        out = io.BytesIO()
        image.save(out, "PNG")
        with Image.open(io.BytesIO(portraits.render(out.getvalue()))) as web:
            self.assertEqual(web.size, (portraits.WIDTH, portraits.HEIGHT))
            top = web.convert("RGB").getpixel((96, 10))
        self.assertGreater(top[0], 200)

    def test_transparency_is_flattened_onto_white(self):
        raw = image_bytes("PNG", colour=(0, 0, 0), alpha=True)
        with Image.open(io.BytesIO(portraits.render(raw))) as web:
            self.assertEqual(web.mode, "RGB")
            value = web.getpixel((96, 128))
        # Half-transparent black over white is mid grey, not black.
        self.assertTrue(all(100 < channel < 160 for channel in value), value)


class MetadataTests(unittest.TestCase):
    def test_the_source_really_carries_metadata(self):
        with Image.open(io.BytesIO(jpeg_with_everything())) as source:
            self.assertIn("exif", source.info)
            self.assertIn("icc_profile", source.info)
            self.assertIn("xmp", source.info)

    def test_nothing_but_the_bitstream_survives(self):
        web = portraits.render(jpeg_with_everything())
        self.assertEqual(portraits.webp_chunk_types(web), ["VP8 "])
        for marker in (b"EXIF", b"ICCP", b"XMP ", b"Camera maker", b"GPS here"):
            self.assertNotIn(marker, web)
        with Image.open(io.BytesIO(web)) as image:
            self.assertEqual(image.format, "WEBP")
            self.assertNotIn("exif", image.info)
            self.assertNotIn("icc_profile", image.info)

    def test_the_chunk_reader_refuses_what_is_not_webp(self):
        with self.assertRaises(ValueError):
            portraits.webp_chunk_types(image_bytes("PNG"))


class IncrementalTests(unittest.TestCase):
    def setUp(self):
        self.corpus = Corpus(self)
        self.corpus.photo("2016-seimo", "ona-1", image_bytes("JPEG", colour=(10, 120, 10)))
        self.corpus.photo("2020-seimo", "jonas-2", image_bytes("PNG", colour=(10, 10, 120)), ext="png")
        self.people = [person("pona", ("2016-seimo", "ona-1")), person("pjonas", ("2020-seimo", "jonas-2"))]
        self.first = self.corpus.build(self.people)

    def snapshot(self) -> dict[str, tuple[int, bytes]]:
        return {p.name: (p.stat().st_mtime_ns, p.read_bytes()) for p in sorted(self.corpus.out.iterdir())}

    def test_a_rerun_with_nothing_changed_writes_nothing(self):
        before = self.snapshot()
        again = self.corpus.build(self.people)
        self.assertEqual((again["unchanged"], again["rendered"], again["written"]), (2, 0, 0))
        self.assertFalse(again["manifest_written"])
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(again["version"], self.first["version"])

    def test_a_lost_manifest_rebuilds_identical_bytes(self):
        before = {k: v for k, v in self.snapshot().items() if k.endswith(".webp")}
        (self.corpus.out / portraits.MANIFEST_NAME).unlink()
        again = self.corpus.build(self.people)
        self.assertEqual((again["rendered"], again["written"]), (2, 0))
        self.assertEqual({k: v for k, v in self.snapshot().items() if k.endswith(".webp")}, before)

    def test_a_changed_source_is_rerendered_and_moves_the_version(self):
        self.corpus.photo("2016-seimo", "ona-1", image_bytes("JPEG", colour=(250, 250, 10)))
        again = self.corpus.build(self.people)
        self.assertEqual((again["unchanged"], again["rendered"], again["written"]), (1, 1, 1))
        self.assertNotEqual(again["version"], self.first["version"])

    def test_a_touched_but_identical_source_is_not_rerendered(self):
        source = self.corpus.data / "2016-seimo" / "photos" / "ona-1.jpg"
        os.utime(source, ns=(source.stat().st_atime_ns, source.stat().st_mtime_ns + 10**9))
        again = self.corpus.build(self.people)
        self.assertEqual((again["unchanged"], again["rendered"]), (2, 0))

    def test_a_new_newer_candidacy_takes_over(self):
        self.corpus.photo("2024-seimo", "ona-3", image_bytes("JPEG", colour=(0, 0, 0)))
        self.people[0]["e"].append({"id": "2024-seimo", "c": "ona-3"})
        again = self.corpus.build(self.people)
        self.assertEqual(again["rendered"], 1)
        self.assertEqual(self.corpus.manifest()["portraits"]["pona"]["src"], "data/2024-seimo/photos/ona-3.jpg")

    def test_a_person_who_is_gone_loses_the_file(self):
        again = self.corpus.build(self.people[:1])
        self.assertEqual(again["removed"], 1)
        self.assertFalse((self.corpus.out / "pjonas.webp").exists())

    def test_a_quality_change_rebuilds_everything(self):
        again = portraits.build(self.people, self.corpus.data, self.corpus.out, jobs=1, quality=40, log=lambda *_: None)
        self.assertEqual(again["rendered"], 2)
        self.assertEqual(self.corpus.manifest()["settings"]["quality"], 40)


class PortraitFlagTests(unittest.TestCase):
    """`ph: 1` exactly where `portraits/<pid>.webp` exists (#185 step 2)."""

    def index(self) -> dict:
        return {"people": [{"pid": "pona", "e": []}, {"pid": "pjonas", "e": [], "ph": 1}, {"pid": "pruta", "e": []}]}

    def test_the_flag_follows_the_file(self):
        corpus = Corpus(self)
        corpus.photo("2016-seimo", "ona-1", image_bytes("JPEG"))
        corpus.build([person("pona", ("2016-seimo", "ona-1"))])
        index = self.index()
        self.assertTrue(portraits.apply_portrait_flags(index, corpus.out))
        flags = {p["pid"]: p.get("ph") for p in index["people"]}
        # pjonas carried a stale flag and has no file: it is removed.
        self.assertEqual(flags, {"pona": 1, "pjonas": None, "pruta": None})
        self.assertEqual(index["portraits"], {"v": corpus.manifest()["version"], "n": 1})
        self.assertFalse(portraits.apply_portrait_flags(index, corpus.out))

    def test_no_portraits_directory_means_no_flags(self):
        index = self.index()
        index["portraits"] = {"v": "old", "n": 1}
        portraits.apply_portrait_flags(index, Path(tempfile.gettempdir()) / "vrk-no-such-portraits")
        self.assertFalse(any("ph" in p for p in index["people"]))
        self.assertNotIn("portraits", index)

    def test_the_main_run_restamps_the_index(self):
        corpus = Corpus(self)
        corpus.photo("2016-seimo", "ona-1", image_bytes("JPEG"))
        index_path = corpus.root / "people.json"
        index_path.write_text(json.dumps(self.index()), encoding="utf-8")
        args = ["--index", str(index_path), "--data-root", str(corpus.data), "--out", str(corpus.out), "--jobs", "1"]
        people = self.index()["people"]
        people[0]["e"] = [{"id": "2016-seimo", "c": "ona-1"}]
        index_path.write_text(json.dumps({"people": people}), encoding="utf-8")
        with unittest.mock.patch("builtins.print"):
            self.assertEqual(portraits.main(args), 0)
        written = json.loads(index_path.read_text(encoding="utf-8"))
        self.assertEqual([p["pid"] for p in written["people"] if p.get("ph") == 1], ["pona"])
        self.assertEqual(written["portraits"]["n"], 1)

    def test_the_person_index_applies_the_same_flag(self):
        # build_person_index.main stamps the flag with this very function,
        # so the two scripts cannot disagree about who has a portrait.
        source = (REPO_ROOT / "scripts" / "build_person_index.py").read_text(encoding="utf-8")
        self.assertIn("from build_web_portraits import PORTRAITS_DIR, apply_portrait_flags", source)
        self.assertIn("apply_portrait_flags(index, PORTRAITS_DIR)", source)


class DistributionTarTests(unittest.TestCase):
    """`vrk-web-portraits.tar`: what production deploys (issue #187)."""

    def setUp(self):
        self.dist_mod = _load("build_distribution")
        self.corpus = Corpus(self)
        self.corpus.photo("2016-seimo", "ona-1", image_bytes("JPEG"))
        self.corpus.photo("2016-seimo", "jonas-1", image_bytes("PNG"), ext="png")
        self.corpus.build([person("pona", ("2016-seimo", "ona-1")), person("pjonas", ("2016-seimo", "jonas-1"))])

    def test_the_tar_holds_the_portraits_and_nothing_else(self):
        target = self.corpus.root / "web.tar"
        counts = self.dist_mod.write_web_portraits_tar(self.corpus.out, target)
        manifest = self.corpus.manifest()
        self.assertEqual(counts["count"], 2)
        self.assertEqual(counts["bytes"], manifest["bytes"])
        self.assertEqual(counts["version"], manifest["version"])
        with tarfile.open(target) as tar:
            members = tar.getmembers()
            self.assertEqual(
                [m.name for m in members],
                ["portraits/pjonas.webp", "portraits/pona.webp"],
            )
            self.assertTrue(all(m.uid == 0 and m.mode == 0o644 and m.isfile() for m in members))
            self.assertEqual(
                tar.extractfile("portraits/pona.webp").read(), (self.corpus.out / "pona.webp").read_bytes()
            )

    def test_a_portrait_that_does_not_match_its_manifest_is_refused(self):
        (self.corpus.out / "pona.webp").write_bytes(b"RIFF\x00\x00\x00\x00WEBP")
        with self.assertRaises(SystemExit) as raised:
            self.dist_mod.check_web_portraits(self.corpus.out)
        self.assertIn("pona.webp: does not hash", str(raised.exception))

    def test_a_stray_or_missing_portrait_is_refused(self):
        (self.corpus.out / "pjonas.webp").unlink()
        shutil.copy(self.corpus.out / "pona.webp", self.corpus.out / "pstray.webp")
        with self.assertRaises(SystemExit) as raised:
            self.dist_mod.check_web_portraits(self.corpus.out)
        self.assertIn("pjonas.webp: listed, not on disk", str(raised.exception))
        self.assertIn("pstray.webp: on disk, not listed", str(raised.exception))

    def test_no_portraits_is_refused_with_the_command(self):
        with self.assertRaises(SystemExit) as raised:
            self.dist_mod.check_web_portraits(self.corpus.root / "nowhere")
        self.assertIn("scripts/build_web_portraits.py", str(raised.exception))

    def test_the_manifest_lists_the_asset_with_its_counts(self):
        dist = self.corpus.root / "dist"
        dist.mkdir()
        for name in self.dist_mod.RELEASE_ARTIFACTS:
            (dist / name).write_bytes(name.encode())
        tar = dist / self.dist_mod.WEB_PORTRAITS_ASSET
        web = self.dist_mod.write_web_portraits_tar(self.corpus.out, tar)
        corpus_counts = {
            "photo_parts": [], "web_portraits": web, "parser_commits": {}, "redacted_values": 0,
            "records": 0, "photos": 0, "photo_records": 0, "photo_bytes": 0, "photos_stripped": 0,
            "photos_untouched": 0, "photos_malformed": 0, "anomalies": 0, "per_election": {},
        }
        manifest = self.dist_mod.write_manifest(
            dist, {"elections": 0, "persons": 2, "campaigns": 0}, corpus_counts, None
        )
        self.assertEqual(
            manifest["artifacts"][self.dist_mod.WEB_PORTRAITS_ASSET],
            {"bytes": tar.stat().st_size, "sha256": hashlib.sha256(tar.read_bytes()).hexdigest()},
        )
        self.assertEqual(
            (manifest["counts"]["webPortraits"], manifest["counts"]["webPortraitBytes"]),
            (2, self.corpus.manifest()["bytes"]),
        )
        self.assertEqual(manifest["webPortraits"]["version"], self.corpus.manifest()["version"])
        self.assertEqual(manifest["webPortraits"]["settings"]["width"], 192)
        # A subset build ships no tar, and the manifest names none.
        self.assertNotIn(
            self.dist_mod.WEB_PORTRAITS_ASSET,
            self.dist_mod.release_assets({"photo_parts": [], "web_portraits": None}),
        )

if __name__ == "__main__":
    unittest.main()
