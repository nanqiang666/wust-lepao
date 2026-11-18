# -*- coding: utf-8 -*-
"""验证 App token 走 ostype=1 (App 协议) 的可用性，确认 client_type 判定依据。
只读探测，不提交。"""
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
os.environ.setdefault("LEPAO2_CONFIG", os.path.join(BASE, "config.json"))

from lepao.accounts import AccountRegistry
from lepao.auth import AuthState
from lepao.v3api import V3Client


def main():
    reg = AccountRegistry(os.path.join(BASE, "config.json"))
    auth = AuthState(reg, reg.resolve())
    uid = auth.uid
    token = auth.token
    print(f"[验证] uid={uid} token={token[:8]}…")

    # 用 ostype=1 平面签名 (post_app) 调 beforeRun
    client = V3Client(uid=uid, token=token, school_id=auth.school_id,
                      student_num=auth.student_num, card_id=auth.card_id,
                      host="api2.lptiyu.com")
    print("\n=== [1] ostype=1 App 协议 beforeRunV260 ===")
    r = client.post_app("/v3/api.php/Run2/beforeRunV260", {})
    print(json.dumps(r, ensure_ascii=False)[:800])

    print("\n=== [2] ostype=1 App 协议 getTermList ===")
    r2 = client.post_app("/v3/api.php/WpRun/getTermList", {})
    print(json.dumps(r2, ensure_ascii=False)[:500])


if __name__ == "__main__":
    main()
