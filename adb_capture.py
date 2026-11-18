# -*- coding: utf-8 -*-
"""ADB 一键抓取/同步手机端「步道乐跑 App」会话工具（Android 专用）

支持两种模式:
  1. --mmkv   (需要手机已 root): 直接从 /data/data/com.lptiyu.tanke/files/mmkv/setting
              读取最新登录态 (uid / access_token / school_id / student_num) 并写入 lepaorun/config.json，
              不修改手机网络代理。
  2. --mitm   (抓包模式): 自动通过 adb reverse tcp:8888 tcp:8888 启动 mitmdump 监听，
              并在退出时自动恢复 settings put global http_proxy :0。
"""
import argparse
import datetime
import json
import os
import re
import struct
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LEPAORUN = os.path.join(_HERE, "lepaorun")
_CFG_PATH = os.path.join(_LEPAORUN, "config.json")
_SAMPLE_CFG = os.path.join(_LEPAORUN, "config.sample.json")
sys.path.insert(0, _LEPAORUN)

from lepao.v3api import V3Client  # noqa: E402


def _read_varint(buf, pos):
    res, shift = 0, 0
    while pos < len(buf):
        b = buf[pos]
        pos += 1
        res |= (b & 0x7F) << shift
        if not (b & 0x80):
            return res, pos
        shift += 7
    raise EOFError()


def _decode_mmkv_val(vb):
    if not vb:
        return ""
    try:
        sl, p = _read_varint(vb, 0)
        if p + sl == len(vb) and sl > 0:
            s = vb[p:].decode("utf-8")
            if all(ord(c) >= 32 for c in s):
                return s
    except Exception:
        pass
    try:
        iv, p = _read_varint(vb, 0)
        if p == len(vb):
            return iv
    except Exception:
        pass
    return vb.hex()


def parse_mmkv_all(raw: bytes) -> dict:
    """按 MMKV 追加顺序解析，保留每个 key 最后一次出现的值，同时提取全部 32 位 hex token。"""
    kv = {}
    tot = struct.unpack_from("<I", raw, 0)[0]
    end = min(len(raw), 4 + tot)
    pos = 12 if raw[8:12] == b"\x00\x00\x00\x00" else 8
    while pos < end:
        kl, p2 = _read_varint(raw, pos)
        if kl == 0 or kl > 128 or p2 + kl > end:
            pos += 1
            continue
        try:
            k = raw[p2:p2 + kl].decode("ascii")
        except Exception:
            pos += 1
            continue
        if not re.match(r"^[A-Za-z0-9_.:-]+$", k):
            pos += 1
            continue
        vl, p3 = _read_varint(raw, p2 + kl)
        if p3 + vl > end:
            pos += 1
            continue
        kv[k] = _decode_mmkv_val(raw[p3:p3 + vl])
        pos = p3 + vl
    return kv


def _extract_uids(raw: bytes) -> list:
    uids = []
    for m in re.finditer(rb"user_id", raw):
        try:
            _, p2 = _read_varint(raw, m.end())
            val, _ = _read_varint(raw, p2)
            if val > 10 and val not in uids:
                uids.append(val)
        except Exception:
            pass
    return list(reversed(uids))


def _adb_prop(prop: str, default: str = "") -> str:
    try:
        r = subprocess.run(["adb", "shell", "getprop", prop], capture_output=True, text=True, timeout=5)
        return r.stdout.strip() or default
    except Exception:
        return default


def sync_from_mmkv() -> int:
    # 使用 exec-out 避免 Windows adb shell 将 0x0a 转成 0x0d 0x0a 破坏二进制 protobuf
    p = subprocess.run(
        ["adb", "exec-out", "su", "-c", "cat /data/data/com.lptiyu.tanke/files/mmkv/setting"],
        capture_output=True,
        timeout=15,
    )
    if p.returncode != 0 or not p.stdout:
        print("[ADB] 读取手机 mmkv 失败，请确认已连接 ADB 且具备 root 权限。")
        return 2
    raw = p.stdout
    kv = parse_mmkv_all(raw)
    uids = _extract_uids(raw)
    if kv.get("user_id") and int(kv["user_id"]) > 10 and int(kv["user_id"]) not in uids:
        uids.insert(0, int(kv["user_id"]))

    tokens = [m.group(0).decode() for m in re.finditer(rb"[0-9A-F]{32}", raw)]
    tok = str(kv.get("access_token") or "")
    cands = ([tok] if len(tok) == 32 else []) + [t for t in reversed(tokens) if t != tok]

    model = _adb_prop("ro.product.model", "PLK110")
    os_ver = _adb_prop("ro.build.version.release", "16")
    dev_id = str(kv.get("device_id") or kv.get("mobileDeviceId") or "00000000-6d3f-2934-ffff-ffffef05ac4a")
    sid_guess = int(kv.get("school_id") or 0)

    active_uid, active_tok, user_info = 0, "", {}
    for u in uids:
        for t in cands:
            cli = V3Client(uid=u, token=t, school_id=sid_guess, host="api2.lptiyu.com")
            r = cli.post_app(
                "/v3/api.php/User/User",
                {},
                version="231",
                version_name="4.3.1",
                mobile_model=model,
                mobile_device_id=dev_id,
                mobile_os_version=os_ver,
            )
            if isinstance(r, dict) and r.get("status") not in (101, 102) and r.get("name"):
                active_uid, active_tok, user_info = u, t, r
                break
        if active_tok:
            break

    if not active_tok:
        print(f"[ADB] 候选 uid={uids} 暂未检测到有效在线 token（App 可能尚未完成登录）。")
        return 2

    cfg = (
        json.load(open(_CFG_PATH, encoding="utf-8-sig"))
        if os.path.isfile(_CFG_PATH)
        else json.load(open(_SAMPLE_CFG, encoding="utf-8"))
    )
    sn = str(user_info.get("student_num") or kv.get("student_num") or active_uid)
    sid = int(user_info.get("school_id") or sid_guess or 0)
    name = str(user_info.get("name") or sn)
    accs = cfg.setdefault("accounts", {})
    accs[sn] = {
        "uid": active_uid,
        "school_id": sid,
        "student_num": sn,
        "card_id": sn,
        "name": name,
        "alias": name,
        "enabled": True,
        "policy": {**(accs.get(sn, {}).get("policy", {})), "mobile_model": model},
        "auth": {
            "token": active_tok,
            "issued_at": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "source": "adb_mmkv",
            "consumed_at": "",
        },
    }
    cfg["active"] = sn
    with open(_CFG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print(f"[ADB] 同步成功! 用户={name} uid={active_uid} school_id={sid} -> {_CFG_PATH}")
    return 0


def run_mitm_capture() -> int:
    mitm = os.path.join(_HERE, ".venv", "Scripts", "mitmdump.exe")
    if not os.path.isfile(mitm):
        mitm = "mitmdump"
    addon = os.path.join(_HERE, "capture", "token_addon.py")
    flow_out = os.path.join(_HERE, "logs", "adb_cap.mitm")
    os.makedirs(os.path.dirname(flow_out), exist_ok=True)
    try:
        subprocess.run(["adb", "reverse", "tcp:8888", "tcp:8888"], check=True)
        subprocess.run(["adb", "shell", "settings", "put", "global", "http_proxy", "127.0.0.1:8888"], check=True)
        print("[ADB抓包] 代理已挂载至 127.0.0.1:8888，请在手机打开步道乐跑 App（Ctrl+C 结束并自动恢复代理）…")
        subprocess.run(
            [mitm, "-p", "8888", "--ssl-insecure", "--allow-hosts", r"^(.*\.)?(lptiyu\.com|wust\.edu\.cn)(:\d+)?$", "-s", addon, "-w", flow_out],
            check=False,
        )
    finally:
        subprocess.run(["adb", "shell", "settings", "delete", "global", "http_proxy"], capture_output=True)
        subprocess.run(["adb", "shell", "settings", "delete", "global", "global_http_proxy_host"], capture_output=True)
        subprocess.run(["adb", "shell", "settings", "delete", "global", "global_http_proxy_port"], capture_output=True)
        subprocess.run(["adb", "reverse", "--remove-all"], capture_output=True)
        print("[ADB抓包] 已清除手机代理设置")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mitm", action="store_true", help="启动 ADB 反向代理抓包")
    ap.add_argument("--mmkv", action="store_true", help="直接从已 root 手机读取登录会话")
    args = ap.parse_args()
    if args.mitm:
        sys.exit(run_mitm_capture())
    sys.exit(sync_from_mmkv())
