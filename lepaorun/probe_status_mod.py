# -*- coding: utf-8 -*-
"""探测可改记录状态/越权的接口: 申诉/状态修改/平行上传/测试点管理"""
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

    # 1. 申诉接口 addRunComplain —— 能否把无效记录申诉成有效
    print("\n=== [1] Run/addRunComplain 申诉 ===")
    for ps in [
        {"record_id": "513356"},
        {"record_id": "513356", "content": "打卡点正常, 请求复核"},
        {"record_id": "513356", "type": "1", "content": "复核"},
        {"record_id": "513356", "complain_type": "1", "content": "抓拍已上传, 请求复核"},
    ]:
        try:
            r = client.post("/v3/api.php/Run/addRunComplain", ps)
            print(f"  {ps}: {json.dumps(r, ensure_ascii=False)[:250]}")
        except Exception as e:
            print(f"  {ps}: 异常 {e.__class__.__name__} {str(e)[:60]}")

    # 2. 状态修改接口 StatusToDel / RollbackDel
    print("\n=== [2] Run/StatusToDel 状态删除 ===")
    for ps in [
        {"record_id": "513356"},
        {"record_id": "513356", "status": "1"},
    ]:
        try:
            r = client.post("/v3/api.php/Run/StatusToDel", ps)
            print(f"  {ps}: {json.dumps(r, ensure_ascii=False)[:250]}")
        except Exception as e:
            print(f"  {ps}: 异常 {e.__class__.__name__}")

    # 3. 平行上传通道 uploadRunRecord
    print("\n=== [3] Run/uploadRunRecord 平行上传 ===")
    try:
        r = client.post("/v3/api.php/Run/uploadRunRecord", {"record_id": "513356"})
        print(f"  {json.dumps(r, ensure_ascii=False)[:250]}")
    except Exception as e:
        print(f"  异常 {e.__class__.__name__}")

    # 4. 测试点管理 AddTestPoints / GetAllZone / GetZonePoints (信息泄露+可能越权)
    print("\n=== [4] Run/GetAllZone 跑区枚举 ===")
    try:
        r = client.post("/v3/api.php/Run/GetAllZone", {})
        print(f"  {json.dumps(r, ensure_ascii=False)[:400]}")
    except Exception as e:
        print(f"  异常 {e.__class__.__name__}")

    print("\n=== [5] Run/runScore 分数 ===")
    for ps in [
        {},
        {"record_id": "513356"},
        {"term_id": "13286"},
    ]:
        try:
            r = client.post("/v3/api.php/Run/runScore", ps)
            print(f"  {ps}: {json.dumps(r, ensure_ascii=False)[:250]}")
        except Exception as e:
            print(f"  {ps}: 异常 {e.__class__.__name__}")

    print("\n[探测] 完成")


if __name__ == "__main__":
    main()
