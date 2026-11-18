# -*- coding: utf-8 -*-
"""探测支付宝人脸验证替代通道 + 抓拍计数真相"""
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
    sel = None
    if "--member" in sys.argv:
        sel = sys.argv[sys.argv.index("--member") + 1]
    reg = AccountRegistry(os.path.join(BASE, "config.json"))
    key = reg.resolve(sel)
    auth = AuthState(reg, key)
    client = auth.make_client(pace=0.3)
    uid = auth.uid
    now = int(time.time())
    print(f"[探测] uid={uid}")

    # 1. 支付宝人脸记录
    print("\n=== [1] Run2/getZfbFaceVerifyRecord ===")
    for ps in [
        {},
        {"game_id": "1963"},
        {"game_id": "1963", "start_time": str(now - 600)},
        {"record_id": "513356"},
    ]:
        try:
            r = client.post("/v3/api.php/Run2/getZfbFaceVerifyRecord", ps)
            print(f"  {ps}: {json.dumps(r, ensure_ascii=False)[:250]}")
        except Exception as e:
            print(f"  {ps}: 异常 {e.__class__.__name__}")

    # 2. updateZfbStatus
    print("\n=== [2] Run2/updateZfbStatus ===")
    for ps in [
        {},
        {"status": "1"},
        {"zfb_status": "1"},
        {"record_id": "513356", "status": "1"},
    ]:
        try:
            r = client.post("/v3/api.php/Run2/updateZfbStatus", ps)
            print(f"  {ps}: {json.dumps(r, ensure_ascii=False)[:250]}")
        except Exception as e:
            print(f"  {ps}: 异常 {e.__class__.__name__}")

    # 3. addSchFaceInfo
    print("\n=== [3] Run2/addSchFaceInfo ===")
    for ps in [
        {},
        {"type": "1"},
        {"face_img": ""},
        {"game_id": "1963"},
    ]:
        try:
            r = client.post("/v3/api.php/Run2/addSchFaceInfo", ps)
            print(f"  {ps}: {json.dumps(r, ensure_ascii=False)[:250]}")
        except Exception as e:
            print(f"  {ps}: 异常 {e.__class__.__name__}")

    # 4. getCaptureStatus 的 miss_num 语义: 用不同 point_ids / distance 看变化
    print("\n=== [4] getCaptureStatus miss_num 语义探测 ===")
    for ps in [
        {"start_time": str(now - 600), "distance": "0.5", "game_id": "1963",
         "point_ids": "23604"},
        {"start_time": str(now - 600), "distance": "2.8", "game_id": "1963",
         "point_ids": "23604,23605,23607,25550"},
        {"start_time": str(now - 1800), "distance": "2.8", "game_id": "1963",
         "point_ids": "23604,23605,23607,25550"},
    ]:
        try:
            r = client.post("/v3/api.php/Run2/getCaptureStatus", ps)
            print(f"  {ps}: {json.dumps(r, ensure_ascii=False)[:200]}")
        except Exception as e:
            print(f"  {ps}: 异常 {e.__class__.__name__}")

    print("\n[探测] 完成")


if __name__ == "__main__":
    main()
