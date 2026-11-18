# -*- coding: utf-8 -*-
"""验证 updateZfbStatus 更新成功后对 capture_num / zfb_face_verify_num 的影响。"""
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

    # 先看当前抓拍状态
    print("[0] 更新前 getZfbFaceVerifyRecord")
    r = client.post("/v3/api.php/Run2/getZfbFaceVerifyRecord",
                    {"game_id": "2448", "start_time": str(now - 600)})
    print(f"    -> {json.dumps(r, ensure_ascii=False)[:300]}")

    print("\n[1] updateZfbStatus 全参数组合（找哪些字段触发'更新成功'）")
    combos = [
        {"game_id": "2448", "start_time": str(now - 600), "status": "1", "type": "1"},
        {"game_id": "2448", "start_time": str(now - 600), "status": "1", "type": "2"},
        {"game_id": "2448", "start_time": str(now - 600), "status": "1", "type": "3"},
        {"game_id": "2448", "start_time": str(now - 600), "status": "1"},
        {"game_id": "2448", "start_time": str(now - 600), "type": "1"},
        {"game_id": "2448", "start_time": str(now - 600), "status": "1", "type": "1", "zfb_face_verify_id": "6afd74ae6e7e9"},
    ]
    for ps in combos:
        r = client.post("/v3/api.php/Run2/updateZfbStatus", ps)
        print(f"    {json.dumps(ps, ensure_ascii=False)[:80]} -> status={r.get('status')} info={str(r.get('info'))[:40]!r} data={str(r.get('data'))[:100]!r}")

    print("\n[2] 更新后 getZfbFaceVerifyRecord")
    r = client.post("/v3/api.php/Run2/getZfbFaceVerifyRecord",
                    {"game_id": "2448", "start_time": str(now - 600)})
    print(f"    -> {json.dumps(r, ensure_ascii=False)[:500]}")

    print("\n[3] 更新后 getCaptureStatus")
    r = client.post("/v3/api.php/Run2/getCaptureStatus",
                    {"start_time": str(now - 600), "distance": "3.0", "game_id": "2448",
                     "point_ids": "27989,27990,27991"})
    print(f"    -> {json.dumps(r, ensure_ascii=False)[:300]}")


if __name__ == "__main__":
    main()
