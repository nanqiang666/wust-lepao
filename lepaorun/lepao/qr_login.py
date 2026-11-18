# -*- coding: utf-8 -*-
# --- lepao-research-notice v1 (do not remove; see LICENSE) ---
# 乐跑协议研究（Lepao Research） · https://github.com/dan-cun/lepao3
# Copyright (c) 2026 dan-cun · 技术讨论 QQ 1224145544（仅作技术讨论，不提供代打卡）
# 许可证 LRL-1.0（乐跑研究协议 1.0）：仅供学习 · 不可牟利 · 再发布须署名引用原始仓库 · 声明不得删除
# 删除或篡改本块即依 LRL-1.0 第三条自动终止授权；衍生版须继续以 LRL-1.0 授权并标注修改说明。
# --- end lepao-research-notice ---
"""lepao.qr_login —— 步道乐跑官方 App 微信 / QQ 二维码扫码登录

依据:
  1. 官方 APK (com.lptiyu.tanke) ShareSDK.xml / classes.dex 实证参数:
     - QQ AppID: 1105660458
     - 微信 AppID: wx5a2e1ff396785475
  2. 微信开放平台官方 App SDK 扫码协议:
     - GET open.weixin.qq.com/connect/sdk/qrconnect -> uuid + qrcode (base64)
     - GET long.open.weixin.qq.com/connect/l/qrconnect?f=json&uuid=... -> wx_code
     - GET api.weixin.qq.com/sns/oauth2/access_token + /sns/userinfo -> openid/unionid
  3. QQ 互联官方扫码协议:
     - GET xui.ptlogin2.qq.com/cgi-bin/xlogin -> pt_login_sig
     - GET ssl.ptlogin2.qq.com/ptqrshow -> PNG 二维码 + qrsig
     - GET ssl.ptlogin2.qq.com/ptqrlogin -> 登录态 + pt_redirect
     - POST graph.qq.com/oauth2.0/authorize -> access_token -> /oauth2.0/me -> openid
"""
import base64
import datetime
import hashlib
import io
import json
import os
import re
import time
import urllib.parse
import uuid

import requests

# 官方 App 参数（来自 com.lptiyu.tanke 官方安装包，支持环境变量覆盖）
WX_APP_ID = os.environ.get("LEPAO_WX_APPID", "wx5a2e1ff396785475")
# 从公开开源工程 WeAuth 提取的客户端集成密钥（仅用于 sdk/qrconnect 官方出码演示）
WX_APP_SECRET = os.environ.get(
    "LEPAO_WX_SECRET",
    bytes(b ^ 0x55 for b in [
        54, 49, 55, 103, 101, 51, 100, 55, 48, 103, 49, 102, 54, 52, 54, 98,
        51, 97, 99, 99, 99, 97, 54, 98, 97, 103, 108, 102, 98, 52, 96, 97
    ]).decode("ascii"),
)
QQ_APP_ID = os.environ.get("LEPAO_QQ_APPID", "1105660458")

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_STATE_DIR = os.path.join(_ROOT, "state")
_CFG_PATH = os.path.join(_ROOT, "lepaorun", "config.json")
_SAMPLE_CFG = os.path.join(_ROOT, "lepaorun", "config.sample.json")
WX_CACHE_PATH = os.path.join(_STATE_DIR, "wechat_qr_cache.json")
OAUTH_SESSION_PATH = os.path.join(_STATE_DIR, "oauth_session.json")


def _session():
    s = requests.Session()
    s.trust_env = False  # 直连腾讯认证服务器，不依赖系统代理
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    })
    return s


def render_ascii_qr(url_or_text: str) -> str:
    """在终端打印清晰的 ASCII 二维码。"""
    try:
        import qrcode
        qr = qrcode.QRCode(border=1)
        qr.add_data(url_or_text)
        qr.make(fit=True)
        buf = io.StringIO()
        qr.print_ascii(out=buf, invert=True)
        return buf.getvalue()
    except Exception:
        return f"[QR URL] {url_or_text}"


def save_oauth_session(info: dict):
    os.makedirs(_STATE_DIR, exist_ok=True)
    data = {**info, "saved_at": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}
    with open(OAUTH_SESSION_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return OAUTH_SESSION_PATH


def load_oauth_session() -> dict:
    if os.path.isfile(OAUTH_SESSION_PATH):
        try:
            with open(OAUTH_SESSION_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


# ================================================================ 微信扫码登录
class WeChatQRLogin:
    """步道乐跑微信开放平台官方 App SDK 扫码登录"""

    def __init__(self, appid: str = WX_APP_ID, secret: str = WX_APP_SECRET):
        self.appid = appid
        self.secret = secret
        self.sess = _session()
        self.uuid = ""
        self.appname = ""
        self.qr_png_bytes = b""
        self.qr_url = ""

    def _get_sdk_ticket(self, force_refresh: bool = False) -> str:
        os.makedirs(_STATE_DIR, exist_ok=True)
        now = time.time()
        if not force_refresh and os.path.isfile(WX_CACHE_PATH):
            try:
                with open(WX_CACHE_PATH, encoding="utf-8") as cf:
                    cache = json.load(cf)
                if cache.get("appid") == self.appid and cache.get("expires_at", 0) > now + 120:
                    if cache.get("sdk_ticket"):
                        return cache["sdk_ticket"]
            except Exception:
                pass

        r1 = self.sess.get(
            "https://api.weixin.qq.com/cgi-bin/token",
            params={"grant_type": "client_credential", "appid": self.appid, "secret": self.secret},
            timeout=10,
        ).json()
        at = r1.get("access_token")
        if not at:
            raise RuntimeError(f"获取微信 access_token 失败: {r1}")

        r2 = self.sess.get(
            "https://api.weixin.qq.com/cgi-bin/ticket/getticket",
            params={"access_token": at, "type": "2"},
            timeout=10,
        ).json()
        ticket = r2.get("ticket")
        if not ticket:
            raise RuntimeError(f"获取微信 sdk_ticket 失败: {r2}")

        expires_in = int(r2.get("expires_in") or 7200)
        with open(WX_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "appid": self.appid,
                "access_token": at,
                "sdk_ticket": ticket,
                "expires_at": now + expires_in,
            }, f, ensure_ascii=False, indent=2)
        return ticket

    def create_qr(self, out_png: str = None) -> dict:
        """生成微信授权登录二维码，返回 {uuid, appname, qr_url, png_bytes, png_path}。"""
        ticket = self._get_sdk_ticket()
        noncestr = uuid.uuid4().hex[:16]
        ts = str(int(time.time()))
        raw = f"appid={self.appid}&noncestr={noncestr}&sdk_ticket={ticket}&timestamp={ts}"
        sig = hashlib.sha1(raw.encode("utf-8")).hexdigest()
        r = self.sess.get(
            "https://open.weixin.qq.com/connect/sdk/qrconnect",
            params={
                "appid": self.appid,
                "noncestr": noncestr,
                "timestamp": ts,
                "scope": "snsapi_userinfo",
                "signature": sig,
            },
            timeout=10,
        ).json()
        if r.get("errcode", -1) != 0:
            # ticket 失效则强刷一次重试
            ticket = self._get_sdk_ticket(force_refresh=True)
            raw = f"appid={self.appid}&noncestr={noncestr}&sdk_ticket={ticket}&timestamp={ts}"
            sig = hashlib.sha1(raw.encode("utf-8")).hexdigest()
            r = self.sess.get(
                "https://open.weixin.qq.com/connect/sdk/qrconnect",
                params={
                    "appid": self.appid,
                    "noncestr": noncestr,
                    "timestamp": ts,
                    "scope": "snsapi_userinfo",
                    "signature": sig,
                },
                timeout=10,
            ).json()
        if r.get("errcode", -1) != 0:
            raise RuntimeError(f"微信生成二维码失败: {r}")

        self.uuid = r["uuid"]
        self.appname = r.get("appname", "步道乐跑")
        qr_info = r.get("qrcode") or {}
        b64 = qr_info.get("qrcodebase64") or ""
        self.qr_png_bytes = base64.b64decode(b64) if b64 else b""
        self.qr_url = f"https://open.weixin.qq.com/connect/qrcode/{self.uuid}"

        png_path = out_png or os.path.join(_STATE_DIR, "qr_wechat.png")
        os.makedirs(os.path.dirname(png_path), exist_ok=True)
        if self.qr_png_bytes:
            with open(png_path, "wb") as f:
                f.write(self.qr_png_bytes)
        return {
            "provider": "wechat",
            "uuid": self.uuid,
            "appname": self.appname,
            "qr_url": self.qr_url,
            "png_bytes": self.qr_png_bytes,
            "png_path": png_path,
        }

    def poll_once(self, last_code: str = "") -> tuple:
        """单次轮询扫码状态。返回 (status, payload)
        status: 'waiting' | 'scanned' | 'confirmed' | 'cancelled' | 'expired' | 'error'
        """
        if not self.uuid:
            return "error", {"msg": "尚未生成二维码"}
        params = {"f": "json", "uuid": self.uuid, "_": str(int(time.time() * 1000))}
        if last_code:
            params["last"] = last_code
        try:
            r = self.sess.get(
                "https://long.open.weixin.qq.com/connect/l/qrconnect",
                params=params,
                timeout=30,
            )
            j = r.json()
        except Exception as e:
            return "waiting", {"detail": str(e)}

        ec = j.get("wx_errcode")
        if ec == 408:
            return "waiting", j
        if ec == 404:
            return "scanned", j
        if ec == 405:
            return "confirmed", j
        if ec == 403:
            return "cancelled", j
        if ec in (402, 500):
            return "expired", j
        return "waiting", j

    def exchange_code(self, wx_code: str) -> dict:
        """用微信扫码得到的 wx_code 换取 openid / unionid / userinfo。"""
        r = self.sess.get(
            "https://api.weixin.qq.com/sns/oauth2/access_token",
            params={
                "appid": self.appid,
                "secret": self.secret,
                "code": wx_code,
                "grant_type": "authorization_code",
            },
            timeout=10,
        ).json()
        if r.get("errcode"):
            raise RuntimeError(f"微信换取 token 失败: {r}")

        at = r.get("access_token", "")
        openid = r.get("openid", "")
        unionid = r.get("unionid", "")
        nickname = ""
        avatar = ""
        if at and openid:
            try:
                ui = self.sess.get(
                    "https://api.weixin.qq.com/sns/userinfo",
                    params={"access_token": at, "openid": openid, "lang": "zh_CN"},
                    timeout=10,
                ).json()
                nickname = ui.get("nickname", "")
                avatar = ui.get("headimgurl", "")
                unionid = unionid or ui.get("unionid", "")
            except Exception:
                pass

        res = {
            "provider": "wechat",
            "appid": self.appid,
            "code": wx_code,
            "access_token": at,
            "refresh_token": r.get("refresh_token", ""),
            "openid": openid,
            "unionid": unionid,
            "nickname": nickname,
            "avatar": avatar,
        }
        save_oauth_session(res)
        return res


# ================================================================ QQ 扫码登录
def _ptqrtoken(qrsig: str) -> int:
    e = 0
    for ch in qrsig:
        e += (e << 5) + ord(ch)
    return 2147483647 & e


def _qq_gtk(skey: str) -> int:
    h = 5381
    for ch in skey:
        h += (h << 5) + ord(ch)
    return h & 0x7FFFFFFF


class QQQRLogin:
    """步道乐跑 QQ 互联移动应用官方扫码登录 (AppID=1105660458, daid=381, openmobile.qq.com)"""

    def __init__(self, client_id: str = QQ_APP_ID):
        self.client_id = client_id
        self.sess = _session()
        self.sess.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 13; PLK110) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Version/4.0 Chrome/116.0.0.0 Mobile Safari/537.36"
            )
        })
        self.qrsig = ""
        self.pt_login_sig = ""
        self.xlogin_url = ""
        self.openlogin_data = ""
        self.h5sig = ""
        self.qr_png_bytes = b""

    def create_qr(self, out_png: str = None) -> dict:
        """通过 openmobile.qq.com/oauth2.0/m_authorize 初始化移动端互联会话 (daid=381) 并获取二维码。"""
        r0 = self.sess.get(
            "https://openmobile.qq.com/oauth2.0/m_authorize",
            params={
                "response_type": "token",
                "client_id": self.client_id,
                "redirect_uri": "auth://tauth.qq.com/",
                "scope": "all",
                "display": "mobile",
                "browser_error": "1",
                "fall_to_wv": "1",
                "qr_login": "1",
                "force_qr": "1",
            },
            timeout=10,
        )
        m_src = re.search(r'var\s+src\s*=\s*"([^"]+)"', r0.text)
        if m_src:
            base_xlogin = m_src.group(1).encode("utf-8").decode("unicode_escape")
            qs = base_xlogin.split("?", 1)[1] if "?" in base_xlogin else ""
            qdict = dict(urllib.parse.parse_qsl(qs))
            self.h5sig = qdict.get("h5sig", "")
            self.xlogin_url = f"{base_xlogin}&force_qr=1&qr_login=1"
            self.openlogin_data = (
                f"{qs}&openapi=1010_1011&pt_flex=1&loginfrom=&h5sig={self.h5sig}&loginty=1"
            )
        else:
            self.xlogin_url = (
                "https://xui.ptlogin2.qq.com/cgi-bin/xlogin"
                f"?appid=716027609&pt_3rd_aid={self.client_id}&daid=381"
                "&pt_skey_valid=0&style=35&s_url=http%3A%2F%2Fconnect.qq.com"
                "&refer_cgi=m_authorize&ucheck=1&fall_to_wv=1"
                "&redirect_uri=auth%3A%2F%2Ftauth.qq.com%2F&browser_error=1"
                f"&client_id={self.client_id}&response_type=token&scope=all"
                "&force_qr=1&qr_login=1"
            )
            self.openlogin_data = (
                f"appid=716027609&pt_3rd_aid={self.client_id}&daid=381"
                "&pt_skey_valid=0&style=35&s_url=http%3A%2F%2Fconnect.qq.com"
                "&refer_cgi=m_authorize&ucheck=1&fall_to_wv=1"
                "&redirect_uri=auth%3A%2F%2Ftauth.qq.com%2F&browser_error=1"
                f"&client_id={self.client_id}&response_type=token&scope=all"
                "&openapi=1010_1011&pt_flex=1"
            )

        r1 = self.sess.get(self.xlogin_url, timeout=10)
        if r1.status_code != 200:
            raise RuntimeError(f"QQ xlogin 初始化失败: HTTP {r1.status_code}")
        self.pt_login_sig = self.sess.cookies.get("pt_login_sig", "")

        r2 = self.sess.get(
            "https://ssl.ptlogin2.qq.com/ptqrshow",
            params={
                "s": "8",
                "e": "0",
                "appid": "716027609",
                "type": "0",
                "t": f"{time.time():.6f}",
                "u1": "http://connect.qq.com",
                "daid": "381",
                "pt_3rd_aid": self.client_id,
            },
            headers={"Referer": self.xlogin_url},
            timeout=10,
        )
        self.qrsig = self.sess.cookies.get("qrsig", "")
        if not r2.content.startswith(b"\x89PNG") or not self.qrsig:
            raise RuntimeError(f"QQ 二维码获取失败: len={len(r2.content)}")
        self.qr_png_bytes = r2.content

        png_path = out_png or os.path.join(_STATE_DIR, "qr_qq.png")
        os.makedirs(os.path.dirname(png_path), exist_ok=True)
        with open(png_path, "wb") as f:
            f.write(self.qr_png_bytes)

        return {
            "provider": "qq",
            "client_id": self.client_id,
            "qrsig": self.qrsig,
            "png_bytes": self.qr_png_bytes,
            "png_path": png_path,
        }

    def poll_once(self) -> tuple:
        """单次轮询 QQ 扫码状态 (daid=381)。返回 (status, payload)"""
        if not self.qrsig:
            return "error", {"msg": "尚未生成二维码"}
        r = self.sess.get(
            "https://ssl.ptlogin2.qq.com/ptqrlogin",
            params={
                "u1": "http://connect.qq.com",
                "from_ui": "1",
                "type": "1",
                "ptlang": "2052",
                "ptqrtoken": str(_ptqrtoken(self.qrsig)),
                "daid": "381",
                "aid": "716027609",
                "pt_3rd_aid": self.client_id,
                "pt_openlogin_data": self.openlogin_data,
                "device": "2",
                "ptopt": "1",
                "pt_uistyle": "35",
            },
            headers={"Referer": self.xlogin_url or "https://xui.ptlogin2.qq.com/"},
            timeout=15,
        )
        m = re.search(r"ptuiCB\((.*)\)", r.text)
        if not m:
            return "waiting", {"raw": r.text[:120]}
        parts = [p.strip().strip("'\"") for p in m.group(1).split(",")]
        code = parts[0] if parts else ""
        if code == "66":
            return "waiting", {"msg": "等待扫码"}
        if code == "67":
            return "scanned", {"msg": "已扫码，请在手机 QQ 上确认"}
        if code in ("65", "68"):
            return "expired", {"msg": "二维码已失效"}
        if code == "0":
            jump_url = parts[2] if len(parts) > 2 else ""
            nick = parts[5] if len(parts) > 5 else ""
            return "confirmed", {"jump_url": jump_url, "nickname": nick}
        return "error", {"code": code, "parts": parts}

    def exchange_oauth(self, jump_url: str, nickname: str = "") -> dict:
        """完成 QQ 移动应用 OAuth2 (daid=381) 授权并获取 openid / access_token。"""
        at = ""
        openid = ""
        collected = jump_url or ""

        # 逐跳跟踪 jump_url，避免重定向到 auth://tauth.qq.com/?#access_token=... 时触发 InvalidSchema
        cur_url = jump_url
        for _ in range(8):
            if not cur_url or not cur_url.startswith(("http://", "https://")):
                break
            r_hop = self.sess.get(cur_url, timeout=10, allow_redirects=False)
            loc = r_hop.headers.get("Location", "")
            collected += "\n" + loc + "\n" + r_hop.text
            m_at = re.search(r"access_token=([A-Za-z0-9_-]+)", collected)
            m_oid = re.search(r'openid["\']?\s*[:=]\s*["\']?([0-9A-Fa-f]{16,64})', collected)
            if m_at:
                at = m_at.group(1)
            if m_oid:
                openid = m_oid.group(1)
            if at and openid:
                break
            if loc:
                cur_url = urllib.parse.urljoin(cur_url, loc)
            else:
                break

        if not at:
            p_skey = (
                self.sess.cookies.get("p_skey")
                or self.sess.cookies.get("skey")
                or self.sess.cookies.get("superkey")
                or ""
            )
            gtk = _qq_gtk(p_skey)
            for auth_url in (
                "https://openmobile.qq.com/oauth2.0/m_authorize",
                "https://graph.qq.com/oauth2.0/authorize",
            ):
                r = self.sess.post(
                    auth_url,
                    data={
                        "response_type": "token",
                        "client_id": self.client_id,
                        "redirect_uri": "auth://tauth.qq.com/",
                        "scope": "all",
                        "status_os": "13",
                        "status_machine": "PLK110",
                        "status_version": "13",
                        "sdkv": "3.5.12.lite",
                        "sdkp": "a",
                        "g_tk": str(gtk),
                        "from_ptlogin": "1",
                        "src": "1",
                        "update_auth": "1",
                        "openapi": "1010_1011",
                    },
                    allow_redirects=False,
                    timeout=10,
                )
                blob = r.headers.get("Location", "") + "\n" + r.text
                m_at = re.search(r"access_token=([A-Za-z0-9_-]+)", blob)
                if m_at:
                    at = m_at.group(1)
                    m_oid = re.search(r'openid["\']?\s*[:=]\s*["\']?([0-9A-Fa-f]{16,64})', blob)
                    if m_oid:
                        openid = m_oid.group(1)
                    break

        unionid = ""
        avatar = ""
        if at:
            r_me = self.sess.get(
                "https://graph.qq.com/oauth2.0/me",
                params={"access_token": at, "unionid": "1"},
                timeout=10,
            ).text
            m_oid = re.search(r'"openid"\s*:\s*"([^"]+)"', r_me)
            if m_oid:
                openid = m_oid.group(1)
            m_uid = re.search(r'"unionid"\s*:\s*"([^"]+)"', r_me)
            if m_uid:
                unionid = m_uid.group(1)
            if openid:
                try:
                    ui = self.sess.get(
                        "https://graph.qq.com/user/get_simple_userinfo",
                        params={"access_token": at, "oauth_consumer_key": self.client_id, "openid": openid},
                        timeout=10,
                    ).json()
                    nickname = ui.get("nickname") or nickname
                    avatar = ui.get("figureurl_qq_2") or ui.get("figureurl_qq_1") or ""
                except Exception:
                    avatar = ""

        res = {
            "provider": "qq",
            "appid": self.client_id,
            "access_token": at,
            "openid": openid,
            "unionid": unionid,
            "nickname": nickname,
            "avatar": avatar,
            "has_qq_oauth": bool(at and openid),
        }
        save_oauth_session(res)
        return res


# ================================================================ 脱机兑换 (Login/quickLoginV339)
def refresh_wechat_oauth(oauth_info: dict = None) -> dict:
    """使用微信 OAuth refresh_token 刷新微信 access_token（有效期 30 天）。"""
    info = dict(oauth_info or load_oauth_session())
    rt = info.get("refresh_token") or ""
    appid = info.get("appid") or WX_APP_ID
    if not rt:
        return info
    s = _session()
    r = s.get(
        "https://api.weixin.qq.com/sns/oauth2/refresh_token",
        params={"appid": appid, "grant_type": "refresh_token", "refresh_token": rt},
        timeout=10,
    ).json()
    if r.get("access_token"):
        info["access_token"] = r["access_token"]
        info["refresh_token"] = r.get("refresh_token") or rt
        info["openid"] = r.get("openid") or info.get("openid", "")
        save_oauth_session(info)
    return info


def exchange_lepao_token(
    oauth_info: dict = None,
    sync_config: bool = True,
    host: str = "api2.lptiyu.com",
    mobile_model: str = "PLK110",
    mobile_device_id: str = "00000000-6d3f-2934-ffff-ffffef05ac4a",
    mobile_os_version: str = "16",
) -> dict:
    """将微信/QQ 扫码获得的 OAuth 凭据 (openid + access_token) 脱机兑换为步道乐跑在线 token，
    自动补全学号/UID/学校ID 并写入 lepaorun/config.json（全程无需手机/模拟器/抓包）。
    """
    from .crypto import build_quick_login_key, decrypt_data
    from .v3api import V3Client

    info = dict(oauth_info or load_oauth_session())
    openid = str(info.get("openid") or "").strip()
    at = str(info.get("access_token") or "").strip()
    if not openid or not at:
        raise RuntimeError("缺少 openid 或 access_token，请先完成微信/QQ 扫码授权")

    provider = str(info.get("provider") or "wechat").lower()
    login_type = 2 if provider == "qq" else 3
    nickname = str(info.get("nickname") or "")
    avatar = str(info.get("avatar") or "")

    s = _session()

    def _call_quick_login(cur_at: str) -> dict:
        key_b64, _ = build_quick_login_key(
            openid=openid,
            access_token=cur_at,
            login_type=login_type,
            nickname=nickname,
            avatar_url=avatar,
            school_id=0,
            mobile_model=mobile_model,
            mobile_device_id=mobile_device_id,
            mobile_os_version=mobile_os_version,
        )
        resp = s.post(
            f"https://{host}/v3/api.php/Login/quickLoginV339",
            data={"key": key_b64},
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": f"Dalvik/2.1.0 (Linux; U; Android {mobile_os_version}; {mobile_model})",
                "Connection": "close",
            },
            timeout=15,
        )
        rj = resp.json()
        if rj.get("is_encrypt") == 1 and isinstance(rj.get("data"), str) and rj["data"]:
            rj["decrypted_data"] = json.loads(decrypt_data(rj["data"]))
        return rj

    rj = _call_quick_login(at)
    if rj.get("status") != 1 and provider == "wechat" and info.get("refresh_token"):
        info = refresh_wechat_oauth(info)
        if info.get("access_token") and info["access_token"] != at:
            at = info["access_token"]
            rj = _call_quick_login(at)

    if rj.get("status") != 1 or not isinstance(rj.get("decrypted_data"), dict):
        raise RuntimeError(f"Login/quickLoginV339 兑换失败: status={rj.get('status')} info={rj.get('info')}")

    lp_data = rj["decrypted_data"]
    uid = int(lp_data.get("uid") or 0)
    lp_token = str(lp_data.get("access_token") or "")
    lp_refresh = str(lp_data.get("refresh_token") or "")
    lp_refresh_exp = int(lp_data.get("refresh_expire") or 0)
    real_name = str(lp_data.get("name") or nickname or uid)

    if not uid or not lp_token:
        raise RuntimeError(f"Login/quickLoginV339 响应缺少 uid/access_token: {lp_data}")

    # 调用 App 端 User/User 与 beforeRunV260 补全学号、学校 ID、性别等真实档案
    c_app = V3Client(uid=uid, token=lp_token, school_id=61, host=host)
    u_info = {}
    try:
        u_res = c_app.post_app(
            "/v3/api.php/User/User",
            {},
            mobile_model=mobile_model,
            mobile_device_id=mobile_device_id,
            mobile_os_version=mobile_os_version,
        )
        if isinstance(u_res, dict):
            u_info = u_res
    except Exception:
        pass

    student_num = str(u_info.get("student_num") or lp_data.get("student_num") or uid)
    real_name = str(u_info.get("name") or real_name)
    sex_str = str(u_info.get("sex") or "")
    gender = "female" if "女" in sex_str else "male"
    school_name = str(u_info.get("school_name") or "武汉科技大学")
    school_id = int(u_info.get("school_id") or (61 if "武汉科技" in school_name else 0) or 61)

    c_v3 = V3Client(
        uid=uid,
        token=lp_token,
        school_id=school_id,
        student_num=student_num,
        card_id=student_num,
        host=host,
    )
    term_id = 0
    zone_name = ""
    try:
        br = c_v3.before_run()
        if isinstance(br, dict) and br.get("school_id"):
            school_id = int(br["school_id"])
            school_name = str(br.get("school_name") or school_name)
            term_id = int(br.get("term_id") or 0)
            zone_name = str(br.get("run_zone_name") or "")
    except Exception:
        pass

    lepao_bundle = {
        "uid": uid,
        "token": lp_token,
        "refresh_token": lp_refresh,
        "refresh_expire": lp_refresh_exp,
        "student_num": student_num,
        "card_id": student_num,
        "name": real_name,
        "gender": gender,
        "school_id": school_id,
        "school_name": school_name,
        "term_id": term_id,
        "run_zone_name": zone_name,
        "exchanged_at": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    }
    info["lepao"] = lepao_bundle
    save_oauth_session(info)

    if sync_config:
        cfg = (
            json.load(open(_CFG_PATH, encoding="utf-8-sig"))
            if os.path.isfile(_CFG_PATH)
            else json.load(open(_SAMPLE_CFG, encoding="utf-8"))
        )
        accs = cfg.setdefault("accounts", {})
        old_pol = (accs.get(student_num) or {}).get("policy") or {}
        accs[student_num] = {
            "uid": uid,
            "school_id": school_id,
            "student_num": student_num,
            "card_id": student_num,
            "name": real_name,
            "alias": real_name,
            "enabled": True,
            "policy": {**old_pol, "gender": gender, "mobile_model": mobile_model},
            "auth": {
                "token": lp_token,
                "refresh_token": lp_refresh,
                "refresh_expire": lp_refresh_exp,
                "issued_at": lepao_bundle["exchanged_at"],
                "source": f"qr_{provider}_quickLoginV339",
                "consumed_at": "",
            },
        }
        # 清理旧的未认证占位槽位（如 school_id=0 的旧记录）
        for k in list(accs.keys()):
            if k != student_num and (accs[k].get("uid") == uid or accs[k].get("school_id") == 0):
                accs.pop(k, None)
        cfg["active"] = student_num
        with open(_CFG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)

    return lepao_bundle
