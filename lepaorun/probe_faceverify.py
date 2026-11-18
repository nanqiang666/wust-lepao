# -*- coding: utf-8 -*-
"""探测 Run2/faceVerify 接口的正确参数(人脸验证/抓拍)。
只读探测, 尝试多种参数组合。"""
import os
import sys

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

    print(f"[faceVerify 探测] uid={auth.uid}")

    # 尝试多种参数组合
    param_sets = [
        {},  # 空参数(基线)
        {"type": "1"},
        {"face_img": ""},
        {"img": ""},
        {"face_file": ""},
        {"photo": ""},
        {"verify_type": "1"},
        {"face_type": "1"},
        {"record_id": "0"},
    ]
    for params in param_sets:
        try:
            resp = client.post("/v3/api.php/Run2/faceVerify", params)
            if isinstance(resp, dict):
                print(f"  参数 {params}: status={resp.get('status')} info={str(resp.get('info'))[:60]!r}")
            else:
                print(f"  参数 {params}: 非JSON {str(resp)[:60]}")
        except Exception as e:
            print(f"  参数 {params}: 异常 {e.__class__.__name__}")

    print("[faceVerify 探测] 完成")


if __name__ == "__main__":
    main()
