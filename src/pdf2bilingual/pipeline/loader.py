# converter/loader.py — 读取中间数据 content.json
import json, os, glob
from pdf2bilingual.paths import WORK_ROOT


def load(key):
    path = os.path.join(WORK_ROOT, key, "content.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def list_keys():
    return [os.path.basename(os.path.dirname(c))
            for c in glob.glob(os.path.join(WORK_ROOT, "*", "content.json"))]
