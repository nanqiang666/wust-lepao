# -*- coding: utf-8 -*-
"""探测 faceVerify 的 type 语义与正确参数（只读）"""
import json
import os
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
os.environ.setdefault("LEPAO2_CONFIG", os.path.join(BASE, "config.json"))

from lepao.accounts import AccountRegistry
from lepao.auth import AuthState


def main():
    reg = AccountRegistry(os.path.join(BASE, "config.json"))
    auth = AuthState(reg, reg.resolve())
    client = auth.make_client(pace=0.3)
    now = int(time.time())
    print(f"[faceVerify type 探测] uid={auth.uid}")

    sets = [
        {"type": "1"},
        {"type": "1", "game_id": "2448"},
        {"type": "1", "game_id": "2448", "start_time": str(now - 600)},
        {"type": "2", "game_id": "2448"},
        {"type": "3", "game_id": "2448"},
        {"type": "1", "game_id": "2448", "start_time": str(now - 600), "face_img": ""},
        {"verify_type": "1", "game_id": "2448"},
        {"face_type": "1", "game_id": "2448"},
    ]
    for ps in sets:
        try:
            r = client.post("/v3/api.php/Run2/faceVerify", ps)
            info = str(r.get("info"))[:40]
            data = str(r.get("data"))[:100]
            print(f"  {json.dumps(ps, ensure_ascii=False)[:70]} -> "
                  f"status={r.get('status')} info={info!r} data={data!r}")
        except Exception as e:
            print(f"  {ps} 异常 {e.__class__.__name__} {str(e)[:60]}")

    print("[完成]")


if __name__ == "__main__":
    main()
