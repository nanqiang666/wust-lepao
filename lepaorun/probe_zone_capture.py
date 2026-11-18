# -*- coding: utf-8 -*-
"""探测武科大三个跑区的 is_capture_zone / is_register_face / capture_config 抓拍要求。
只读，不提交。用法: py -3 probe_zone_capture.py [--member 学号]
"""
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
os.environ.setdefault("LEPAO2_CONFIG", os.path.join(BASE, "config.json"))

from lepao.accounts import AccountRegistry
from lepao.auth import AuthState

ZONES = [
    ("1963", "沁湖环道跑区"),
    ("2447", "北区田径场跑区"),
    ("2448", "南区田径场跑区"),
]


def main():
    sel = None
    if "--member" in sys.argv:
        sel = sys.argv[sys.argv.index("--member") + 1]
    reg = AccountRegistry(os.path.join(BASE, "config.json"))
    key = reg.resolve(sel)
    auth = AuthState(reg, key)
    client = auth.make_client(pace=0.5)
    print(f"[探测] 成员 {auth.label} uid={auth.uid} token={auth.token[:8]}…")

    for zid, zname in ZONES:
        try:
            client.set_run_zone(zid)
            cfg = client.before_run()
        except Exception as e:
            print(f"  [{zname}] 切换/查询失败: {e}")
            continue
        if not isinstance(cfg, dict):
            print(f"  [{zname}] 异常响应: {str(cfg)[:120]}")
            continue
        cap_cfg = cfg.get("capture_config") or {}
        config = cap_cfg.get("config") or [{}]
        print(f"  [{zname}] game_id={cfg.get('run_zone_id')} "
              f"is_capture_zone={cfg.get('is_capture_zone')} "
              f"is_register_face={cfg.get('is_register_face')} "
              f"capture_type={cap_cfg.get('capture_type')} "
              f"day_capture_site_num={config[0].get('day_capture_site_num')} "
              f"day_capture_num={config[0].get('day_capture_num')} "
              f"night_capture_site_num={config[0].get('night_capture_site_num')} "
              f"night_capture_num={config[0].get('night_capture_num')}")

    # 还原默认跑区(不强制, 打印即可)
    print("[探测] 完成")


if __name__ == "__main__":
    main()
