# -*- coding: utf-8 -*-
"""武科大乐跑 —— 微信 / QQ 官方二维码扫码登录工具

用法:
  python qr_login.py --wx         # 微信扫码登录并自动脱机兑换乐跑 token
  python qr_login.py --qq         # QQ 扫码登录并自动脱机兑换乐跑 token
  python qr_login.py --exchange   # 使用已保存的 state/oauth_session.json 直接脱机兑换新 token（免重扫）
  python qr_login.py --test       # 仅测试二维码生成（不阻塞轮询）
"""
import argparse
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "lepaorun"))

from lepao.qr_login import (  # noqa: E402
    QQQRLogin,
    WeChatQRLogin,
    exchange_lepao_token,
    render_ascii_qr,
)


def _do_exchange(oauth_res=None):
    lp = exchange_lepao_token(oauth_res, sync_config=True)
    print(
        f"[脱机兑换] 成功! 姓名={lp['name']} 学号={lp['student_num']} "
        f"UID={lp['uid']} 学校={lp['school_name']}({lp['school_id']}) "
        f"跑区={lp['run_zone_name'] or '-'} Token={lp['token'][:10]}…"
    )
    print("[脱机兑换] 账号与在线 Token 已自动写入 lepaorun/config.json，可直接运行 driver.py！")
    return lp


def run_wx(test_only=False, timeout_s=180):
    cli = WeChatQRLogin()
    info = cli.create_qr()
    print(f"[微信扫码] 应用名: {info['appname']} | PNG 已保存: {info['png_path']}")
    print(f"[微信扫码] 浏览器直链: {info['qr_url']}")
    print(render_ascii_qr(info["qr_url"]))
    if test_only:
        return 0
    t0 = time.time()
    last = ""
    while time.time() - t0 < timeout_s:
        st, payload = cli.poll_once(last_code=last)
        if st == "scanned":
            last = "404"
            print("[微信扫码] 已扫码，请在手机微信上点击「允许/确认登录」…")
        elif st == "confirmed":
            code = payload.get("wx_code") or ""
            print(f"[微信扫码] 授权成功，换取用户信息 (code={code[:8]}…)…")
            res = cli.exchange_code(code)
            print(f"[微信扫码] 成功! 昵称={res.get('nickname')} openid={res.get('openid')} unionid={res.get('unionid')}")
            _do_exchange(res)
            return 0
        elif st in ("cancelled", "expired"):
            print(f"[微信扫码] 状态={st}，请重新执行")
            return 2
        time.sleep(1.5)
    print("[微信扫码] 超时未确认")
    return 2


def run_qq(test_only=False, timeout_s=180):
    cli = QQQRLogin()
    info = cli.create_qr()
    print(f"[QQ扫码] AppID={info['client_id']} | PNG 已保存: {info['png_path']}")
    if test_only:
        print(f"[QQ扫码] 二维码字节={len(info['png_bytes'])}B，生成成功!")
        return 0
    try:
        os.startfile(info["png_path"])
        print("[QQ扫码] 已自动打开二维码图片窗口，请用手机 QQ 扫码…")
    except Exception:
        print(f"[QQ扫码] 请打开图片扫码: {info['png_path']}")
    t0 = time.time()
    last_st = ""
    while time.time() - t0 < timeout_s:
        st, payload = cli.poll_once()
        if st != last_st:
            last_st = st
            if st == "scanned":
                print("[QQ扫码] 已扫码，请在手机 QQ 上确认授权…")
        if st == "confirmed":
            res = cli.exchange_oauth(payload.get("jump_url", ""), payload.get("nickname", ""))
            print(f"[QQ扫码] 成功! 昵称={res.get('nickname')} openid={res.get('openid')} token={res.get('access_token', '')[:8]}…")
            _do_exchange(res)
            return 0
        if st in ("expired", "error"):
            print(f"[QQ扫码] 失败: {payload}")
            return 2
        time.sleep(2.0)
    print("[QQ扫码] 超时未确认")
    return 2


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--wx", action="store_true", help="微信扫码登录并脱机兑换")
    ap.add_argument("--qq", action="store_true", help="QQ 扫码登录并脱机兑换")
    ap.add_argument("--exchange", action="store_true", help="直接用已有 OAuth 凭据脱机兑换新 token")
    ap.add_argument("--test", action="store_true", help="仅测试出码不等待扫码")
    args = ap.parse_args()
    if args.exchange:
        _do_exchange()
        sys.exit(0)
    if args.qq:
        sys.exit(run_qq(test_only=args.test))
    sys.exit(run_wx(test_only=args.test))
