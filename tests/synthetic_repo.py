"""A tiny synthetic repository for the smoke-check tests: a built frontend,
an index, portraits and two records, laid out as scripts/serve_dashboard.py
serves them.
"""

from __future__ import annotations

from pathlib import Path

PID = "p0123456789ab"
PORTRAIT_VERSION = "abcd1234"
#: The smallest file that passes for a WebP: RIFF, size, WEBP.
WEBP = b"RIFF\x0c\x00\x00\x00WEBPVP8 \x00\x00\x00\x00"


def record(election: str, candidate: str, name: str) -> dict:
    return {
        "electionId": election,
        "candidateId": candidate,
        "candidateName": name,
        "source": {"url": f"https://www.vrk.lt/{candidate}"},
        "normalized": {"vardas": name},
    }


def make_repo(root: Path, portraits: bool = True) -> Path:
    """A repository with a built frontend, an index, portraits and two records.

    `portraits=False` leaves the person unflagged and the set unbuilt.
    """
    import importlib.util
    import json

    spec = importlib.util.spec_from_file_location("person_index_files", Path(__file__).resolve().parents[1] / "scripts" / "person_index_files.py")
    index_files = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(index_files)

    def write(relative: str, content: str | bytes) -> Path:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        (path.write_bytes if isinstance(content, bytes) else path.write_text)(content)
        return path

    for relative, body in {
        "data/2019-prezidento/vardenis-pavardenis-2019-prezidento.json": json.dumps(record("2019-prezidento", "vardenis-pavardenis-2019-prezidento", "Vardenis PAVARDENIS"), indent=2),
        "data/2020-seimo/vardenis-pavardenis-2020-seimo.json": json.dumps(record("2020-seimo", "vardenis-pavardenis-2020-seimo", "Vardenis PAVARDENIS"), indent=2),
        "docs/concept-map.json": '{"concepts": []}',
    }.items():
        write(relative, body)
    person = {
        "k": "VARDENIS PAVARDENIS|1970-01-01",
        "pid": PID,
        "n": "Vardenis PAVARDENIS",
        "b": "1970-01-01",
        "e": [
            {"id": "2019-prezidento", "c": "vardenis-pavardenis"},
            {"id": "2020-seimo", "c": "vardenis-pavardenis"},
        ],
        **({"ph": 1} if portraits else {}),
    }
    index = {
        "elections": [{"id": "2019-prezidento"}, {"id": "2020-seimo"}],
        "parties": {},
        "people": [person],
        **({"portraits": {"v": PORTRAIT_VERSION, "n": 1}} if portraits else {}),
    }
    index_files.write_index(index, root / "dashboard")
    write("dashboard/field-labels.json", json.dumps({"turtas": "Turtas"}))
    if portraits:
        write(f"portraits/{PID}.webp", WEBP)
        write("portraits/manifest.json", json.dumps({"version": PORTRAIT_VERSION, "portraits": {PID: {"out": "x", "outBytes": len(WEBP)}}}))
    write(
        "frontend/dist/index.html",
        '<!doctype html><html><head><link rel="stylesheet" href="/_astro/index.abc.css">'
        '<script type="module" src="/_astro/index.abc.js"></script></head><body>'
        + "<p>Kandidatai</p>" * 40 + "</body></html>",
    )
    write("frontend/dist/_astro/index.abc.js", "console.log('page');\n" * 40)
    write("frontend/dist/_astro/index.abc.css", "body { color: #1b313f; }\n" * 40)
    write("frontend/dist/branding/icon.svg", "<svg xmlns='http://www.w3.org/2000/svg'/>")
    return root
