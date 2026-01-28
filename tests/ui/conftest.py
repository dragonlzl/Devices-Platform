import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def base_url():
    dist_path = Path(__file__).resolve().parents[2] / "frontend" / "dist" / "admin.html"
    if not dist_path.exists():
        pytest.skip("frontend/dist 未构建，请先在 frontend 目录执行 npm install && npm run build")
    os.environ["APP_DB_FILE"] = "data/apitest.db"
    db_path = Path(__file__).resolve().parents[2] / "data" / "apitest.db"
    if db_path.exists():
        db_path.unlink()
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8099",
        ],
        cwd=str(Path(__file__).resolve().parents[2]),
        env=os.environ.copy(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    url = "http://127.0.0.1:8099"
    for _ in range(40):
        try:
            with urllib.request.urlopen(url, timeout=0.5):
                break
        except Exception:
            time.sleep(0.25)
    else:
        proc.terminate()
        raise RuntimeError("测试服务器启动失败")

    yield url

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture(scope="session")
def browser_type_launch_args():
    return {
        "args": [
            "--disable-gpu",
            "--use-gl=swiftshader",
            "--no-sandbox",
        ]
    }
