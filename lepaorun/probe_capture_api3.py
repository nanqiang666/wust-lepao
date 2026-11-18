# -*- coding: utf-8 -*-
"""第三波抓拍接口探测: 重点探测"文件关联"类接口(类比 Run2/gyroscope 模式)。
只读探测(传空参数, 看接口是否存在)。"""
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
os.environ.setdefault("LEPAO2_CONFIG", os.path.join(BASE, "config.json"))

from lepao.accounts import AccountRegistry
from lepao.auth import AuthState

# 重点: 类比 gyroscope 的"文件关联"接口, 以及之前没试过的词根组合
CANDIDATES = [
    "Run2/captureFile", "Run2/saveCaptureFile", "Run2/uploadCaptureFile",
    "Run2/captureImgFile", "Run2/capturePhotoFile", "Run2/uploadCapturePhoto",
    "Run2/saveCapturePhoto", "Run2/capturePic", "Run2/uploadCapturePic",
    "Run2/saveCapturePic", "Run2/runCaptureFile", "Run2/captureRunFile",
    "Run2/captureImageFile", "Run2/uploadImage", "Run2/saveImage",
    "Run2/captureFileV2", "Run2/captureV2", "Run2/uploadCaptureV2",
    "Run2/capturePhotoV2", "Run2/savePhoto", "Run2/uploadPhotoFile",
    "Run2/addCapture", "Run2/addCaptureFile", "Run2/addPhoto",
    "Run2/captureAdd", "Run2/photoAdd", "Run2/captureSave",
    "Run2/checkPhoto", "Run2/checkImg", "Run2/captureCheckV2",
]


def main():
    sel = None
    if "--member" in sys.argv:
        sel = sys.argv[sys.argv.index("--member") + 1]
    reg = AccountRegistry(os.path.join(BASE, "config.json"))
    key = reg.resolve(sel)
    auth = AuthState(reg, key)
    client = auth.make_client(pace=0.2)

    print(f"[探测3] 成员 {auth.label} uid={auth.uid}")
    found = []
    for c in CANDIDATES:
        path = f"/v3/api.php/{c}"
        try:
            resp = client.post(path, {})
        except Exception:
            continue  # 404
        if isinstance(resp, dict):
            st = resp.get("status")
            info = str(resp.get("info") or "")[:50]
            print(f"  ★[{c}] status={st} info={info!r}")
            found.append(c)
    print(f"[探测3] 完成, 找到 {len(found)} 个存在的接口")


if __name__ == "__main__":
    main()
