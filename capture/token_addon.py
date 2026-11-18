# -*- coding: utf-8 -*-
"""mitmproxy addon: 拦截步道乐跑 (lptiyu.com / zhty.wust.edu.cn) 流量，自动解密提取 token。

支持:
  - 小程序 ostype=5 (POST body data=<AES>)
  - Android App (响应 data=<AES> 或登录响应 JSON，请求 key=<AES>)
  - 捕获后同时写入临时文件 lepao_captured_token.json 与 lepaorun/config.json（若已有账号槽位则更新）
"""
import base64
import datetime
import json
import os
import tempfile
import urllib.parse as up

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

KEY = b"Wet2C8d34f62ndi3"
IV = b"K6iv85jBD8jgf32D"
APP_KEY = b"goMEzJ1pDpncNHb9"
APP_IV = b"ZUrAS2lUidjyY2gK"
TOKEN_FILE = os.path.join(tempfile.gettempdir(), "lepao_captured_token.json")
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_CFG_PATH = os.path.join(_ROOT, "lepaorun", "config.json")

TARGET_HOSTS = ("lptiyu.com", "zhty.wust.edu.cn")


def dec(b64_text, field="data"):
    raw = base64.b64decode(b64_text)
    pairs = [(APP_KEY, APP_IV), (KEY, IV)] if field == "key" else [(KEY, IV), (APP_KEY, APP_IV)]
    for k, iv in pairs:
        try:
            return json.loads(unpad(AES.new(k, AES.MODE_CBC, iv).decrypt(raw), 16).decode("utf-8"))
        except Exception:
            continue
    raise ValueError("unable to decrypt payload")


class TokenCapture:
    def __init__(self):
        self.last_token = ""

    def response(self, flow):
        url = flow.request.pretty_url
        if not any(h in url for h in TARGET_HOSTS):
            return
        # 1) 优先从请求体提取（data=<AES> 或 key=<AES>）
        try:
            body = flow.request.get_text(strict=False) or ""
            for field in ("data", "key"):
                if f"{field}=" in body:
                    part = body.split(f"{field}=", 1)[1].split("&", 1)[0]
                    plain = dec(up.unquote(part), field=field)
                    tok = str(plain.get("token") or "")
                    uid = plain.get("uid") or 0
                    sid = plain.get("school_id") or 0
                    sn = str(plain.get("student_num") or "")
                    if tok and len(tok) >= 16:
                        self._emit(tok, uid, sid, sn, url, "request")
                        return
        except Exception:
            pass

        # 2) 从响应体解密提取 token（登录响应）
        try:
            resp_txt = flow.response.get_text(strict=False) or ""
            j = json.loads(resp_txt)
            if isinstance(j.get("data"), str) and len(j["data"]) > 32:
                plain = dec(j["data"])
            elif isinstance(j.get("data"), dict):
                plain = j["data"]
            else:
                plain = j
            if isinstance(plain, dict):
                tok = str(plain.get("token") or plain.get("access_token") or "")
                uid = plain.get("uid") or 0
                sid = plain.get("school_id") or 0
                sn = str(plain.get("student_num") or "")
                if tok and len(tok) >= 16:
                    self._emit(tok, uid, sid, sn, url, "response")
        except Exception:
            pass

    def _emit(self, token, uid, school_id, student_num, url, src):
        if token == self.last_token:
            return
        self.last_token = token
        now_str = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        data = {
            "token": token,
            "uid": uid,
            "school_id": school_id,
            "student_num": student_num,
            "url": url,
            "source": src,
            "captured_at": now_str,
        }
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[TOKEN_CAPTURED] {token[:10]}… uid={uid} school={school_id} sn={student_num} ({src})", flush=True)
        self._sync_to_config(data)

    @staticmethod
    def _sync_to_config(data):
        try:
            if not os.path.isfile(_CFG_PATH):
                sample = os.path.join(_ROOT, "lepaorun", "config.sample.json")
                if os.path.isfile(sample):
                    cfg = json.load(open(sample, encoding="utf-8"))
                else:
                    return
            else:
                cfg = json.load(open(_CFG_PATH, encoding="utf-8-sig"))
            sn = str(data.get("student_num") or data.get("uid") or "wust_user")
            accounts = cfg.setdefault("accounts", {})
            acc = accounts.setdefault(sn, {
                "uid": data.get("uid") or 0,
                "school_id": data.get("school_id") or 0,
                "student_num": sn,
                "card_id": sn,
                "name": sn,
                "alias": sn,
                "enabled": True,
                "policy": {},
                "auth": {},
            })
            if data.get("uid"):
                acc["uid"] = int(data["uid"])
            if data.get("school_id"):
                acc["school_id"] = int(data["school_id"])
            acc.setdefault("auth", {})["token"] = data["token"]
            acc["auth"]["issued_at"] = data["captured_at"]
            acc["auth"]["source"] = f"mitm_{data['source']}"
            acc["auth"]["consumed_at"] = ""
            if not cfg.get("active"):
                cfg["active"] = sn
            with open(_CFG_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[warn] sync config failed: {e}", flush=True)


addons = [TokenCapture()]
