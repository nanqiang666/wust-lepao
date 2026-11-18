# -*- coding: utf-8 -*-
"""刷新重兑乐跑 token：用 oauth_session.json 里的微信 OAuth 凭据重新兑换新 token。
无需重新扫码；微信 access_token 过期时自动用 refresh_token 刷新。
用法: py -3 refresh_token.py [--member 学号]
"""
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
os.environ.setdefault("LEPAO2_CONFIG", os.path.join(BASE, "config.json"))

from lepao import qr_login as QL


def main():
    # 刷新微信 OAuth（若 access_token 过期则用 refresh_token 换新）
    info = QL.load_oauth_session()
    if not info.get("openid"):
        print("[失败] state/oauth_session.json 缺少 openid，需要先扫码授权")
        return 1

    print(f"[1] 载入 OAuth 会话: provider={info.get('provider')} openid={str(info.get('openid'))[:12]}…")
    # 先主动刷新微信 OAuth，确保 access_token 是新的
    info = QL.refresh_wechat_oauth(info)
    at = info.get("access_token", "")
    print(f"[2] 微信 access_token: {'有(' + str(len(at)) + '位)' if at else '无'}")

    print("[3] 兑换乐跑 token (quickLoginV339)…")
    bundle = QL.exchange_lepao_token(
        info, sync_config=True,
        mobile_model=info.get("lepao", {}).get("mobile_model") or "PLK110",
    )
    print(f"[4] 成功! uid={bundle.get('uid')} 学号={bundle.get('student_num')} "
          f"学校={bundle.get('school_name')} 跑区={bundle.get('run_zone_name')}")
    print(f"    token={bundle.get('token', '')[:12]}… "
          f"refresh_expire={bundle.get('refresh_expire')}")
    print("[完成] config.json 已更新为该成员新 token，可直接实跑提交验证抓拍")
    return 0


if __name__ == "__main__":
    sys.exit(main())
