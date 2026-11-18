# -*- coding: utf-8 -*-
"""第二波抓拍接口探测: 更系统的命名变体。只读。
"""
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
os.environ.setdefault("LEPAO2_CONFIG", os.path.join(BASE, "config.json"))

from lepao.accounts import AccountRegistry
from lepao.auth import AuthState

CANDIDATES = [
    "Run2/faceVerify", "Run2/face", "Run2/faceLogin", "Run2/faceCheck",
    "Run2/registerFace", "Run2/faceRegister", "Run2/addFace",
    "Run2/captureRun", "Run2/runCapture", "Run2/captureImage",
    "Run2/captureRecord", "Run2/uploadCaptureImg", "Run2/saveCaptureImg",
    "Run2/checkPoint", "Run2/captureCheck", "Run2/captureNum",
    "Run2/getCapture", "Run2/captureList", "Run2/captureInfo",
    "Run2/uploadImgRun", "Run2/runImg", "Run2/runPhoto",
    "Run2/photoUpload", "Run2/imgUpload", "Run2/captureUpload",
    "WpRun/faceVerify", "Run/faceVerify",
]


def main():
    sel = None
    if "--member" in sys.argv:
        sel = sys.argv[sys.argv.index("--member") + 1]
    reg = AccountRegistry(os.path.join(BASE, "config.json"))
    key = reg.resolve(sel)
    auth = AuthState(reg, key)
    client = auth.make_client(pace=0.3)

    print(f"[探测2] 成员 {auth.label} uid={auth.uid}")
    for c in CANDIDATES:
        path = f"/v3/api.php/{c}"
        try:
            resp = client.post(path, {})
        except Exception as e:
            print(f"  [{c}] 404/不存在")
            continue
        if isinstance(resp, dict):
            st = resp.get("status")
            info = str(resp.get("info") or "")[:50]
            print(f"  [{c}] ★JSON status={st} info={info!r}")
        else:
            print(f"  [{c}] 非JSON")
    print("[探测2] 完成")


if __name__ == "__main__":
    main()
