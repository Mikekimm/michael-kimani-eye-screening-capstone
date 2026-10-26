"""Render docs/report/report.html to report.pdf with Chromium (Playwright).

Usage:  python docs/report/build_report.py
No Playwright? Open report.html in Chrome and choose Print -> Save as PDF (A4, margins: default, background graphics on).
Checks that the PDF has at most 5 pages.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto((HERE / "report.html").as_uri())
        page.pdf(path=str(HERE / "report.pdf"), format="A4", print_background=True, prefer_css_page_size=True)
        browser.close()
    try:
        from pypdf import PdfReader
        pages = len(PdfReader(str(HERE / "report.pdf")).pages)
        print(f"report.pdf: {pages} page(s)" + ("" if pages <= 5 else "  <-- OVER THE 5-PAGE LIMIT"))
    except ImportError:
        print("report.pdf written (install pypdf to check the page count)")


if __name__ == "__main__":
    main()
