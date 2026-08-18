import os
import tempfile
import unittest
from pathlib import Path

from scraper.elections.seimo_2016.anketa_parser import (
    _parse_nested_campaign_samples,
    _resolve_sample_path,
)


TAB_HTML = """<html><body>
<div class="sectionDescription">Kampanijos duomenys</div>
<div>turinys</div>
</body></html>
"""

CANDIDATE_ID = "jonas-jonaitis"
CAMPAIGN_KEY = "savarankiskas-pkdid-1"
TAB_SLUGS = ["izdininkas", "auditorius"]


def _build_candidate_tree(
    root: Path,
    recorded_prefix: str | None = None,
) -> tuple[Path, dict]:
    """Create a candidate fixture tree whose index.json records fetch-time
    paths, which only resolve from the fetch-time CWD (the repo root)."""
    campaign_dir = root / CANDIDATE_ID / "campaigns" / CAMPAIGN_KEY
    campaign_dir.mkdir(parents=True)
    if recorded_prefix is None:
        recorded_prefix = f"samples/html/2016-seimo/{CANDIDATE_ID}/campaigns/{CAMPAIGN_KEY}"

    tab_samples = []
    for slug in TAB_SLUGS:
        (campaign_dir / f"{slug}.html").write_text(TAB_HTML, encoding="utf-8")
        tab_samples.append(
            {
                "label": slug.capitalize(),
                "slug": slug,
                "url": f"https://example.test/{slug}.html",
                "path": f"{recorded_prefix}/{slug}.html",
                "fetched": True,
            }
        )

    meta = {
        "candidate": {"candidateId": CANDIDATE_ID, "url": "https://example.test/anketa.html"},
        "campaignSamples": [
            {
                "campaignKey": CAMPAIGN_KEY,
                "campaignLabel": "Savarankiškas",
                "campaignUrl": "https://example.test/kampanija.html",
                "tabCount": len(tab_samples),
                "tabSamples": tab_samples,
            }
        ],
    }
    return root / CANDIDATE_ID, meta


class CampaignSamplePathResolutionTests(unittest.TestCase):
    def _parse(self, candidate_dir: Path, meta: dict) -> tuple[list, list]:
        anomalies: list = []
        campaigns = _parse_nested_campaign_samples(
            meta,
            None,
            candidate_dir=candidate_dir,
            election_id="2016-seimo",
            candidate_id=CANDIDATE_ID,
            source_url="https://example.test/anketa.html",
            anomalies=anomalies,
        )
        return campaigns, anomalies

    def test_tabs_resolve_against_samples_root_from_any_cwd(self) -> None:
        # The recorded paths do not exist relative to the test CWD, so this
        # passes only when they are re-anchored onto the candidate directory.
        with tempfile.TemporaryDirectory() as tmp:
            candidate_dir, meta = _build_candidate_tree(Path(tmp))
            campaigns, anomalies = self._parse(candidate_dir, meta)

        self.assertEqual(anomalies, [])
        self.assertEqual(len(campaigns), 1)
        self.assertEqual([tab["slug"] for tab in campaigns[0]["tabs"]], TAB_SLUGS)
        self.assertEqual(campaigns[0]["sectionDescription"], "Kampanijos duomenys")

    def test_absolute_recorded_paths_from_moved_tree_resolve(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            candidate_dir, meta = _build_candidate_tree(
                Path(tmp),
                recorded_prefix=(
                    "/nonexistent-old-drive/samples/html/2016-seimo/"
                    f"{CANDIDATE_ID}/campaigns/{CAMPAIGN_KEY}"
                ),
            )
            campaigns, anomalies = self._parse(candidate_dir, meta)

        self.assertEqual(anomalies, [])
        self.assertEqual([tab["slug"] for tab in campaigns[0]["tabs"]], TAB_SLUGS)

    def test_missing_tab_file_emits_anomaly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            candidate_dir, meta = _build_candidate_tree(Path(tmp))
            missing = candidate_dir / "campaigns" / CAMPAIGN_KEY / "auditorius.html"
            missing.unlink()
            campaigns, anomalies = self._parse(candidate_dir, meta)

            self.assertEqual([tab["slug"] for tab in campaigns[0]["tabs"]], ["izdininkas"])
            self.assertEqual(len(anomalies), 1)
            event = anomalies[0]
            self.assertEqual(event["eventType"], "CampaignTabSampleMissing")
            self.assertEqual(event["severity"], "error")
            self.assertEqual(event["stage"], "parse")
            self.assertEqual(event["electionId"], "2016-seimo")
            self.assertEqual(event["candidateId"], CANDIDATE_ID)
            self.assertEqual(event["detail"]["campaignKey"], CAMPAIGN_KEY)
            self.assertEqual(event["detail"]["tabSlug"], "auditorius")
            self.assertTrue(event["detail"]["fetched"])
            self.assertEqual(event["detail"]["reason"], "missing")
            self.assertEqual(
                event["detail"]["recordedPath"],
                f"samples/html/2016-seimo/{CANDIDATE_ID}/campaigns/{CAMPAIGN_KEY}/auditorius.html",
            )
            self.assertEqual(event["detail"]["resolvedPath"], str(missing))

    def test_unreadable_tab_file_emits_anomaly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            candidate_dir, meta = _build_candidate_tree(Path(tmp))
            tab_path = candidate_dir / "campaigns" / CAMPAIGN_KEY / "izdininkas.html"
            tab_path.unlink()
            tab_path.mkdir()
            campaigns, anomalies = self._parse(candidate_dir, meta)

        self.assertEqual([tab["slug"] for tab in campaigns[0]["tabs"]], ["auditorius"])
        self.assertEqual(len(anomalies), 1)
        event = anomalies[0]
        self.assertEqual(event["eventType"], "CampaignTabSampleMissing")
        self.assertEqual(event["detail"]["tabSlug"], "izdininkas")
        self.assertEqual(event["detail"]["reason"], "unreadable")
        self.assertTrue(event["detail"]["error"])

    def test_missing_root_campaign_page_emits_anomaly(self) -> None:
        # Campaigns without tab links record a single campaignRootPath instead
        # of tabSamples; its file must be covered by the same guarantees.
        meta = {
            "campaignSamples": [
                {
                    "campaignKey": CAMPAIGN_KEY,
                    "campaignUrl": "https://example.test/kampanija.html",
                    "tabSamples": [],
                    "campaignRootPath": (
                        f"samples/html/2016-seimo/{CANDIDATE_ID}/campaigns/{CAMPAIGN_KEY}/root.html"
                    ),
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            candidate_dir = Path(tmp) / CANDIDATE_ID
            candidate_dir.mkdir()
            campaigns, anomalies = self._parse(candidate_dir, meta)

        self.assertEqual(campaigns[0]["tabs"], [])
        self.assertEqual(len(anomalies), 1)
        self.assertEqual(anomalies[0]["eventType"], "CampaignTabSampleMissing")
        self.assertEqual(anomalies[0]["detail"]["tabSlug"], "root")


class ResolveSamplePathTests(unittest.TestCase):
    def test_samples_root_in_use_wins_over_cwd(self) -> None:
        # When the CWD holds a stale copy at the recorded path (the repo tree)
        # and --samples-root points elsewhere, the samples root must win.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recorded = Path("samples") / CANDIDATE_ID / "file.html"
            cwd_copy = root / recorded
            cwd_copy.parent.mkdir(parents=True)
            cwd_copy.write_text("cwd copy", encoding="utf-8")

            candidate_dir = root / "elsewhere" / CANDIDATE_ID
            candidate_dir.mkdir(parents=True)
            (candidate_dir / "file.html").write_text("samples root copy", encoding="utf-8")

            previous_cwd = os.getcwd()
            os.chdir(root)
            try:
                resolved = _resolve_sample_path(str(recorded), candidate_dir)
            finally:
                os.chdir(previous_cwd)

        self.assertEqual(resolved, candidate_dir / "file.html")

    def test_falls_back_to_cwd_relative_path(self) -> None:
        # Recorded paths without the candidate directory component keep the
        # legacy CWD-relative behavior.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recorded = Path("other-tree") / "file.html"
            (root / recorded).parent.mkdir(parents=True)
            (root / recorded).write_text("cwd file", encoding="utf-8")
            candidate_dir = root / CANDIDATE_ID
            candidate_dir.mkdir()

            previous_cwd = os.getcwd()
            os.chdir(root)
            try:
                resolved = _resolve_sample_path(str(recorded), candidate_dir)
            finally:
                os.chdir(previous_cwd)

        self.assertEqual(resolved, recorded)

    def test_unresolvable_path_reports_candidate_anchored_guess(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            candidate_dir = Path(tmp) / CANDIDATE_ID
            candidate_dir.mkdir()
            recorded = f"samples/html/2016-seimo/{CANDIDATE_ID}/campaigns/x/tab.html"
            resolved = _resolve_sample_path(recorded, candidate_dir)

        self.assertEqual(resolved, candidate_dir / "campaigns" / "x" / "tab.html")


if __name__ == "__main__":
    unittest.main()
