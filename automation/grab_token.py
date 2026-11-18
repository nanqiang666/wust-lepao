# -*- coding: utf-8 -*-
"""从 mitm 抓包文件 (.mitm) 里解密提取乐跑 token（支持 api2.lptiyu.com 与 zhty.wust.edu.cn）。

用法: python automation/grab_token.py [flows.mitm ...]
"""
import glob
import json
import os
import sys
from urllib.parse import parse_qs, unquote

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_ROOT, "lepaorun"))

from lepao.crypto import decrypt_app_key, decrypt_data  # noqa: E402

TARGETS = ("lptiyu.com", "zhty.wust.edu.cn")


def try_decrypt(text):
    try:
        obj = json.loads(text)
    except Exception:
        return None
    if isinstance(obj, dict) and obj.get("is_encrypt") and obj.get("data"):
        try:
            return json.loads(decrypt_data(obj["data"]))
        except Exception:
            return None
    return obj


def scan(path):
    from mitmproxy.io import FlowReader

    out = []
    with open(path, "rb") as f:
        for flow in FlowReader(f).stream():
            req = getattr(flow, "request", None)
            if not req or not any(t in req.host for t in TARGETS):
                continue
            raw = req.get_text(strict=False) or ""
            for field in ("data", "key"):
                if f"{field}=" in raw:
                    try:
                        q = parse_qs(raw)
                        val = unquote(q[field][0])
                        try:
                            plain = decrypt_app_key(val) if field == "key" else decrypt_data(val)
                        except Exception:
                            plain = decrypt_data(val) if field == "key" else decrypt_app_key(val)
                        body = json.loads(plain)
                        if body.get("token"):
                            out.append({
                                "ts": req.timestamp_start,
                                "endpoint": req.path.split("v3/api.php/")[-1],
                                "token": body["token"],
                                "uid": body.get("uid"),
                                "school_id": body.get("school_id"),
                                "student_num": body.get("student_num"),
                                "src": f"request.{field}",
                            })
                            break
                    except Exception:
                        pass
            resp = getattr(flow, "response", None)
            if not resp:
                continue
            body = try_decrypt(resp.get_text(strict=False) or "")
            if not isinstance(body, dict):
                continue
            tok = body.get("token") or body.get("access_token")
            if not tok:
                continue
            out.append({
                "ts": req.timestamp_start,
                "endpoint": req.path.split("v3/api.php/")[-1],
                "token": tok,
                "uid": body.get("uid") or (body.get("user_info") or {}).get("uid"),
                "school_id": body.get("school_id"),
                "student_num": body.get("student_num") or body.get("card_id"),
                "src": "response",
            })
    return out


if __name__ == "__main__":
    paths = sys.argv[1:] or sorted(glob.glob(os.path.join(_ROOT, "flows", "*.mitm")))
    found = []
    for p in paths:
        try:
            found += scan(p)
        except Exception as e:
            print(f"[warn] {p}: {e}", file=sys.stderr)
    found.sort(key=lambda r: r["ts"] or 0)
    for r in found:
        print(json.dumps(r, ensure_ascii=False))
    if not found:
        print("NO_TOKEN", file=sys.stderr)
        sys.exit(2)
