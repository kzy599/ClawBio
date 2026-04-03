import json
import subprocess
import sys
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPT = SKILL_DIR / "hiblup_ebv.py"


def test_demo_mode_uses_filegenerator_and_writes_outputs(tmp_path):
    out_dir = tmp_path / "hiblup_demo"

    cmd = [
        sys.executable,
        str(SCRIPT),
        "--demo",
        "--fast-demo",
        "--output",
        str(out_dir),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)

    assert proc.returncode == 0, proc.stderr

    payload = json.loads(proc.stdout)
    assert payload["mode"] == "demo"
    assert payload["summary"]["n_records"] > 0

    assert (out_dir / "report.md").exists()
    assert (out_dir / "result.json").exists()

    assert (out_dir / "tables" / "phe_ebv.csv").exists()
    assert (out_dir / "tables" / "sel_ebv.csv").exists()
    assert (out_dir / "tables" / "ref_ebv.csv").exists()

    assert (out_dir / "work" / "phe.csv").exists()
    assert (out_dir / "work" / "geno.csv").exists()
    assert (out_dir / "work" / "sel_id.csv").exists()
    assert (out_dir / "work" / "ref_id.csv").exists()

    report_text = (out_dir / "report.md").read_text()
    assert "ClawBio is a research and educational tool" in report_text
