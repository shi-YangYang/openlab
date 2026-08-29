# PyInstaller spec for openlab backend
import os
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

block_cipher = None

# Collect langchain/langchain-openai data files and hidden imports
hiddenimports = [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "app.main",
    "app.config",
    "app.database",
    "app.translation",
    "app.experiment_runner",
    "app.reasoning_efforts",
    "app.redact",
    "app.ssh",
    "app.monitor",
    "app.downloader",
    "app.presets",
    "app.upload",
    "app.export",
    "app.llm",
    "app.llm_config",
    "app.arxiv",
    "app.pdf",
    "app.schemas",
    "app.search",
    "app.search.aggregator",
    "app.search.arxiv",
    "app.search.semantic_scholar",
    "app.search.baidu_xueshu",
    "app.search.cnki",
    "app.search.base",
    "app.platforms",
    "app.platforms.browser",
    "app.platforms.sessions",
    "app.agent",
    "app.agent.agent",
    "app.agent.tools",
    "app.agent.ws",
    "app.agent.sandbox",
    "app.agent.sessions",
    "app.agent.compaction",
    "app.experiment",
    "app.innovation",
    "app.analysis",
]
hiddenimports += collect_submodules("langchain")
hiddenimports += collect_submodules("langchain_core")
hiddenimports += collect_submodules("langchain_openai")
hiddenimports += collect_submodules("langchain_community")
hiddenimports += collect_submodules("pydantic")

playwright_datas, playwright_binaries, playwright_hiddenimports = collect_all("playwright")
hiddenimports += playwright_hiddenimports

datas = []
datas += collect_data_files("langchain")
datas += collect_data_files("langchain_core")
datas += collect_data_files("langchain_openai")
datas += collect_data_files("pymupdf")
datas += playwright_datas

ms_playwright_dir = os.path.join(os.environ.get("LOCALAPPDATA", ""), "ms-playwright")
if not os.path.isdir(ms_playwright_dir):
    ms_playwright_dir = os.path.join(
        os.path.expanduser("~"), "AppData", "Local", "ms-playwright"
    )
if os.path.isdir(ms_playwright_dir):
    datas.append((ms_playwright_dir, "playwright-browsers"))

binaries = list(playwright_binaries)

a = Analysis(
    ["main_entry.py"],
    pathex=[SPECPATH],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="openlab-backend",
    debug=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="openlab-backend",
)
