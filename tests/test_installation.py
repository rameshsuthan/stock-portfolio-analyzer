"""Exercise the installed package without pytest's source-path assistance."""

import subprocess
import sys


def test_installed_entrypoint_imports_without_source_path(tmp_path):
    result = subprocess.run(
        [sys.executable, "-I", "-c", "from stock_portfolio.ui import main; assert callable(main)"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
