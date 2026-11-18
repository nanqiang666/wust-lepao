# -*- coding: utf-8 -*-
# --- lepao-research-notice v1 (do not remove; see LICENSE) ---
# 乐跑协议研究（Lepao Research） · https://github.com/dan-cun/lepao3
# Copyright (c) 2026 dan-cun · 技术讨论 QQ 1224145544（仅作技术讨论，不提供代打卡）
# 许可证 LRL-1.0（乐跑研究协议 1.0）：仅供学习 · 不可牟利 · 再发布须署名引用原始仓库 · 声明不得删除
# 删除或篡改本块即依 LRL-1.0 第三条自动终止授权；衍生版须继续以 LRL-1.0 授权并标注修改说明。
# --- end lepao-research-notice ---
"""武汉科技大学乐跑驱动引擎（基于 dan-cun/lepao3 与 2422725977/ctbu-lepao 适配）

模式:
  python driver.py --simulate [--zone qinhu|south_track|north_track] [--gender male|female]
      离线模拟模式（零联网，用武科大黄家湖校区预设跑区验证轨迹生成、防封自检与加解密报文）
  python driver.py [--zone ...] [--gender ...]
      在线 Dry-Run（真门校验 -> 拉取武科大真实跑区/打卡点/围栏 -> 当日额度 -> 轨迹生成，零写入）
  python driver.py --submit [--canary]
      正式提交（OSS 上传 -> stopRunV278 -> 陀螺仪补传 -> recordDetailV270 复核）
  python driver.py --probe-host
      实测 api2.lptiyu.com 服务器连通性与 App System/getIp 接口

退出码: 0 成功/模拟/干跑 | 2 token 失效/缺失 | 3 当日额度已满 | 4 接口或生成异常
"""
import datetime
import json
import os
import random
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)

from lepao.crypto import decrypt_data, encrypt_data, sign_md5  # noqa: E402
from lepao import license_guard as LG  # noqa: E402
from lepao import record as REC  # noqa: E402
from lepao import wust_track as WT  # noqa: E402
from lepao.v3api import V3Client, V3Error  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DEFAULTS = {
    "dist_lo": 2.60,
    "dist_hi": 3.30,
    "pace_lo": 240,
    "pace_hi": 480,
    "mobile_model": "BRQ-AN00",
    "zone_key": "qinhu",
    "gender": "male",
    "min_checkpoints": 3,
    "vena4": False,
}

CFG_PATH = os.path.join(_HERE, "config.json")
SAMPLE_CFG_PATH = os.path.join(_HERE, "config.sample.json")


def load_config():
    if os.path.isfile(CFG_PATH):
        with open(CFG_PATH, encoding="utf-8-sig") as f:
            return json.load(f)
    if os.path.isfile(SAMPLE_CFG_PATH):
        with open(SAMPLE_CFG_PATH, encoding="utf-8-sig") as f:
            return json.load(f)
    return {"version": 2, "accounts": {}, "environment": {"api_host": "api2.lptiyu.com"}, "policy": dict(DEFAULTS)}


def log(msg):
    print(msg, flush=True)


class Account:
    """封装单个账号的全部信息，供提交流程使用"""

    def __init__(self, acc_dict: dict, cfg: dict):
        self.raw = acc_dict
        self.alias = acc_dict.get("alias") or acc_dict.get("name") or acc_dict.get("student_num") or "WUST"
        self.uid = acc_dict.get("uid", 0)
        self.school_id = acc_dict.get("school_id", 0)
        self.student_num = acc_dict.get("student_num", "")
        self.card_id = acc_dict.get("card_id", self.student_num)
        self.token = (acc_dict.get("auth") or {}).get("token", "")
        env = cfg.get("environment") or {}
        self.api_host = env.get("api_host", "api2.lptiyu.com")
        self.api_proxy = env.get("api_proxy") or None

        pol = {**DEFAULTS}
        pol.update(cfg.get("policy") or {})
        pol.update(acc_dict.get("policy") or {})
        self.gender = pol.get("gender", "male")
        rule_g = WT.WUST_RULES["female" if self.gender == "female" else "male"]
        self.dist_lo = float(pol.get("dist_lo") or rule_g["default_dist_lo"])
        self.dist_hi = float(pol.get("dist_hi") or rule_g["default_dist_hi"])
        if self.gender == "female" and "dist_lo" not in (acc_dict.get("policy") or {}):
            self.dist_lo = min(self.dist_lo, rule_g["default_dist_lo"])
            self.dist_hi = min(self.dist_hi, rule_g["default_dist_hi"])
        self.pace_lo = int(pol.get("pace_lo") or WT.WUST_RULES["safe_pace_lo"])
        self.pace_hi = int(pol.get("pace_hi") or WT.WUST_RULES["safe_pace_hi"])
        self.min_checkpoints = int(pol.get("min_checkpoints") or WT.WUST_RULES["min_checkpoints"])
        self.zone_key = WT.resolve_zone_key(pol.get("zone_key", "qinhu"))
        self.vena4 = bool(pol.get("vena4", False))
        self.mobile_model = pol.get("mobile_model", "BRQ-AN00")

    def make_client(self, pace=0.0):
        return V3Client(
            uid=self.uid,
            token=self.token,
            school_id=self.school_id,
            student_num=self.student_num,
            card_id=self.card_id,
            host=self.api_host,
            proxy=self.api_proxy,
            pace=pace,
        )


def gen_with_retry(cps, rnd, acc: Account, zone_polygon=None, attempts=10, canary=False):
    rule_g = WT.WUST_RULES["female" if acc.gender == "female" else "male"]
    min_req = rule_g["min_dist_km"]
    d_lo = max(min_req + 0.05, 2.55 if acc.gender == "male" else 2.08) if canary else max(min_req + 0.05, acc.dist_lo)
    d_hi = (d_lo + 0.25) if canary else max(d_lo + 0.20, acc.dist_hi)
    p_lo = 300 if canary else acc.pace_lo
    p_hi = 460 if canary else acc.pace_hi
    min_cp = min(acc.min_checkpoints, len(cps))

    for k in range(attempts):
        target = rnd.uniform(d_lo + 0.05, d_hi - 0.05) * 1000.0
        subset_n = min_cp if (acc.vena4 and len(cps) > min_cp) else None
        res = WT.generate_run(cps, target, rnd, zone_polygon=zone_polygon, subset_n=subset_n)
        res["_target"] = target
        dist = res["distance_km"]
        used = res["used_time"]
        pace = used / dist if dist else 9e9
        ok_dist = d_lo <= dist <= d_hi
        ok_pace = p_lo <= pace <= p_hi
        ok_time = used <= 3300 if dist <= 3.0 else used <= 6900
        checks = WT.self_check(res, zone_polygon=zone_polygon, min_checkpoints=min_cp)
        failed = {k2: v for k2, v in checks.items() if not v[0]}
        log(
            f"  [{acc.alias} gen.{k}] target={target:.0f}m {dist:.2f}km {used}s "
            f"pace={int(pace)}s/km pts={res['path_pts']} steps={res['step_num']} "
            f"cp={len(res['crossings'])} | "
            f"{'PASS' if not failed else 'FAIL ' + json.dumps({k2: v[1] for k2, v in failed.items()}, ensure_ascii=False)}"
        )
        if ok_dist and ok_pace and ok_time and not failed:
            res["self_check"] = checks
            return res
    raise RuntimeError(f"[{acc.alias}] 轨迹生成重试耗尽")


# ---------- 离线模拟模式 ----------
def simulate_wust(zone_key="qinhu", gender="male", cfg=None, save_path=None):
    """离线模拟武科大跑步：生成轨迹、步数、陀螺仪、stopRun 报文与加密闭环验证（零联网）。"""
    cfg = cfg or load_config()
    zk = WT.resolve_zone_key(zone_key)
    zinfo = WT.WUST_ZONES[zk]
    acc_dict = {
        "uid": 0,
        "school_id": 0,
        "student_num": "SIM_WUST",
        "alias": f"模拟-{zinfo['name']}",
        "policy": {"zone_key": zk, "gender": gender},
    }
    acc = Account(acc_dict, cfg)
    rnd = random.Random()
    cps = zinfo["checkpoints"]
    poly = zinfo["polygon"]
    is_open, win_str = WT.is_in_open_window(zk)
    log(f"[WUST 离线模拟] 跑区={zinfo['name']}({zk}) 打卡点x{len(cps)} 性别={gender} "
        f"距离窗=[{acc.dist_lo:.2f},{acc.dist_hi:.2f}]km")
    log(f"[WUST 离线模拟] 当前时段开放状态={'开放中' if is_open else '非开放时段'} (规程: {win_str})")

    res = gen_with_retry(cps, rnd, acc, zone_polygon=poly)
    srv_now = int(time.time())
    end_time = srv_now - rnd.randint(15, 75)
    start_time = end_time - res["used_time"]
    now_ms, record_file, fname = REC.make_record_file(rnd)
    tr_json = json.dumps(res["track"], ensure_ascii=False, separators=(",", ":"))
    step_info = json.dumps(res["step_info"], separators=(",", ":"))

    biz = {
        "term_id": 1,
        "game_id": zk,
        "start_time": int(start_time),
        "end_time": int(end_time),
        "distance": round(float(res["distance_km"]), 2),
        "record_img": "",
        "log_data": json.dumps(
            [{**e, "time": int(start_time) + max(5, int(e["time"]))} for e in res["log_data"]],
            ensure_ascii=False, separators=(",", ":"),
        ),
        "file_img": "",
        "is_running_area_valid": 1,
        "mobileDeviceId": 1,
        "mobileModel": acc.mobile_model,
        "mobileOsVersion": 1,
        "step_info": step_info,
        "step_num": int(res["step_num"]),
        "used_time": int(res["used_time"]),
        "record_file": record_file,
    }

    # 验证加密/解密/签名与官方协议一致
    signed = {**biz, "timestamp": srv_now, "nonce": "123456", "ostype": 5}
    signed["sign"] = sign_md5(signed)
    ct = encrypt_data(json.dumps(signed, ensure_ascii=False))
    pt = json.loads(decrypt_data(ct))
    assert pt["sign"] == signed["sign"] and abs(pt["distance"] - biz["distance"]) < 1e-6

    out = {
        "mode": "offline_simulate",
        "school": "武汉科技大学",
        "zone_key": zk,
        "zone_name": zinfo["name"],
        "gender": gender,
        "open_now": is_open,
        "open_windows": win_str,
        "distance_km": biz["distance"],
        "used_time": biz["used_time"],
        "pace_s_per_km": int(biz["used_time"] / biz["distance"]),
        "step_num": biz["step_num"],
        "track_pts": res["path_pts"],
        "gyr_samples": len(res["gyr"]),
        "crossings": res["crossings"],
        "self_check": {k: {"passed": v[0], "detail": v[1]} for k, v in res["self_check"].items()},
        "crypto_roundtrip_ok": True,
        "zone_polygon": poly,
        "checkpoints": cps,
        "track": res["track"],
        "stopRun_biz": biz,
    }
    state_dir = os.path.join(_ROOT, "state")
    os.makedirs(state_dir, exist_ok=True)
    out_path = save_path or os.path.join(state_dir, "sim_last.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    log(f"[WUST 离线模拟] 完成! 轨迹={res['path_pts']}点 距离={biz['distance']}km "
        f"配速={out['pace_s_per_km']}s/km 陀螺仪={len(res['gyr'])}点 已保存 -> {out_path}")
    return out, 0


# ---------- 在线全流程 ----------
def run_for_account(acc: Account, submit=False, canary=False, zone_override=None):
    rnd = random.Random()
    if not acc.token:
        log(f"[{acc.alias}] TOKEN_MISSING: 未配置有效 token（先扫码登录或抓包捕获）")
        return None, 2

    client = acc.make_client(pace=0.8)

    # [0] 真门
    r = client.post("/v3/api.php/WpRun/getTermList", {})
    if isinstance(r, dict) and r.get("status") == 101:
        log(f"[{acc.alias}] TOKEN_DEAD (101)")
        return None, 2
    s = client.get_school_info()
    log(f"[{acc.alias} 0] token 有效 | 学校={s.get('school_name', '未知')} api={s.get('api_link', acc.api_host)}")

    # [1] 跑区/打卡点/官方电子围栏
    cfg = client.before_run()
    if not isinstance(cfg, dict) or not cfg.get("run_line_info"):
        log(f"[{acc.alias} 1] beforeRunV260 异常: {str(cfg)[:250]}")
        return None, 4
    if zone_override and str(cfg.get("run_zone_id") or "") != str(zone_override):
        try:
            client.set_run_zone(str(zone_override))
            cfg = client.before_run()
            log(f"[{acc.alias} 1b] 已切换跑区 -> {zone_override}")
        except Exception as e:
            log(f"[{acc.alias} 1b] 切跑区失败(忽略继续): {e}")

    rli = cfg.get("run_line_info") or {}
    zone = str(cfg.get("run_zone_id") or "")
    term_id = str(cfg.get("term_id") or "0")
    cps = []
    for p in rli.get("point_list") or []:
        try:
            la, lo = str(p.get("jingwei")).strip().split(",")
            cps.append((float(la), float(lo), str(p.get("id"))))
        except Exception:
            continue
    poly = WT.parse_zone_polygon(cfg.get("run_zone_latlng"), fallback_cps=cps)
    log(f"[{acc.alias} 1] 跑区={zone}({cfg.get('run_zone_name')}) 打卡点x{len(cps)} 围栏顶点x{len(poly)} 学期={term_id}")
    if len(cps) < 2:
        return None, 4

    # [2] 当日额度
    day0 = int(time.mktime(datetime.date.today().timetuple()))
    done = 0
    for page in (1, 2):
        rr = client.post("/v3/api.php/WpRun/getTermRunRecord", {"term_id": term_id, "page": page})
        for rec in (rr.get("list") or [] if isinstance(rr, dict) else []):
            try:
                if int(rec.get("start_time") or 0) >= day0 and float(rec.get("distance") or 0) > 0 \
                        and str(rec.get("record_status") or "") == "1":
                    done += 1
            except Exception:
                pass
        if not (isinstance(rr, dict) and rr.get("list")):
            break
    log(f"[{acc.alias} 2] 今日已完成 {done} 次 (上限 1)")
    if done >= 1 and submit:
        log(f"[{acc.alias}] 当日额度已满, 不提交")
        return None, 3

    # [3] 服务器时间（两次调用对齐最新协议）
    ts_detail = client.get_timestamp_detail()
    srv_now = int(ts_detail.get("timestamp") or time.time())
    log(f"[{acc.alias} 3] 服务器时间={srv_now}")

    # [4] 生成武科大反检测轨迹
    log(f"[{acc.alias} 4] 生成轨迹:")
    res = gen_with_retry(cps, rnd, acc, zone_polygon=poly, canary=canary)
    tr_json = json.dumps(res["track"], ensure_ascii=False, separators=(",", ":"))
    step_info = json.dumps(res["step_info"], separators=(",", ":"))

    # [5] 组装
    end_time = srv_now - rnd.randint(15, 75)
    start_time = end_time - res["used_time"]
    now_ms, record_file, fname = REC.make_record_file(rnd)
    g = {
        "term_id": int(term_id),
        "game_id": zone,
        "start_time": int(start_time),
        "end_time": int(end_time),
        "distance": round(float(res["distance_km"]), 2),
        "record_img": "",
        "log_data": json.dumps(
            [{**e, "time": int(start_time) + max(5, int(e["time"]))} for e in res["log_data"]],
            ensure_ascii=False, separators=(",", ":"),
        ),
        "file_img": "",
        "is_running_area_valid": 1,
        "mobileDeviceId": 1,
        "mobileModel": acc.mobile_model,
        "mobileOsVersion": 1,
        "step_info": step_info,
        "step_num": int(res["step_num"]),
        "used_time": int(res["used_time"]),
        "record_file": record_file,
    }
    win = (
        datetime.datetime.fromtimestamp(start_time).strftime("%H:%M")
        + "~"
        + datetime.datetime.fromtimestamp(end_time).strftime("%H:%M")
    )
    log(f"[{acc.alias} 5] record_file={record_file} 时间窗={win} 距离={g['distance']}km")

    if not submit:
        out = {
            "stopRun_biz": g,
            "crossings": res["crossings"],
            "track_pts": res["path_pts"],
            "gyr_samples": len(res["gyr"]),
            "self_check": {k: {"passed": v[0], "detail": v[1]} for k, v in res["self_check"].items()},
        }
        return out, 0

    # [6] OSS 轨迹上传
    time.sleep(rnd.uniform(0.5, 1.3))
    sts = client.get_oss_sts()
    if not isinstance(sts, dict) or "AccessKeySecret" not in sts:
        log(f"[{acc.alias}] getOssSts 异常: {str(sts)[:200]}")
        return None, 4
    status, rbody = REC.upload_to_oss(encrypt_data(tr_json), sts, now_ms, record_file, rnd)
    log(f"[{acc.alias} 6] OSS 轨迹上传 status={status}")
    if status not in (200, 203, 204):
        log(f"[{acc.alias}] OSS 上传失败: {rbody[:400]}")
        return None, 4

    # [6b] 抓拍照片上传(强制抓拍跑区 is_capture_zone=1 必需; 失败不中断提交)
    try:
        from lepao import capture_photo as CP
        c_status, c_rel, c_src = CP.capture_photo_for_submit(sts, rnd=rnd)
        if c_status in (200, 203, 204) and c_rel:
            g["file_img"] = c_rel
            g["record_img"] = c_rel
            log(f"[{acc.alias} 6b] 抓拍照片上传成功 status={c_status} file_img={c_rel[:60]}… src={c_src}")
        else:
            log(f"[{acc.alias} 6b] 抓拍照片上传失败/降级 status={c_status} src={c_src}")
    except Exception as e:
        log(f"[{acc.alias} 6b] 抓拍照片上传异常(降级): {e}")

    # [6c] 人脸抓拍 faceVerify（强制抓拍跑区 is_capture_zone=1 必需，失败不中断提交）
    try:
        from lepao import face_verify as FV
        fv_status, fv_id, fv_info = FV.face_verify(
            client, ftype=FV.TYPE_STOP, game_id=zone)
        if fv_status == 1 and fv_id:
            FV.attach_face_to_stoprun(g, face_verify_id=fv_id)
            log(f"[{acc.alias} 6c] 人脸抓拍成功 face_verify_id={fv_id}")
        else:
            # 无真人脸照片/验证失败 → 用兜底 id 提交，服务器会判抓拍不足
            FV.attach_face_to_stoprun(g, face_verify_id=None)
            log(f"[{acc.alias} 6c] 人脸抓拍未通过 status={fv_status} info={fv_info!r} "
                f"(使用兜底 run_face_verify_id)")
    except Exception as e:
        log(f"[{acc.alias} 6c] 人脸抓拍异常(降级): {e}")

    # [7] stopRun
    time.sleep(rnd.uniform(0.8, 2.0))
    log(f"[{acc.alias} 7] stopRun: {g['distance']}km {g['used_time']}s steps={g['step_num']}")
    resp = client.stop_run(g)
    log(f"[{acc.alias} 7] 响应: " + json.dumps(resp, ensure_ascii=False)[:300])
    if isinstance(resp, str) and "has" in resp.lower():
        log(f"[{acc.alias} 7] 服务器返回已存在(has)——当日已有记录")
        return {"record_id": None, "distance": g["distance"], "already": True}, 0
    if not isinstance(resp, dict) or not resp.get("record_id"):
        return resp, 4
    record_id = resp["record_id"]

    # [8] 陀螺仪补传
    try:
        time.sleep(rnd.uniform(1.0, 2.5))
        sts2 = client.get_oss_sts()
        gkey = REC.gyroscope_key(rnd)
        st2, rb2 = REC.upload_oss_content(sts2, gkey, json.dumps(res["gyr"], separators=(",", ":")), rnd)
        log(f"[{acc.alias} 8] OSS 陀螺仪上传 status={st2} samples={len(res['gyr'])}")
        if st2 in (200, 203, 204):
            gy = client.post("/v3/api.php/Run2/gyroscope", {"record_id": record_id, "gyroscope_file": gkey})
            log(f"[{acc.alias} 8] Run2/gyroscope -> {json.dumps(gy, ensure_ascii=False)[:200]}")
    except Exception as e:
        log(f"[{acc.alias} 8] 陀螺仪补传异常(不影响记录): {e}")

    # [9] 复核
    time.sleep(rnd.uniform(2.5, 5.0))
    detail = client.post(
        "/v3/api.php/Run/recordDetailV270",
        {"record_id": str(record_id), "year_num": str(datetime.date.today().year)},
    )
    log(f"[{acc.alias} 9] recordDetail: " + json.dumps(detail, ensure_ascii=False)[:500])
    return {
        "record_id": record_id,
        "distance": g["distance"],
        "used_time": g["used_time"],
        "record_status": detail.get("record_status") if isinstance(detail, dict) else None,
        "record_failed_reason": detail.get("record_failed_reason") if isinstance(detail, dict) else None,
        "start_time": g["start_time"],
        "end_time": g["end_time"],
    }, 0


def probe_host(host="api2.lptiyu.com"):
    """只读探测：验证 api2.lptiyu.com App System/getIp 连通性。"""
    c = V3Client(uid=0, token="", school_id=-1, host=host)
    ip_info = c.get_server_ip(2)
    log(f"[probe] {host} System/getIp(type=2) -> {ip_info}")
    return ip_info


if __name__ == "__main__":
    LG.print_banner(lambda s: print(s, file=sys.stderr))
    args = sys.argv[1:]
    if "--probe-host" in args:
        probe_host()
        sys.exit(0)

    zone_arg = args[args.index("--zone") + 1] if "--zone" in args and args.index("--zone") + 1 < len(args) else "qinhu"
    gender_arg = args[args.index("--gender") + 1] if "--gender" in args and args.index("--gender") + 1 < len(args) else "male"
    cfg = load_config()

    if "--simulate" in args or "--offline" in args:
        summary, code = simulate_wust(zone_key=zone_arg, gender=gender_arg, cfg=cfg)
        print("EXIT", code, flush=True)
        # 精简打印，避免终端刷屏轨迹数组
        brief = {k: v for k, v in summary.items() if k not in ("track", "zone_polygon", "checkpoints", "stopRun_biz")}
        print(json.dumps(brief, ensure_ascii=False, indent=1))
        sys.exit(code)

    accounts = cfg.get("accounts") or {}
    if not accounts:
        log("[错误] accounts 表为空！请先运行 `python qr_login.py` / `capture` 或用 `--simulate` 进行离线模拟。")
        print("EXIT 2", flush=True)
        sys.exit(2)

    ak = cfg.get("active") if cfg.get("active") in accounts else list(accounts.keys())[0]
    acc = Account(accounts[ak], cfg)
    if "--gender" in args:
        acc.gender = gender_arg
    if "--vena4" in args:
        acc.vena4 = True
    submit = "--submit" in args
    canary = "--canary" in args
    z_ovr = zone_arg if "--zone" in args and zone_arg.isdigit() else None
    summary, code = run_for_account(acc, submit=submit, canary=canary, zone_override=z_ovr)
    print("EXIT", code, flush=True)
    print(json.dumps(summary, ensure_ascii=False, indent=1) if summary else "no summary")
    sys.exit(code)
