# -*- coding: utf-8 -*-
"""诊断抓拍照片 OSS callback 失败原因：上传带 callback 照片，打印完整响应，再查 capture_num。"""
import json
import os
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
os.environ.setdefault("LEPAO2_CONFIG", os.path.join(BASE, "config.json"))

from lepao.accounts import AccountRegistry
from lepao.auth import AuthState
from lepao import record as REC
from lepao import capture_photo as CP


def main():
    reg = AccountRegistry(os.path.join(BASE, "config.json"))
    auth = AuthState(reg, reg.resolve())
    client = auth.make_client(pace=0.4)
    now = int(time.time())

    sts = client.get_oss_sts()
    print(f"[1] STS bucket={sts.get('bucket')}")
    print(f"[1] callback 字段: {str(sts.get('callback'))[:120]}...")

    photo_bytes, src = CP.load_capture_photo_bytes(None)
    print(f"[2] 照片 {len(photo_bytes)} 字节 src={src}")

    # 直接调底层上传，拿完整响应
    status, rel_path, url, body = REC.upload_capture_photo(sts, photo_bytes)
    print(f"[3] 上传 status={status} rel_path={rel_path}")
    print(f"[3] url={url}")
    print(f"[3] 响应 body 全文:")
    print(body)

    # 查抓拍状态
    print(f"\n[4] 查询 getCaptureStatus")
    r = client.post("/v3/api.php/Run2/getCaptureStatus", {
        "start_time": str(now - 600),
        "distance": "2.8",
        "game_id": "2448",
        "point_ids": "27989,27990,27991",
    })
    print(f"  -> {json.dumps(r, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
