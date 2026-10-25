"""Paths for an editable source checkout or dist/release/PDFBilingual.exe."""
import os
import sys
from pathlib import Path

REPO_DIR = str(Path(__file__).resolve().parents[1])


def project_root():
    override = os.environ.get('PDFBILINGUAL_HOME')
    if override:
        return Path(override).resolve()
    if getattr(sys, 'frozen', False):
        folder = Path(sys.executable).resolve().parent
        if folder.name.lower() == 'release' and folder.parent.name.lower() == 'dist':
            return folder.parent.parent
        return folder
    repo = Path(REPO_DIR)
    return repo.parent if (repo / 'pyproject.toml').is_file() else Path.cwd()


PROJECT_ROOT = str(project_root())

DIST_DIR = os.path.join(PROJECT_ROOT, "dist")
WORK_ROOT = os.path.join(DIST_DIR, "work")        # 本地中间数据，不上传
OUTPUT_ROOT = os.path.join(DIST_DIR, "output")     # 最终产物
INPUT_ROOT = os.path.join(DIST_DIR, "input")       # 原始素材
CONFIG_ROOT = os.path.join(DIST_DIR, 'config')
BUILD_ROOT = os.path.join(DIST_DIR, 'build')
RELEASE_ROOT = os.path.join(DIST_DIR, 'release')

# 主题（海军蓝 + 白 + 浅灰）
NAVY = (31, 56, 100)
LIGHT = (242, 244, 248)
GREY = (74, 74, 74)
WHITE = (255, 255, 255)
EN_FONT = "Calibri"
ZH_FONT = "微软雅黑"
