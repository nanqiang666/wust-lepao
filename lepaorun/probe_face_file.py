# -*- coding: utf-8 -*-
"""用正确字段 face_file 探测 faceVerify 真实行为（只读，不提交）。"""
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

    # 取一张照片的 base64 和字节
    photo_bytes, src = CP.load_capture_photo_bytes(None)
    print(f"[0] 照片 {len(photo_bytes)} 字节 src={src}")

    import base64
    face_b64 = base64.b64encode(photo_bytes).decode()

    print(f"\n=== face_file 字段探测 ===")
    sets = [
        {"type": "1", "game_id": "2448"},
        {"type": "1", "face_file": face_b64[:64] + "..."},
        {"type": "1", "face_file": face_b64},
        {"type": "1", "game_id": "2448", "face_file": face_b64},
        {"type": "1", "game_id": "2448", "start_time": str(now - 600), "face_file": face_b64},
        {"type": "2", "game_id": "2448", "face_file": face_b64},
    ]
    for ps in sets:
        # face_file 太长，打印时截断
        brief = dict(ps)
        if "face_file" in brief:
            brief["face_file"] = f"<base64 {len(ps['face_file'])} chars>"
        try:
            r = client.post("/v3/api.php/Run2/faceVerify", ps)
            print(f"  {json.dumps(brief, ensure_ascii=False)[:80]}")
            print(f"     -> status={r.get('status')} info={str(r.get('info'))[:60]!r} data={str(r.get('data'))[:150]!r}")
        except Exception as e:
            print(f"  {brief} 异常 {e.__class__.__name__} {str(e)[:60]}")


if __name__ == "__main__":
    main()
