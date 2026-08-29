"""PyInstaller entry point for the openlab backend.

Runs uvicorn programmatically (no --reload in packaged mode).
Port can be overridden via --port CLI argument or OPENLAB_PORT env var.
"""
import sys
import os

# frozen environment: data directory is alongside the exe
if getattr(sys, "frozen", False):
    exe_dir = os.path.dirname(sys.executable)
    os.environ.setdefault(
        "DATA_DIR",
        os.path.join(exe_dir, "data"),
    )
    bundled_browsers = os.path.join(exe_dir, "playwright-browsers")
    if not os.path.isdir(bundled_browsers):
        bundled_browsers = os.path.join(exe_dir, "_internal", "playwright-browsers")
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", bundled_browsers)

import uvicorn

if __name__ == "__main__":
    args = sys.argv[1:]
    if "--check-imports" in args:
        import importlib

        for module_name in ("playwright.sync_api", "pymupdf", "fitz"):
            importlib.import_module(module_name)
            print(f"[check-imports] OK: {module_name}")
        print(
            "[check-imports] PLAYWRIGHT_BROWSERS_PATH="
            f"{os.environ.get('PLAYWRIGHT_BROWSERS_PATH', '')}"
        )
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            print(f"[check-imports] chromium executable: {p.chromium.executable_path}")
        sys.exit(0)
    port = 8001
    for i, arg in enumerate(args):
        if arg == "--port" and i + 1 < len(args):
            port = int(args[i + 1])
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, log_level="info")
