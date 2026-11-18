# -*- coding: utf-8 -*-
"""探测可能的抓拍接口名(只读, 不提交)。
方法存在 → 返回 JSON(status=1/0); 方法不存在 → 返回 32KB TP 错误页(非JSON)。
用法: py -3 probe_capture_api.py [--member 学号]
"""
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
os.environ.setdefault("LEPAO2_CONFIG", os.path.join(BASE, "config.json"))

from lepao.accounts import AccountRegistry
from lepao.auth import AuthState

# 候选抓拍接口(Module/method), 按命名规律猜测
CANDIDATES = [
    "Run2/capture", "Run2/uploadCapture", "Run2/capturePhoto",
    "Run2/checkCapture", "Run2/saveCapture", "Run2/capturePoint",
    "Run/capture", "Run/uploadCapture", "Run/capturePhoto",
    "Run/checkCapture", "Run/saveCapture", "Run/capturePoint",
    "WpRun/capture", "WpRun/uploadCapture", "WpRun/capturePhoto",
    "Run2/screenshot", "Run2/photo", "Run2/captureImg",
    "Run2/uploadImg", "Run2/saveImg", "Run2/captureLog",
    "Run2/faceVerify", "Run2/captureVerify", "Run2/uploadPhoto",
]


def main():
    sel = None
    if "--member" in sys.argv:
        sel = sys.argv[sys.argv.index("--member") + 1]
    reg = AccountRegistry(os.path.join(BASE, "config.json"))
    key = reg.resolve(sel)
    auth = AuthState(reg, key)
    client = auth.make_client(pace=0.3)

    print(f"[探测] 成员 {auth.label} uid={auth.uid} token={auth.token[:8]}…")
    for c in CANDIDATES:
        path = f"/v3/api.php/{c}"
        try:
            resp = client.post(path, {})
        except Exception as e:
            print(f"  [{c}] 异常: {e.__class__.__name__} {str(e)[:60]}")
            continue
        if isinstance(resp, dict):
            st = resp.get("status")
            info = str(resp.get("info") or "")[:40]
            print(f"  [{c}] JSON status={st} info={info!r}")
        else:
            s = str(resp)
            print(f"  [{c}] 非JSON(方法不存在?) len={len(s)} 头={s[:40]!r}")
    print("[探测] 完成")


if __name__ == "__main__":
    main()
