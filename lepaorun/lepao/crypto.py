# -*- coding: utf-8 -*-
# --- lepao-research-notice v1 (do not remove; see LICENSE) ---
# 乐跑协议研究（Lepao Research） · https://github.com/dan-cun/lepao3
# Copyright (c) 2026 dan-cun · 技术讨论 QQ 1224145544（仅作技术讨论，不提供代打卡）
# 许可证 LRL-1.0（乐跑研究协议 1.0）：仅供学习 · 不可牟利 · 再发布须署名引用原始仓库 · 声明不得删除
# 删除或篡改本块即依 LRL-1.0 第三条自动终止授权；衍生版须继续以 LRL-1.0 授权并标注修改说明。
# --- end lepao-research-notice ---
# Copyright (c) 2026 dan-cun · 许可协议见项目根目录 LICENSE
"""lepao.crypto —— 乐跑协议核心算法（AES-128-CBC + SignMD5）

算法来源: 小程序 wxapkg 反编译（乐跑/逆向分析.md），2026-09-07 安卓真机抓包逐字节验证。
"""
import base64
import hashlib
import random

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

AES_KEY = b"Wet2C8d34f62ndi3"
AES_IV = b"K6iv85jBD8jgf32D"
APP_AES_KEY = b"goMEzJ1pDpncNHb9"
APP_AES_IV = b"ZUrAS2lUidjyY2gK"
SIGN_KEY = "rDJiNB9j7vD2"
SIGN_KEY_NEW = "eFoqdHOdDy6ViJ0i"
DEFAULT_UMID = "4x7y0z3a6b9c2d5e8f1g4h7i0j3k6l9m"

# App v4.3.x (Lo9/c;->a9) 生产环境 type="1" 动态密钥表 (按 int(nonce) % 10 索引)
A9_KEYS = (
    ("R7gT3pL9sF2kD5mQ", "B8jN4wH6xJ2vK7rE"),
    ("M5dS8fG3hJ7kL2pR", "C9tY6rU3eW4qX8sZ"),
    ("P2bN7vF4cD9mK6jA", "S3nH5gJ8dL2fT9wQ"),
    ("X6rV9tB3yG5hN7kP", "E4sW2qA8dZ6fC3jM"),
    ("K8jD3mF7nH2pL5rT", "Q6wS4eX9cV2bN7gJ"),
    ("F3dG7hJ2kL5pM8rN", "Z9xC4vB6nA2sD7fH"),
    ("B5vN8cM3xZ6dF2gJ", "H7kL4jP9mQ2rT5sW"),
    ("N6mK3lJ7pO2iU5yT", "G8hF4dS2fA6gH9jK"),
    ("V2bC7nM3vX6cZ9dF", "J5kL8jH3gD7fS2dA"),
    ("H9jG4fD7sA2dF5gH", "K3lJ6pO9iU2yT5rE"),
)

# App v4.3.x (Lo9/c;->c9) 生产环境 type="2" 动态密钥表 (按 int(timestamp) % 15 索引)
C9_KEYS = (
    ("L3xP7kQ2fD9sH5jR", "N8wB4mG6vK2rT9cE"),
    ("Z5tF8gS3dA7hJ2pQ", "Y6rU3eW9qX4sC8vB"),
    ("Q2mK7jP3nL5iO9uY", "W4sE8qR2tT5yU3iO"),
    ("D9fG3hJ7kL2pM5rN", "B6vC8nX3mZ5dF7gH"),
    ("P7bN2vF9cD4mK6jA", "S3hG5jJ8dL7fT2wQ"),
    ("H5jG8fD3sA6dF9gH", "K7lJ2pO5iU8yT3rE"),
    ("X8rV3tB6yG9hN4kP", "E2sW5qA3dZ7fC8jM"),
    ("M3dS5fG8hJ2kL7pR", "C4tY9rU6eW3qX5sZ"),
    ("F6dG2hJ5kL8pM3rN", "Z7xC5vB3nA9sD2fH"),
    ("V5bC3nM8vX4cZ6dF", "J9kL2jH5gD3fS7dA"),
    ("B8vN5cM2xZ9dF3gJ", "H4kL7jP2mQ5rT8sW"),
    ("N3mK6lJ8pO5iU2yT", "G5hF7dS9fA3gH4jK"),
    ("T6rE2yU5iO8pJ3lK", "J7kH3gF5dS8aQ2wE"),
    ("W9qE3sA6dF5gH7jK", "R5tY2eU7iO8pJ3lK"),
    ("S4dF8aQ3wE6rT5yU", "I2uO5pJ8lK3jH7gF"),
)


def encrypt_data(plaintext: str) -> str:
    """AES-128-CBC + PKCS7 → base64"""
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    ct = cipher.encrypt(pad(plaintext.encode("utf-8"), 16))
    return base64.b64encode(ct).decode()


def decrypt_data(data_b64: str) -> str:
    """base64 → AES-128-CBC 解密 → UTF-8 明文"""
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    pt = unpad(cipher.decrypt(base64.b64decode(data_b64)), 16)
    return pt.decode("utf-8")


def encrypt_app_key(plaintext: str) -> str:
    """App v4.3.x key= 参数加密 (goMEzJ1pDpncNHb9 / ZUrAS2lUidjyY2gK)"""
    cipher = AES.new(APP_AES_KEY, AES.MODE_CBC, APP_AES_IV)
    return base64.b64encode(cipher.encrypt(pad(plaintext.encode("utf-8"), 16))).decode()


def decrypt_app_key(data_b64: str) -> str:
    """App v4.3.x key= 参数解密"""
    cipher = AES.new(APP_AES_KEY, AES.MODE_CBC, APP_AES_IV)
    return unpad(cipher.decrypt(base64.b64decode(data_b64)), 16).decode("utf-8")


def sign_md5(params: dict, secret: str = SIGN_KEY) -> str:
    """SignMD5: 按键升序拼接 k+v, 末尾拼 secret, 整体 MD5"""
    concat = "".join(f"{k}{params[k]}" for k in sorted(params.keys()))
    return hashlib.md5((concat + secret).encode("utf-8")).hexdigest()


def aes_cbc_android_b64(key: str, iv: str, plaintext: str) -> str:
    """与 Android Base64.encode(bytes, Base64.DEFAULT=0) 完全对齐的 AES-CBC 加密（76 字符换行 + 末尾 \\n）"""
    cipher = AES.new(key.encode("utf-8"), AES.MODE_CBC, iv.encode("utf-8"))
    ct = cipher.encrypt(pad(plaintext.encode("utf-8"), 16))
    return base64.encodebytes(ct).decode("utf-8")


def sign_md5_encrypt_new(params: dict, is_login_v339: bool = False, secret: str = SIGN_KEY_NEW) -> str:
    """App v4.3.x isEncryptNew 签名算法 (Lea/k;->f):
    - secret 置于最前（而非末尾）
    - mobileDeviceId 不参与签名
    - is_login_v339=True 时 nick_name 与 avatar_url 不参与签名
    """
    skip = {"sign", "mobileDeviceId", "nick_name", "avatar_url"} if is_login_v339 else {"sign", "mobileDeviceId"}
    parts = [secret]
    for k in sorted(params.keys()):
        if k in skip:
            continue
        parts.append(f"{k}{params[k]}")
    return hashlib.md5("".join(parts).encode("utf-8")).hexdigest()


def build_quick_login_key(
    openid: str,
    access_token: str,
    login_type: int = 3,
    nickname: str = "",
    avatar_url: str = "",
    school_id: int = 0,
    timestamp: int = None,
    nonce: str = None,
    mobile_model: str = "PLK110",
    mobile_device_id: str = "00000000-6d3f-2934-ffff-ffffef05ac4a",
    mobile_os_version: str = "16",
    version: str = "231",
    version_name: str = "4.3.1",
    umid: str = DEFAULT_UMID,
) -> tuple:
    """构造 Login/quickLoginV339 脱机兑换请求的 (key_cipher_b64, plain_params_dict)。"""
    import json
    import time as _time

    ts_str = str(int(timestamp if timestamp is not None else _time.time()))
    nonce_str = str(nonce or random6())

    k1, iv1 = A9_KEYS[int(nonce_str) % 10]
    enc_openid = aes_cbc_android_b64(k1, iv1, openid)
    enc_token = aes_cbc_android_b64(k1, iv1, access_token)

    dyn_key = "lp" + mobile_model[1:2].lower() + ts_str[3:4]
    k2, iv2 = C9_KEYS[int(ts_str) % 15]
    ts_md5 = hashlib.md5(ts_str.encode("utf-8")).hexdigest()
    dyn_val = aes_cbc_android_b64(k2, iv2, umid + ts_md5)

    params = {
        "version": str(version),
        "version_name": str(version_name),
        "mobileModel": mobile_model,
        "mobileDeviceId": mobile_device_id,
        "mobileOsVersion": str(mobile_os_version),
        "ostype": "1",
        "school_id": str(school_id),
        "uid": "0",
        "timestamp": ts_str,
        "nonce": nonce_str,
        "openid": enc_openid,
        "accesstoken": enc_token,
        "type": str(login_type),
        "avatar_url": avatar_url or "",
        "nick_name": nickname or "",
        dyn_key: dyn_val,
    }
    params["sign"] = sign_md5_encrypt_new(params, is_login_v339=True)
    json_str = json.dumps(params, ensure_ascii=False, separators=(",", ":"))
    key_b64 = aes_cbc_android_b64(APP_AES_KEY.decode("ascii"), APP_AES_IV.decode("ascii"), json_str)
    return key_b64, params


def random6() -> str:
    """6 位随机数字（与小程序 random6 一致）"""
    return str(int(1e6 * random.random()) + 1e6)[1:7]
