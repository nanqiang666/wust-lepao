# -*- coding: utf-8 -*-
"""探测 addSchFaceInfo（注册学校人脸）的正确字段，以及 faceVerify 是否做 1:1 比对。"""
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
from lepao import capture_photo as CP


def main():
    reg = AccountRegistry(os.path.join(BASE, "config.json"))
    auth = AuthState(reg, reg.resolve())
    client = auth.make_client(pace=0.3)
    now = int(time.time())

    photo_bytes, src = CP.load_capture_photo_bytes(None)
    face_b64 = base64.b64encode(photo_bytes).decode()
    print(f"[0] 照片 {len(photo_bytes)} 字节 src={src}")

    print(f"\n=== addSchFaceInfo 字段探测 ===")
    sets = [
        {"type": "1", "face_file": face_b64},
        {"face_file": face_b64},
        {"type": "1", "game_id": "2448", "face_file": face_b64},
        {"face_img": face_b64},
        {"type": "1", "face_img": face_b64},
        {"type": "2", "face_file": face_b64},
    ]
    for ps in sets:
        brief = dict(ps)
        for k in ("face_file", "face_img"):
            if k in brief:
                brief[k] = f"<base64 {len(ps[k])} chars>"
        try:
            r = client.post("/v3/api.php/Run2/addSchFaceInfo", ps)
            print(f"  {json.dumps(brief, ensure_ascii=False)[:80]}")
            print(f"     -> status={r.get('status')} info={str(r.get('info'))[:60]!r} data={str(r.get('data'))[:150]!r}")
        except Exception as e:
            print(f"  {brief} 异常 {e.__class__.__name__} {str(e)[:60]}")

    print(f"\n=== 查询人脸注册状态 getZfbFaceVerifyRecord ===")
    try:
        r = client.post("/v3/api.php/Run2/getZfbFaceVerifyRecord", {"game_id": "2448", "start_time": str(now - 600)})
        print(f"  -> {json.dumps(r, ensure_ascii=False)[:300]}")
    except Exception as e:
        print(f"  异常 {e}")


if __name__ == "__main__":
    main()
