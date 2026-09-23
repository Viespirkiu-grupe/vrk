"""Read the maintained Astro sources for dashboard regression tests.

Behavior tests execute helpers from the actual client module. UI assertions also
read the Astro templates and CSS, so they do not depend on a local build or the
formatting/minification of generated assets. There is deliberately no fallback
to the retired MVP HTML: a missing source is a broken checkout.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_SOURCE = REPO_ROOT / "frontend" / "src"
SCRIPT_PATH = FRONTEND_SOURCE / "scripts" / "dashboard.js"


def script_source() -> str:
    paths = [*sorted((FRONTEND_SOURCE / "lib").glob("*.js")), SCRIPT_PATH]
    source = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    # The extracted helper bodies run independently under Node, outside module
    # loading. Keep their source untouched apart from the module-boundary syntax.
    source = re.sub(r"^import\b.*?;\s*$", "", source, flags=re.M | re.S)
    source = re.sub(r"^export\s*\{[^}]*\};?\s*$", "", source, flags=re.M)
    return re.sub(r"^export (?=(?:async )?(?:function|const|let|class)\b)", "", source, flags=re.M)


def style_source() -> str:
    return "\n".join(
        (FRONTEND_SOURCE / "styles" / name).read_text(encoding="utf-8")
        for name in ("tokens.css", "dashboard.css")
    )


def markup_source() -> str:
    # index.astro is required; the layouts/components are maintained alongside it.
    paths = [FRONTEND_SOURCE / "pages" / "index.astro"]
    for directory in ("layouts", "components"):
        paths.extend(sorted((FRONTEND_SOURCE / directory).glob("*.astro")))
    return "\n".join(path.read_text(encoding="utf-8") for path in paths)


def dashboard_source() -> str:
    return "\n".join((markup_source(), style_source(), script_source()))
