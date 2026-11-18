# -*- coding: utf-8 -*-
"""系统探测 zfb 通道 + 状态修改接口的正确参数（只读/低危，不提交跑步记录）。"""
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
    uid = auth.uid
    now = int(time.time())

    # ============ 1. updateZfbStatus 参数爆破 ============
    print("=== [1] updateZfbStatus 参数爆破 ===")
    zfb_sets = [
        {"game_id": "2448", "start_time": str(now - 600)},
        {"game_id": "2448", "start_time": str(now - 600), "zfb_face_verify_id": "test123"},
        {"game_id": "2448", "start_time": str(now - 600), "status": "1", "type": "1"},
        {"game_id": "2448", "start_time": str(now - 600), "zfb_status": "1", "face_verify_status": "1"},
        {"game_id": "2448", "record_id": "514578", "status": "1"},
        {"game_id": "2448", "record_id": "514578", "zfb_face_verify_num": "1"},
        {"game_id": "2448", "start_time": str(now - 600), "is_timeout_zfb": "0"},
        {"type": "1", "game_id": "2448", "start_time": str(now - 600)},
    ]
    for ps in zfb_sets:
        try:
            r = client.post("/v3/api.php/Run2/updateZfbStatus", ps)
            info = str(r.get("info"))[:60]
            data = str(r.get("data"))[:100]
            st = r.get("status")
            if st != 0 or "参数" not in info:
                print(f"  ★ {json.dumps(ps, ensure_ascii=False)[:70]} -> status={st} info={info!r} data={data!r}")
            else:
                print(f"  {json.dumps(ps, ensure_ascii=False)[:70]} -> status={st} info={info!r}")
        except Exception as e:
            print(f"  {ps} 异常 {e.__class__.__name__}")

    # ============ 2. StatusToDel 参数爆破 ============
    print("\n=== [2] StatusToDel 参数爆破 ===")
    del_sets = [
        {"record_id": "514578", "point_id": "27989"},
        {"record_id": "514578", "point_id": "27989,27990,27991"},
        {"record_id": "514578", "point_ids": "27989,27990,27991"},
        {"record_id": "514578", "game_id": "2448", "point_id": "27989"},
        {"record_id": "514578", "point_id": "27989", "status": "1"},
        {"record_id": "514578", "checkpoint_id": "27989"},
    ]
    for ps in del_sets:
        try:
            r = client.post("/v3/api.php/Run/StatusToDel", ps)
            print(f"  {json.dumps(ps, ensure_ascii=False)[:70]} -> status={r.get('status')} info={str(r.get('info'))[:60]!r}")
        except Exception as e:
            print(f"  {ps} 异常 {e.__class__.__name__}")

    # ============ 3. uploadRunRecord 平行上传 ============
    print("\n=== [3] uploadRunRecord 平行上传 ===")
    for ps in [
        {"record_id": "514578"},
        {"record_id": "514578", "game_id": "2448"},
        {"record_id": "514578", "status": "1"},
        {"record_id": "514578", "point_ids": "27989,27990,27991"},
    ]:
        try:
            r = client.post("/v3/api.php/Run/uploadRunRecord", ps)
            print(f"  {json.dumps(ps, ensure_ascii=False)[:70]} -> status={r.get('status')} info={str(r.get('info'))[:60]!r}")
        except Exception as e:
            print(f"  {ps} 异常 {e.__class__.__name__}")

    # ============ 4. addRunComplain 申诉 ============
    print("\n=== [4] addRunComplain 申诉 ===")
    for ps in [
        {"record_id": "514578", "content": "打卡点正常,请求复核", "complain_type": "1"},
        {"record_id": "514578", "type": "1", "content": "复核"},
        {"record_id": "514578", "reason": "1", "content": "打卡点正常"},
        {"record_id": "514578", "complain_type": "2", "content": "抓拍已上传"},
    ]:
        try:
            r = client.post("/v3/api.php/Run/addRunComplain", ps)
            print(f"  {json.dumps(ps, ensure_ascii=False)[:70]} -> status={r.get('status')} info={str(r.get('info'))[:60]!r}")
        except Exception as e:
            print(f"  {ps} 异常 {e.__class__.__name__}")


if __name__ == "__main__":
    main()
