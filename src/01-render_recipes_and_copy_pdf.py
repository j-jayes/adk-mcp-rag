#!/usr/bin/env python3
"""
Render Quarto website (HTML) and export PDFs (with embedded YAML) to data/.

Pipeline:
1) Render HTML site into quarto/_site/ (keeps your website working).
2) For each content page (e.g., quarto/recipes/*.qmd):
   - Create a temporary augmented copy that appends the source YAML front matter
     as a visible `yaml` code block in the body (so info is included in the PDF text).
   - Render that temp file to PDF into quarto/_pdf/<subdir>/.
     (We render each file with `cwd=out_dir` and `--output <name>.pdf`.)
3) Copy PDFs from quarto/_pdf/** into data/**, preserving folder structure.

Usage:
    python src/01-render_recipes_and_copy_pdf.py
"""

import re
import shutil
import subprocess
from pathlib import Path

# --- Paths (assumes this file lives in repo/src) ---
ROOT = Path(__file__).resolve().parents[1]
QUARTO_DIR = ROOT / "quarto"
HTML_OUT_DIR = QUARTO_DIR / "_site"
PDF_TMP_DIR = QUARTO_DIR / "_tmp_pdf"   # augmented .qmd sources
PDF_OUT_DIR = QUARTO_DIR / "_pdf"       # final PDFs land here
DATA_DIR = ROOT / "data"

# Which subfolders contain the documents you want PDFs for
CONTENT_SUBDIRS = ["recipes"]

# Optional: clean old PDFs in data before copying
CLEAN_DATA_PDF = True

def run(cmd, cwd=None):
    try:
        res = subprocess.run(
            cmd, cwd=cwd, text=True, capture_output=True, check=True
        )
        return res.stdout
    except FileNotFoundError:
        raise SystemExit(
            "Could not find the 'quarto' CLI. Make sure Quarto is installed and on PATH."
        )
    except subprocess.CalledProcessError as e:
        print(e.stdout)
        print(e.stderr)
        raise SystemExit(1)

def render_html_site():
    print("📦 Rendering Quarto site → HTML (_site/)...")
    run(["quarto", "render"], cwd=QUARTO_DIR)
    if not HTML_OUT_DIR.exists():
        raise SystemExit("❌ Expected HTML output directory not found: _site/")
    print("✅ HTML render complete.")

YAML_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)

def split_front_matter(text: str):
    """Return (yaml_text, body_text). If no YAML is found, yaml_text=''."""
    m = YAML_RE.match(text)
    if not m:
        return "", text
    yaml_text = m.group(1)
    body_text = text[m.end():]
    return yaml_text, body_text

def make_augmented_qmd(src_qmd: Path, dst_qmd: Path):
    """
    Copy a .qmd and append a visible YAML dump to the end as a code block,
    so the PDF includes the YAML info in its text content.
    """
    raw = src_qmd.read_text(encoding="utf-8")
    yaml_text, body = split_front_matter(raw)

    fm_prefix = f"---\n{yaml_text}\n---\n" if yaml_text else ""
    meta_section = (
        "\n\n## Metadata (YAML)\n\n```yaml\n"
        f"{yaml_text.strip()}\n```\n"
        if yaml_text else ""
    )

    dst_qmd.parent.mkdir(parents=True, exist_ok=True)
    dst_qmd.write_text(fm_prefix + body + meta_section, encoding="utf-8")

def collect_source_qmds():
    """Yield all source .qmd files to render as PDFs (skip project root index.qmd)."""
    for sub in CONTENT_SUBDIRS:
        for qmd in (QUARTO_DIR / sub).rglob("*.qmd"):
            yield qmd

def render_pdfs():
    """
    Create augmented temp .qmds with YAML embedded, then render each to PDF.

    NOTE: For single-file renders, Quarto forbids paths in --output.
    We set cwd=target_out_dir and pass only the filename to --output.
    """
    print("🛠️ Preparing augmented sources for PDF...")
    if PDF_TMP_DIR.exists():
        shutil.rmtree(PDF_TMP_DIR)
    PDF_TMP_DIR.mkdir(parents=True, exist_ok=True)

    PDF_OUT_DIR.mkdir(parents=True, exist_ok=True)

    augmented_files = []
    for src in collect_source_qmds():
        rel = src.relative_to(QUARTO_DIR)
        dst = PDF_TMP_DIR / rel  # mirror structure under _tmp_pdf
        make_augmented_qmd(src, dst)
        augmented_files.append(dst)

    if not augmented_files:
        print("⚠️ No content .qmd files found to render as PDF.")
        return

    print("📄 Rendering PDFs (single-file renders with cwd-outdir)...")
    for tmp_qmd in augmented_files:
        rel = tmp_qmd.relative_to(PDF_TMP_DIR)
        out_dir = PDF_OUT_DIR / rel.parent
        out_dir.mkdir(parents=True, exist_ok=True)

        # Output must be only a filename (no path) → set cwd=out_dir
        output_name = rel.with_suffix(".pdf").name
        # Use absolute path for the input qmd to be safe across cwd changes
        input_qmd_abs = str(tmp_qmd.resolve())

        run(
            [
                "quarto",
                "render",
                input_qmd_abs,
                "--to", "pdf",
                "--output", output_name,  # filename only!
            ],
            cwd=out_dir,  # ensures the PDF is written into out_dir
        )
        print(f"  ✓ {rel.with_suffix('.pdf')}")

    print("✅ PDF render complete.")

def clean_old_pdfs_in_data():
    if not DATA_DIR.exists():
        return
    count = 0
    for p in DATA_DIR.rglob("*.pdf"):
        p.unlink(missing_ok=True)
        count += 1
    print(f"🧹 Removed {count} old .pdf files from data/.")

def copy_pdfs_to_data():
    print("📂 Copying PDFs from _pdf/ → data/ ...")
    if not PDF_OUT_DIR.exists():
        raise SystemExit("❌ PDF output directory not found: quarto/_pdf")

    DATA_DIR.mkdir(exist_ok=True)

    pdfs = list(PDF_OUT_DIR.rglob("*.pdf"))
    if not pdfs:
        print("⚠️ No PDFs found in quarto/_pdf.")
        return

    for src in pdfs:
        rel = src.relative_to(PDF_OUT_DIR)   # preserve folder structure
        dst = DATA_DIR / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"  → {rel}")

    print("✅ Copied PDFs into data/.")

def main():
    render_html_site()   # keep your website working
    render_pdfs()        # build PDFs with YAML in body
    if CLEAN_DATA_PDF:
        clean_old_pdfs_in_data()
    copy_pdfs_to_data()

if __name__ == "__main__":
    main()
