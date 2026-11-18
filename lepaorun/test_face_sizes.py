# -*- coding: utf-8 -*-
"""压缩照片多尺寸重试 faceVerify，并检查人脸注册状态。"""
import base64
import io
import json
import os
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
os.environ.setdefault("LEPAO2_CONFIG", os.path.join(BASE, "config.json"))

from PIL import Image
from lepao.accounts import AccountRegistry
from lepao.auth import AuthState

PHOTO = r"D:\nanqiang\Downloads\IMG20261118173421..jpg"


def shrink(max_side, quality):
    img = Image.open(PHOTO)
    img = img.convert("RGB")
    w, h = img.size
    scale = min(1.0, max_side / max(w, h))
    if scale < 1.0:
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def main():
    reg = AccountRegistry(os.path.join(BASE, "config.json"))
    auth = AuthState(reg, reg.resolve())
    client = auth.make_client(pace=0.5)

    print("[0] 查询人脸注册状态")
    now = int(time.time())
    for ps in ({"game_id": "2448"}, {}):
        try:
            r = client.post("/v3/api.php/Run2/getZfbFaceVerifyRecord", ps)
            print(f"    {ps} -> {json.dumps(r, ensure_ascii=False)[:200]}")
        except Exception as e:
            print(f"    {ps} 异常 {e}")

    for max_side, q in ((1280, 85), (800, 80), (640, 75)):
        b = shrink(max_side, q)
        b64 = base64.b64encode(b).decode()
        print(f"\n[试] {max_side}px q{q} -> {len(b)} 字节 base64 {len(b64)}")
        r = client.post("/v3/api.php/Run2/faceVerify",
                        {"type": "1", "game_id": "2448", "face_file": b64})
        print(f"    status={r.get('status')} info={str(r.get('info'))[:80]!r}")
        if isinstance(r.get("data"), dict):
            print(f"    id={r['data'].get('run_face_verify_id')}")
        if r.get("status") == 1 and "错误" not in str(r.get("info")):
            print("    ★ 通过!")
            return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
