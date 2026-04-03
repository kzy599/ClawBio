#!/usr/bin/env python3
"""HI-BLUP EBV skill wrapper.

Thin Python shell for an R-based EBV workflow:
- --demo: call filegenerator.r to create synthetic inputs
- run_hiblup.r: execute PLINK + hiblup steps and produce EBV CSV outputs
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from clawbio.common.report import DISCLAIMER, write_result_json

SKILL_NAME = "hiblup-ebv"
SKILL_VERSION = "0.1.0"
SKILL_DIR = Path(__file__).resolve().parent
DEFAULT_PHE = "phe.csv"
DEFAULT_GENO = "geno.csv"
DEFAULT_SEL = "sel_id.csv"
DEFAULT_REF = "ref_id.csv"


def _run_cmd(cmd: list[str], cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), env=env, text=True, capture_output=True, check=False)


def _resolve_input_paths(input_path: Path, phe_file: str, geno_file: str, sel_file: str, ref_file: str) -> dict[str, Path]:
    if not input_path.is_dir():
        raise ValueError("--input 必须是目录，目录内需包含 phe/geno/sel/ref 文件")

    paths = {
        "phe": input_path / phe_file,
        "geno": input_path / geno_file,
        "sel": input_path / sel_file,
        "ref": input_path / ref_file,
    }
    missing = [str(p) for p in paths.values() if not p.exists()]
    if missing:
        raise FileNotFoundError(f"缺少输入文件: {', '.join(missing)}")
    return paths


def generate_demo_data(work_dir: Path, env: dict[str, str] | None = None) -> dict[str, Path]:
    script = SKILL_DIR / "filegenerator.r"
    proc = _run_cmd(["Rscript", str(script), "--output", str(work_dir)], cwd=work_dir, env=env)
    if proc.returncode != 0:
        raise RuntimeError(f"Demo 数据生成失败:\n{proc.stderr}")

    paths = {
        "phe": work_dir / DEFAULT_PHE,
        "geno": work_dir / DEFAULT_GENO,
        "sel": work_dir / DEFAULT_SEL,
        "ref": work_dir / DEFAULT_REF,
    }
    for path in paths.values():
        if not path.exists():
            raise FileNotFoundError(f"Demo 生成后缺少文件: {path}")
    return paths


def run_ebv(
    work_dir: Path,
    phe_path: Path,
    geno_path: Path,
    sel_path: Path,
    ref_path: Path,
    trait_pos: int,
    plink_format: bool,
    threads: int,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    script = SKILL_DIR / "run_hiblup.r"
    cmd = [
        "Rscript",
        str(script),
        "--phe-file",
        str(phe_path),
        "--geno-file",
        str(geno_path),
        "--sel-id",
        str(sel_path),
        "--ref-id",
        str(ref_path),
        "--trait-pos",
        str(trait_pos),
        "--threads",
        str(threads),
        "--workdir",
        str(work_dir),
    ]
    if plink_format:
        cmd.append("--plink-format")

    proc = _run_cmd(cmd, cwd=work_dir, env=env)
    if proc.returncode != 0:
        raise RuntimeError(f"EBV 计算失败:\n{proc.stderr}")

    output_files = {
        "phe_ebv": work_dir / "phe_ebv.csv",
        "sel_ebv": work_dir / "sel_ebv.csv",
        "ref_ebv": work_dir / "ref_ebv.csv",
    }
    for key, path in output_files.items():
        if not path.exists():
            raise FileNotFoundError(f"期望输出缺失 ({key}): {path}")

    return {
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "files": output_files,
    }


def _collect_summary(phe_ebv_file: Path) -> dict[str, Any]:
    lines = phe_ebv_file.read_text().strip().splitlines()
    return {"n_records": max(0, len(lines) - 1), "ebv_column": "ebv1"}


def _write_report(output_dir: Path, mode: str, trait_pos: int, summary: dict[str, Any]) -> Path:
    report = "\n".join(
        [
            "# HI-BLUP GBLUP EBV Report",
            "",
            f"**Date**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            f"**Skill**: {SKILL_NAME}",
            f"**Mode**: {mode}",
            f"**Trait position**: {trait_pos}",
            "",
            "## Summary",
            "",
            f"- Records with EBV: {summary['n_records']}",
            f"- EBV column: `{summary['ebv_column']}`",
            "",
            "## Output Files",
            "",
            "- `tables/phe_ebv.csv`",
            "- `tables/sel_ebv.csv`",
            "- `tables/ref_ebv.csv`",
            "",
            "## Disclaimer",
            "",
            f"*{DISCLAIMER}*",
            "",
        ]
    )
    path = output_dir / "report.md"
    path.write_text(report)
    return path


def _write_reproducibility(output_dir: Path, mode: str, trait_pos: int, threads: int, plink_format: bool, run_result: dict[str, Any]) -> None:
    repro_dir = output_dir / "reproducibility"
    repro_dir.mkdir(parents=True, exist_ok=True)

    cmd_parts = [
        "python skills/hiblup-ebv/hiblup_ebv.py",
        "--demo" if mode == "demo" else "--input <input_dir>",
        f"--output {output_dir}",
        f"--trait-pos {trait_pos}",
        f"--threads {threads}",
    ]
    if plink_format:
        cmd_parts.append("--plink-format")

    (repro_dir / "commands.sh").write_text("#!/usr/bin/env bash\n" + " \\\n  ".join(cmd_parts) + "\n")
    (repro_dir / "run.log").write_text(f"[STDOUT]\n{run_result['stdout']}\n\n[STDERR]\n{run_result['stderr']}\n")


def _copy_outputs(run_result: dict[str, Any], output_dir: Path, work_dir: Path) -> dict[str, Path]:
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    copied: dict[str, Path] = {}
    for key, src in run_result["files"].items():
        dst = tables_dir / src.name
        shutil.copy2(src, dst)
        copied[key] = dst

    work_copy = output_dir / "reproducibility" / "workdir"
    if work_copy.exists():
        shutil.rmtree(work_copy)
    shutil.copytree(work_dir, work_copy)

    return copied


def run_pipeline(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = Path(args.output).resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        print(f"Warning: output directory already exists and contains files: {output_dir}", file=sys.stderr)
    output_dir.mkdir(parents=True, exist_ok=True)

    work_dir = output_dir / "work"
    work_dir.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    if args.fast_demo:
        env["HIBLUP_EBV_FAST_DEMO"] = "1"
        env["HIBLUP_EBV_MOCK"] = "1"

    if args.demo:
        inputs = generate_demo_data(work_dir=work_dir, env=env)
        mode = "demo"
    else:
        if not args.input:
            raise ValueError("非 demo 模式下必须提供 --input")
        inputs = _resolve_input_paths(
            input_path=Path(args.input).resolve(),
            phe_file=args.phe_file,
            geno_file=args.geno_file,
            sel_file=args.sel_file,
            ref_file=args.ref_file,
        )
        mode = "input"

    run_result = run_ebv(
        work_dir=work_dir,
        phe_path=inputs["phe"],
        geno_path=inputs["geno"],
        sel_path=inputs["sel"],
        ref_path=inputs["ref"],
        trait_pos=args.trait_pos,
        plink_format=args.plink_format,
        threads=args.threads,
        env=env,
    )

    copied = _copy_outputs(run_result=run_result, output_dir=output_dir, work_dir=work_dir)
    summary = _collect_summary(copied["phe_ebv"])
    _write_report(output_dir=output_dir, mode=mode, trait_pos=args.trait_pos, summary=summary)
    _write_reproducibility(
        output_dir=output_dir,
        mode=mode,
        trait_pos=args.trait_pos,
        threads=args.threads,
        plink_format=args.plink_format,
        run_result=run_result,
    )

    result = {
        "mode": mode,
        "trait_pos": args.trait_pos,
        "summary": summary,
        "output_dir": str(output_dir),
        "tables": {k: str(v) for k, v in copied.items()},
    }

    write_result_json(
        output_dir=output_dir,
        skill=SKILL_NAME,
        version=SKILL_VERSION,
        summary={
            "mode": mode,
            "trait_pos": args.trait_pos,
            "n_records": summary["n_records"],
        },
        data=result,
    )

    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="HI-BLUP GBLUP EBV skill")
    parser.add_argument("--input", help="输入目录，需包含 phe.csv/geno.csv/sel_id.csv/ref_id.csv")
    parser.add_argument("--output", required=True, help="输出目录")
    parser.add_argument("--demo", action="store_true", help="使用 filegenerator.r 生成 demo 并运行")

    parser.add_argument("--phe-file", default=DEFAULT_PHE, help="输入目录中的表型文件名")
    parser.add_argument("--geno-file", default=DEFAULT_GENO, help="输入目录中的基因型文件名")
    parser.add_argument("--sel-file", default=DEFAULT_SEL, help="输入目录中的选择集 ID 文件名")
    parser.add_argument("--ref-file", default=DEFAULT_REF, help="输入目录中的参考集 ID 文件名")

    parser.add_argument("--trait-pos", type=int, default=4, help="hiblup 表型列位置（1-based）")
    parser.add_argument("--threads", type=int, default=32, help="hiblup/plink 线程数")
    parser.add_argument("--plink-format", action="store_true", help="geno 文件已是 plink 格式时启用")
    parser.add_argument("--fast-demo", action="store_true", help="测试专用：mock demo 加速")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.demo and not args.input:
        parser.error("Provide --input or use --demo")

    result = run_pipeline(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
