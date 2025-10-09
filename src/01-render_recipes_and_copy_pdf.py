#!/usr/bin/env python3
"""
Render Quarto website (HTML) and export PDFs (with embedded YAML) to data/.

Pipeline:
1) Render HTML site into quarto/_site/ (keeps your website working).
2) For each content page (e.g., quarto/recipes/*.qmd):
   - Create a temporary augmented copy that appends the source YAML front matter
     as a visible `yaml` code block in the body (so info is included in the PDF text).
   - Normalize text in the augmented copy only to improve PDF text extraction:
       • integer + vulgar fraction → decimal (e.g., 3½ → 3.5)
       • standalone vulgar fraction → ASCII (e.g., ½ → 1/2)
       • normalize dashes, NBSP, quotes, fraction slash
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

# --- Normalization rules for PDF text extraction ---
# Standalone ASCII replacements for vulgar fractions
_VULGAR_TO_ASCII = {
    "¼": "1/4",
    "½": "1/2",
    "¾": "3/4",
    "⅐": "1/7",
    "⅑": "1/9",
    "⅒": "1/10",
    "⅓": "1/3",
    "⅔": "2/3",
    "⅕": "1/5",
    "⅖": "2/5",
    "⅗": "3/5",
    "⅘": "4/5",
    "⅙": "1/6",
    "⅚": "5/6",
    "⅛": "1/8",
    "⅜": "3/8",
    "⅝": "5/8",
    "⅞": "7/8",
}

# When a vulgar fraction directly follows an integer, convert to decimal part
# Use readable decimals; exact where finite, otherwise common rounded approximations.
_VULGAR_TO_DECIMAL_PART = {
    "¼": ".25",
    "½": ".5",
    "¾": ".75",
    "⅐": ".14",   # ~.142857
    "⅑": ".11",   # ~.111...
    "⅒": ".1",
    "⅓": ".33",
    "⅔": ".67",
    "⅕": ".2",
    "⅖": ".4",
    "⅗": ".6",
    "⅘": ".8",
    "⅙": ".17",
    "⅚": ".83",
    "⅛": ".125",
    "⅜": ".375",
    "⅝": ".625",
    "⅞": ".875",
}

_VFRACS_CLASS = "".join(map(re.escape, _VULGAR_TO_ASCII.keys()))
# Match an integer followed (optionally with a space) by a vulgar fraction
_RE_INT_VFRAC = re.compile(rf"(?P<int>\d+)\s*(?P<vfrac>[{_VFRACS_CLASS}])")

def _replace_int_vfrac_with_decimal(m: re.Match) -> str:
    v = m.group("vfrac")
    dec = _VULGAR_TO_DECIMAL_PART.get(v)
    if dec is None:
        # Fallback: leave as integer + ASCII fraction with a space
        return f"{m.group('int')} {_VULGAR_TO_ASCII.get(v, '')}"
    # Avoid things like "3.50" -> keep as "3.5" by not adding trailing zeros beyond mapping
    return f"{m.group('int')}{dec}"

def normalize_text_for_pdf(text: str) -> str:
    """
    Normalize text to ASCII-friendly forms for robust PDF text extraction:
    - integer + vulgar fraction → decimal (3½ → 3.5)
    - standalone vulgar fraction → ASCII (½ → 1/2)
    - fraction slash: ⁄ → /
    - dashes: –, — → -
    - NBSP/narrow NBSP → space; remove zero-width characters
    - smart quotes → straight; ellipsis → ...
    """
    if not text:
        return text

    # Normalize spaces and remove zero-widths
    text = (
        text.replace("\u00A0", " ")  # NBSP
            .replace("\u202F", " ")  # narrow NBSP
            .replace("\u2009", " ")  # thin space
            .replace("\u200A", " ")  # hair space
            .replace("\u200B", "")   # zero-width space
            .replace("\uFEFF", "")   # BOM / zero-width no-break space
    )

    # Fraction slash
    text = text.replace("\u2044", "/")

    # Integer + vulgar fraction → decimal (3½ → 3.5)
    text = _RE_INT_VFRAC.sub(_replace_int_vfrac_with_decimal, text)

    # Replace remaining standalone vulgar fractions with ASCII (½ → 1/2)
    if _VFRACS_CLASS:
        text = re.sub(
            rf"[{_VFRACS_CLASS}]",
            lambda m: _VULGAR_TO_ASCII[m.group(0)],
            text,
        )

    # Normalize dashes
    text = text.replace("–", "-").replace("—", "-")

    # Normalize smart quotes and ellipsis
    text = text.translate({
        ord("“"): '"',
        ord("”"): '"',
        ord("‘"): "'",
        ord("’"): "'",
        ord("…"): "...",
    })

    return text

def make_augmented_qmd(src_qmd: Path, dst_qmd: Path):
    """
    Copy a .qmd and append a visible YAML dump to the end as a code block,
    so the PDF includes the YAML info in its text content.

    Important: Keep the original front matter unchanged for Quarto.
    Apply normalization to the BODY and to the visible YAML block only.
    """
    raw = src_qmd.read_text(encoding="utf-8")
    yaml_text, body = split_front_matter(raw)

    # Keep original front matter for Quarto metadata handling
    fm_prefix = f"---\n{yaml_text}\n---\n" if yaml_text else ""

    # Normalize only the content that will be rendered as PDF text
    norm_body = normalize_text_for_pdf(body)
    norm_yaml_visible = normalize_text_for_pdf(yaml_text)

    meta_section = (
        "\n\n## Metadata (YAML)\n\n```yaml\n"
        f"{norm_yaml_visible.strip()}\n```\n"
        if yaml_text else ""
    )

    dst_qmd.parent.mkdir(parents=True, exist_ok=True)
    dst_qmd.write_text(fm_prefix + norm_body + meta_section, encoding="utf-8")

def collect_source_qmds():
    """Yield all source .qmd files to render as PDFs (skip project root index.qmd)."""
    for sub in CONTENT_SUBDIRS:
        for qmd in (QUARTO_DIR / sub).rglob("*.qmd"):
            yield qmd

def render_pdfs():
    """
    Create augmented temp .qmds with YAML embedded (and normalized text),
    then render each to PDF.

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
    render_pdfs()        # build PDFs with YAML in body and normalized text
    if CLEAN_DATA_PDF:
        clean_old_pdfs_in_data()
    copy_pdfs_to_data()

if __name__ == "__main__":
    main()