---
name: hiblup-ebv
description: >-
  Estimate breeding values (EBV) using GBLUP via HI-BLUP from phenotype and genotype tables,
  with a local R backend and ClawBio-compatible report outputs.
version: 0.1.0
author: ClawBio
license: MIT
tags: [animal-breeding, gblup, ebv, hiblup, quantitative-genetics]
metadata:
  openclaw:
    requires:
      bins:
        - python3
        - Rscript
        - plink
        - hiblup
      env: []
      config: []
    always: false
    emoji: "🐄"
    homepage: https://github.com/kzy599/ClawBio
    os: [linux, darwin]
    install:
      - kind: pip
        package: pandas
        bins: []
    trigger_keywords:
      - gblup
      - ebv
      - breeding value
      - hiblup
      - genomic selection
      - estimate ebv
---

# 🐄 HI-BLUP EBV

You are **HI-BLUP EBV**, a ClawBio skill for estimating genomic breeding values using GBLUP (HI-BLUP backend).

## Core Capabilities

1. Convert genotype CSV to PLINK PED/MAP (when needed)
2. Build genomic relationship matrix via HI-BLUP workflow
3. Estimate EBV and write `phe_ebv.csv`, `sel_ebv.csv`, `ref_ebv.csv`
4. Produce ClawBio-style `report.md`, `result.json`, and reproducibility files

## Input Formats

| Format | Extension | Required Fields | Example |
|---|---|---|---|
| Phenotype | `.csv` | `ID` and trait column position (`--trait-pos`) | `phe.csv` |
| Genotype | `.csv` | first column `ID`, remaining marker columns coded as 0/1/2 | `geno.csv` |
| Selection IDs | `.csv` | `ID` | `sel_id.csv` |
| Reference IDs | `.csv` | `ID` | `ref_id.csv` |

## Workflow

1. Validate required files
2. Optionally generate demo input (`filegenerator.r`)
3. Run R thin wrapper (`run_hiblup.r`) to execute PLINK + HI-BLUP steps
4. Collect EBV tables and generate report artifacts

## CLI Reference

```bash
python skills/hiblup-ebv/hiblup_ebv.py \
  --input <input_dir> --output <report_dir> --trait-pos 4

python skills/hiblup-ebv/hiblup_ebv.py --demo --output /tmp/hiblup_demo

python clawbio.py run hiblup --demo
```

## Demo

`--demo` will call `filegenerator.r` to generate synthetic `phe.csv`, `geno.csv`, `sel_id.csv`, `ref_id.csv`, then run EBV estimation.

## Output Structure

```
output_directory/
├── report.md
├── result.json
├── tables/
│   ├── phe_ebv.csv
│   ├── sel_ebv.csv
│   └── ref_ebv.csv
└── reproducibility/
    ├── run.log
    ├── commands.sh
    └── workdir/
```

## Safety

- Local-first: all genomic data processing remains on-machine
- Reports include required ClawBio disclaimer
- Warn-before-overwrite enforced by CLI
- No external API calls with sample-level genetic data
