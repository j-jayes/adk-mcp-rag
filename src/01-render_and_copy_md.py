#!/usr/bin/env python3
"""
Render Quarto website (HTML) and export Markdown to data/.

- First render HTML site into quarto/_site (default).
- Then render Markdown (gfm) into quarto/_md (separate folder so we don't
  clobber the HTML site).
- Finally copy all .md files from quarto/_md/** into data/** preserving paths.

Usage:
    python src/01-render_and_copy_md.py
"""

import shutil
import subprocess
from pathlib import Path

# --- Paths (assumes this file lives in repo/src) ---
ROOT = Path(__file__).resolve().parents[1]
QUARTO_DIR = ROOT / "quarto"
HTML_OUT_DIR = QUARTO_DIR / "_site"
MD_OUT_DIR = QUARTO_DIR / "_md"   # temporary build dir for Markdown
DATA_DIR = ROOT / "data"

# Optional: clean old Markdown in data before copying
CLEAN_DATA_MD = False  # set True if you want to wipe old .md in data/

def run(cmd, cwd):
    try:
        res = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=True)
        return res.stdout
    except FileNotFoundError:
        raise SystemExit(
            "Could not find the 'quarto' CLI. Make sure Quarto is installed and on PATH."
        )
    except subprocess.CalledProcessError as e:
        print(e.stdout)
        print(e.stderr)
        raise SystemExit(1)

def render_html():
    print("📦 Rendering Quarto site → HTML (_site/)...")
    run(["quarto", "render"], cwd=QUARTO_DIR)
    if not HTML_OUT_DIR.exists():
        raise SystemExit("❌ Expected HTML output directory not found: _site/")
    print("✅ HTML render complete.")

def render_markdown():
    print("📦 Rendering Quarto site → GFM Markdown (_md/)...")
    # Render Markdown to a *separate* output dir so we don't overwrite _site
    MD_OUT_DIR.mkdir(exist_ok=True)
    run(["quarto", "render", "--to", "gfm", "--output-dir", str(MD_OUT_DIR)], cwd=QUARTO_DIR)
    print("✅ Markdown render complete.")

def clean_old_md_in_data():
    if not DATA_DIR.exists():
        return
    count = 0
    for p in DATA_DIR.rglob("*.md"):
        p.unlink(missing_ok=True)
        count += 1
    print(f"🧹 Removed {count} old .md files from data/.")

def copy_md_to_data():
    print("📂 Copying Markdown files from _md/ → data/ ...")
    if not MD_OUT_DIR.exists():
        raise SystemExit("❌ Markdown output directory not found: quarto/_md")

    DATA_DIR.mkdir(exist_ok=True)

    md_files = list(MD_OUT_DIR.rglob("*.md"))
    if not md_files:
        print("⚠️ No Markdown files found in quarto/_md.")
        return

    for src in md_files:
        rel = src.relative_to(MD_OUT_DIR)   # preserve folder structure
        dst = DATA_DIR / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"  → {rel}")

    print("✅ Copied Markdown into data/.")

def main():
    render_html()       # keeps your website working in _site/
    render_markdown()   # builds markdown in _md/, separate from _site/
    if CLEAN_DATA_MD:
        clean_old_md_in_data()
    copy_md_to_data()

if __name__ == "__main__":
    main()
