# -*- coding: utf-8 -*-
"""只验证抓拍照片 OSS 上传链路：取 STS → 上传照片 → 打印 URL。
不提交跑步记录，零风险。用法: py -3 verify_photo_upload.py [--member 学号] [--photo 图片路径]
"""
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
os.environ.setdefault("LEPAO2_CONFIG", os.path.join(BASE, "config.json"))

from lepao.accounts import AccountRegistry
from lepao.auth import AuthState
from lepao import capture_photo as CP


def main():
    sel = None
    photo_path = None
    if "--member" in sys.argv:
        sel = sys.argv[sys.argv.index("--member") + 1]
    if "--photo" in sys.argv:
        photo_path = sys.argv[sys.argv.index("--photo") + 1]

    reg = AccountRegistry(os.path.join(BASE, "config.json"))
    key = reg.resolve(sel)
    auth = AuthState(reg, key)
    client = auth.make_client(pace=0.5)

    print(f"[1] 成员 {auth.label} uid={auth.uid} token={auth.token[:8]}…")
    sts = client.get_oss_sts()
    if not isinstance(sts, dict) or "AccessKeySecret" not in sts:
        print(f"[失败] getOssSts 异常: {str(sts)[:200]}")
        return 1
    print(f"[2] STS 已获取 bucket={sts.get('bucket')}")

    photo_bytes, src = CP.load_capture_photo_bytes(photo_path)
    print(f"[3] 照片内容: {len(photo_bytes)} 字节, 来源={src}")

    status, url, body = CP.capture_photo_for_submit(sts, photo_path=photo_path)
    print(f"[4] 上传结果 status={status}")
    print(f"    url={url}")
    if status not in (200, 203, 204):
        print(f"    body={str(body)[:400]}")
        return 1
    print("[成功] 抓拍照片 OSS 上传链路通了，URL 可作为 file_img 填入提交")
    return 0


if __name__ == "__main__":
    sys.exit(main())
