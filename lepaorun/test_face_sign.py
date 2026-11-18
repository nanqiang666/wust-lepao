# -*- coding: utf-8 -*-
"""给照片写入 UserComment=MD5(uid) 后重发 faceVerify，验证活体检测真面目。"""
import base64
import hashlib
import io
import json
import os
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
os.environ.setdefault("LEPAO2_CONFIG", os.path.join(BASE, "config.json"))

import piexif
from PIL import Image

from lepao.accounts import AccountRegistry
from lepao.auth import AuthState

PHOTO = r"D:\nanqiang\Downloads\IMG20261118173421..jpg"


def make_signed_photo(uid_str, max_side=640, quality=78):
    """缩放 + 写 UserComment=MD5(uid) 的 EXIF，返回 JPEG bytes。"""
    img = Image.open(PHOTO).convert("RGB")
    w, h = img.size
    scale = min(1.0, max_side / max(w, h))
    if scale < 1.0:
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    md5 = hashlib.md5(uid_str.encode()).hexdigest()
    exif_dict = {"0th": {}, "Exif": {piexif.ExifIFD.UserComment: md5.encode("utf-8")},
                 "GPS": {}, "1st": {}}
    exif_bytes = piexif.dump(exif_dict)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, exif=exif_bytes)
    return buf.getvalue(), md5


def main():
    reg = AccountRegistry(os.path.join(BASE, "config.json"))
    auth = AuthState(reg, reg.resolve())
    client = auth.make_client(pace=0.5)
    uid = auth.uid
    uid_str = str(uid)
    now = int(time.time())

    print(f"[0] uid={uid_str}")

    # 控制组：不带签名的原始缩放照片
    img = Image.open(PHOTO).convert("RGB")
    w, h = img.size
    scale = min(1.0, 640 / max(w, h))
    img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=78)
    plain_b64 = base64.b64encode(buf.getvalue()).decode()
    print(f"\n[1] 对照组：无签名照片")
    r = client.post("/v3/api.php/Run2/faceVerify",
                    {"type": "1", "game_id": "2448", "face_file": plain_b64})
    print(f"    status={r.get('status')} info={str(r.get('info'))[:60]!r}")

    # 实验组：签名照片（UserComment=MD5(uid)）
    signed, md5 = make_signed_photo(uid_str)
    signed_b64 = base64.b64encode(signed).decode()
    print(f"\n[2] 实验组：签名照片 UserComment=MD5({uid_str})={md5}")
    print(f"    签名照片 {len(signed)} 字节")
    r2 = client.post("/v3/api.php/Run2/faceVerify",
                     {"type": "1", "game_id": "2448", "face_file": signed_b64})
    print(f"    status={r2.get('status')} info={str(r2.get('info'))[:80]!r}")
    if isinstance(r2.get("data"), dict):
        print(f"    data={json.dumps(r2.get('data'), ensure_ascii=False)[:200]}")


if __name__ == "__main__":
    main()
