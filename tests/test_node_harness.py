"""Node-run tests hand node their script on stdin, never through argv.

Linux's execve refuses any single argument longer than MAX_ARG_STRLEN
(32 pages, 131,072 bytes) with E2BIG. macOS has no per-argument cap, so a
script passed as `node -e <script>` passes on the laptop and fails on the CI
runner. The comparison-row tests embed the whole concept map in their script:
#162's concepts took eleven of those scripts to 144,559-166,741 bytes, and all
eleven failed on CI only. A script piped in has no such limit.
"""

import re
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent

#: A node argv that carries its program: -e/--eval or -p/--print.
EVAL_FLAG = re.compile(r'\[NODE\b[^\]]*"(?:-e|--eval|-p|--print)"')


class NodeScriptsGoThroughStdinTests(unittest.TestCase):
    def test_no_test_passes_node_its_script_through_argv(self):
        offenders = [
            f"{path.name}:{number}"
            for path in sorted(TESTS.glob("test_*.py"))
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
            if EVAL_FLAG.search(line)
        ]
        self.assertEqual(offenders, [], 'pipe the script in: subprocess.run([NODE, "-"], input=script, ...)')


if __name__ == "__main__":
    unittest.main()
