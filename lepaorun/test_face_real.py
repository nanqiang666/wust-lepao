# -*- coding: utf-8 -*-
"""用真人脸照片实测 faceVerify 闭环。"""
import base64
import json
import os
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
os.environ.setdefault("LEPAO2_CONFIG", os.path.join(BASE, "config.json"))

from lepao.accounts import AccountRegistry
from lepao.auth import AuthState

PHOTO = r"D:\nanqiang\Downloads\IMG20261118173421..jpg"


def main():
    b = open(PHOTO, "rb").read()
    print(f"[1] 照片 {len(b)} 字节")
    face_b64 = base64.b64encode(b).decode()
    print(f"[1] base64 {len(face_b64)} 字符")

    reg = AccountRegistry(os.path.join(BASE, "config.json"))
    auth = AuthState(reg, reg.resolve())
    client = auth.make_client(pace=0.5)
    now = int(time.time())

    print("[2] faceVerify type=1 (start) 带真人脸")
    r = client.post("/v3/api.php/Run2/faceVerify",
                    {"type": "1", "game_id": "2448", "face_file": face_b64})
    print(f"    status={r.get('status')} info={str(r.get('info'))[:80]!r}")
    print(f"    data={json.dumps(r.get('data'), ensure_ascii=False)[:300] if r.get('data') else None}")

    vid = None
    if isinstance(r.get("data"), dict):
        vid = r["data"].get("run_face_verify_id")
    print(f"    run_face_verify_id={vid}")

    if r.get("status") == 1 and vid:
        print("[3] type=3 (stop) 带同一张脸 + 同一会话id")
        r2 = client.post("/v3/api.php/Run2/faceVerify",
                         {"type": "3", "game_id": "2448", "face_file": face_b64,
                          "run_face_verify_id": vid})
        print(f"    status={r2.get('status')} info={str(r2.get('info'))[:80]!r}")
        print(f"    data={json.dumps(r2.get('data'), ensure_ascii=False)[:300] if r2.get('data') else None}")


if __name__ == "__main__":
    main()
