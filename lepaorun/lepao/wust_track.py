# -*- coding: utf-8 -*-
# --- lepao-research-notice v1 (do not remove; see LICENSE) ---
# 乐跑协议研究（Lepao Research） · https://github.com/dan-cun/lepao3
# Copyright (c) 2026 dan-cun · 技术讨论 QQ 1224145544（仅作技术讨论，不提供代打卡）
# 许可证 LRL-1.0（乐跑研究协议 1.0）：仅供学习 · 不可牟利 · 再发布须署名引用原始仓库 · 声明不得删除
# 删除或篡改本块即依 LRL-1.0 第三条自动终止授权；衍生版须继续以 LRL-1.0 授权并标注修改说明。
# --- end lepao-research-notice ---
"""wust_track —— 武汉科技大学（WUST）三跑区自适应反检测轨迹生成器

适配依据:
  1. 《武汉科技大学 2026-2027 学年第一学期课外环湖健康跑规程》:
     - 三个跑区（黄家湖校区）:
       * 沁湖环道跑区: 4 打卡点，整圈约 2.6km
         开放时段: 06:00-07:30, 08:30-11:30, 13:30-17:30, 20:00-23:00
       * 南区田径场跑区: 3 打卡点，每圈约 400m
         开放时段: 06:00-10:00, 12:00-14:00, 17:30-23:00
       * 北区田径场跑区: 3 打卡点，每圈约 400m
         开放时段: 06:00-10:00, 12:00-14:00, 17:30-23:00
     - 合格标准: 男生 >= 2.5km，女生 >= 2.0km，经过 >= 3 个打卡点，配速 3-11 min/km (180-660 s/km)
  2. 运行策略:
     - 在线模式: 优先解析 Run2/beforeRunV260 返回的 run_zone_latlng 多边形与 point_list
     - 离线模拟: 使用基于黄家湖校区实测地标（OSM）构建的参考跑区与打卡点
  3. 衍生修改声明: 基于 dan-cun/lepao3 与 2422725977/ctbu-lepao (ctbu_track.py) 改造适配武汉科技大学。
"""
import datetime
import json
import math
import random
import statistics

DT = 2.833  # 真机采样步长 (s)
CHECKIN_RADIUS_M = 40.0
ZONE_MARGIN_M = 12.0  # 多边形内边距（向内收缩，防止压线）
WUST_SCHOOL_ID = 61
WUST_DEFAULT_ZONE_ID = "1963"
WUST_DEFAULT_TERM_ID = "13286"

# ---------------------------------------------------------------- 武科大跑区预设与校规
WUST_RULES = {
    "male": {"min_dist_km": 2.50, "default_dist_lo": 2.60, "default_dist_hi": 3.30},
    "female": {"min_dist_km": 2.00, "default_dist_lo": 2.10, "default_dist_hi": 2.70},
    "pace_lo": 180,   # 3'00"/km
    "pace_hi": 660,   # 11'00"/km
    "safe_pace_lo": 240,  # 4'00"/km
    "safe_pace_hi": 480,  # 8'00"/km
    "min_checkpoints": 3,
}

# 离线模拟参考跑区（黄家湖校区 OSM 实测坐标中心: 沁湖绿道 30.443096,114.267034 / 北苑田径场 30.444625,114.267467 / 校园 30.441651,114.262633）
WUST_ZONES = {
    "qinhu": {
        "name": "沁湖环道跑区",
        "alias": ["沁湖", "环湖", "qinhu"],
        "open_windows": [("06:00", "07:30"), ("08:30", "11:30"), ("13:30", "17:30"), ("20:00", "23:00")],
        "min_checkpoints": 3,
        "checkpoints": [
            (30.44310, 114.26703, "wust_qh_1"),  # 沁湖东岸绿道
            (30.44485, 114.26380, "wust_qh_2"),  # 沁湖北岸
            (30.44150, 114.25985, "wust_qh_3"),  # 沁湖西侧南苑方向
            (30.43965, 114.26495, "wust_qh_4"),  # 沁湖南岸
        ],
        # [lng, lat] 多边形围栏（覆盖沁湖环道及外延缓冲）
        "polygon": [
            (114.25880, 30.44600),
            (114.26840, 30.44600),
            (114.26840, 30.43850),
            (114.25880, 30.43850),
        ],
    },
    "south_track": {
        "name": "南区田径场跑区",
        "alias": ["南区", "南田径场", "南苑", "south"],
        "open_windows": [("06:00", "10:00"), ("12:00", "14:00"), ("17:30", "23:00")],
        "min_checkpoints": 3,
        "checkpoints": [
            (30.43995, 114.26115, "wust_st_1"),  # 南苑田径场西直道
            (30.44045, 114.26165, "wust_st_2"),  # 南苑田径场北弯道
            (30.43955, 114.26205, "wust_st_3"),  # 南苑田径场东直道
        ],
        "polygon": [
            (114.26020, 30.44110),
            (114.26290, 30.44110),
            (114.26290, 30.43890),
            (114.26020, 30.43890),
        ],
    },
    "north_track": {
        "name": "北区田径场跑区",
        "alias": ["北区", "北田径场", "北苑", "north"],
        "open_windows": [("06:00", "10:00"), ("12:00", "14:00"), ("17:30", "23:00")],
        "min_checkpoints": 3,
        "checkpoints": [
            (30.44435, 114.26695, "wust_nt_1"),  # 北苑田径场西直道
            (30.44505, 114.26747, "wust_nt_2"),  # 北苑田径场北弯道
            (30.44425, 114.26798, "wust_nt_3"),  # 北苑田径场东直道
        ],
        "polygon": [
            (114.26610, 30.44570),
            (114.26880, 30.44570),
            (114.26880, 30.44350),
            (114.26610, 30.44350),
        ],
    },
}


def resolve_zone_key(name_or_key: str) -> str:
    s = (name_or_key or "qinhu").strip().lower()
    if s in WUST_ZONES:
        return s
    for k, info in WUST_ZONES.items():
        if s in info["name"].lower() or any(a in s for a in info["alias"]):
            return k
    return "qinhu"


def is_in_open_window(zone_key: str, dt: datetime.datetime = None) -> tuple:
    """检查当前时间是否在武科大对应跑区开放时段内。返回 (is_open: bool, windows_str: str)"""
    zk = resolve_zone_key(zone_key)
    wins = WUST_ZONES[zk]["open_windows"]
    now = dt or datetime.datetime.now()
    hm = now.strftime("%H:%M")
    ok = any(lo <= hm <= hi for lo, hi in wins)
    desc = ", ".join(f"{lo}-{hi}" for lo, hi in wins)
    return ok, desc


# ---------------------------------------------------------------- 地理与多边形工具
def haversine_m(lat1, lng1, lat2, lng2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(min(1.0, a)))


def quantize_geo(v):
    return int(round(v * 3600000.0)) / 3600000.0


def parse_zone_polygon(raw_latlng, fallback_cps=None):
    """解析 beforeRunV260.run_zone_latlng 为 [(lng, lat), ...]。支持多格式与兜底外接多边形。"""
    poly = []
    data = raw_latlng
    if isinstance(data, str) and data.strip():
        s = data.strip()
        if s.startswith("["):
            try:
                data = json.loads(s)
            except Exception:
                data = None
        else:
            # "lng,lat;lng,lat..." 或 "lat,lng;..."
            for seg in s.split(";"):
                parts = [x.strip() for x in seg.split(",") if x.strip()]
                if len(parts) >= 2:
                    a, b = float(parts[0]), float(parts[1])
                    # 中国武科大经度 ~114，纬度 ~30
                    poly.append((a, b) if a > 70 else (b, a))
    if isinstance(data, list):
        for item in data:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                a, b = float(item[0]), float(item[1])
                poly.append((a, b) if a > 70 else (b, a))
            elif isinstance(item, dict):
                lng = item.get("lng") or item.get("longitude") or item.get("longtitude") or item.get("o")
                lat = item.get("lat") or item.get("latitude") or item.get("a")
                if lng is not None and lat is not None:
                    poly.append((float(lng), float(lat)))
    if len(poly) >= 3:
        return poly
    if fallback_cps and len(fallback_cps) >= 2:
        lats = [c[0] for c in fallback_cps]
        lngs = [c[1] for c in fallback_cps]
        pad_lat = 0.0005  # ~55m 缓冲
        pad_lng = 0.0006
        return [
            (min(lngs) - pad_lng, max(lats) + pad_lat),
            (max(lngs) + pad_lng, max(lats) + pad_lat),
            (max(lngs) + pad_lng, min(lats) - pad_lat),
            (min(lngs) - pad_lng, min(lats) - pad_lat),
        ]
    return WUST_ZONES["qinhu"]["polygon"]


def point_in_zone(lat, lng, zone_polygon, margin_m=ZONE_MARGIN_M):
    """判断点是否在跑区多边形内（含边界安全边距）。"""
    poly = zone_polygon
    if not poly or len(poly) < 3:
        return True
    n = len(poly)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > lat) != (yj > lat)) and (lng < (xj - xi) * (lat - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    if not inside:
        return False
    if margin_m <= 0:
        return True
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        dx = (x2 - x1) * 111320 * math.cos(math.radians(lat))
        dy = (y2 - y1) * 111320
        px = (lng - x1) * 111320 * math.cos(math.radians(lat))
        py = (lat - y1) * 111320
        L2 = dx * dx + dy * dy
        tt = max(0.0, min(1.0, (px * dx + py * dy) / (L2 + 1e-9)))
        if math.hypot(px - tt * dx, py - tt * dy) < margin_m:
            return False
    return True


# ---------------------------------------------------------------- 路线规划与路径展开
def plan_route(cps, rnd):
    """按环线随机选起点与顺/逆时针方向（防止跨天路线完全重叠）。"""
    order = list(cps)
    if rnd.random() < 0.5:
        order = order[::-1]
    k = rnd.randrange(len(order))
    return order[k:] + order[:k]


def plan_route_subset(cps, rnd, n=3):
    """当跑区点位较多且启用随机抽点时，按环线序抽取 n 个点（至少 3 个）。"""
    order = list(cps)
    if len(order) <= n:
        return plan_route(order, rnd)
    chosen = rnd.sample(order, n)
    idx = {c[2]: i for i, c in enumerate(order)}
    chosen.sort(key=lambda c: idx[c[2]])
    if rnd.random() < 0.5:
        chosen = chosen[::-1]
    return chosen


def build_path(order, rnd, laps, zone_polygon):
    """铺设多圈扰动路径，中点随机摆动并受多边形围栏约束。"""
    path = []
    wob = rnd.uniform(0.06, 0.16)
    n = len(order)
    for lap in range(laps):
        ox = rnd.uniform(-6e-5, 6e-5)
        oy = rnd.uniform(-6e-5, 6e-5)
        seq = [(p[0] + ox + rnd.uniform(-2.5e-5, 2.5e-5),
                p[1] + oy + rnd.uniform(-2.5e-5, 2.5e-5)) for p in order]
        for i in range(n):
            a = seq[i]
            if lap == 0 or i > 0:
                path.append(a)
            b = seq[(i + 1) % n]
            m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            d = haversine_m(a[0], a[1], b[0], b[1])
            mid = None
            for shrink in (1.0, 0.6, 0.3, 0.0):
                lat_o = math.copysign(wob * shrink * d / 111000.0 * rnd.uniform(0.4, 1.0), rnd.random() - 0.5)
                lng_o = math.copysign(wob * shrink * d / (111000.0 * math.cos(math.radians(m[0]))) * rnd.uniform(0.4, 1.0), rnd.random() - 0.5)
                cand = (m[0] + lat_o, m[1] + lng_o)
                if point_in_zone(cand[0], cand[1], zone_polygon):
                    mid = cand
                    break
            path.append(mid or m)
    # 局部轻微凸起（模拟绕开行人/路口，不折返）
    for _ in range(rnd.randrange(0, 3)):
        if len(path) < 3:
            break
        i = rnd.randrange(len(path) - 1)
        a, b = path[i], path[i + 1]
        m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        d = haversine_m(a[0], a[1], b[0], b[1])
        amp = rnd.uniform(0.25, 0.50)
        cand = (
            m[0] + math.copysign(amp * d / 111000.0, rnd.random() - 0.5),
            m[1] + math.copysign(amp * d / (111000.0 * math.cos(math.radians(m[0]))), rnd.random() - 0.5),
        )
        if point_in_zone(cand[0], cand[1], zone_polygon):
            path[i + 1] = cand
    return path


def route_at(path, cum, s):
    s = min(max(s, 0.0), cum[-1] - 0.01)
    lo, hi = 0, len(cum) - 1
    while lo < hi:
        m = (lo + hi) // 2
        if cum[m] < s:
            lo = m + 1
        else:
            hi = m
    i = max(lo - 1, 0)
    seg = cum[i + 1] - cum[i] or 1.0
    t = (s - cum[i]) / seg
    return (path[i][0] + (path[i + 1][0] - path[i][0]) * t,
            path[i][1] + (path[i + 1][1] - path[i][1]) * t)


# ---------------------------------------------------------------- 速度与步态模型
def speed_profile(target_m, rnd):
    base_v = rnd.uniform(2.8, 3.9)  # ~4'15"-6'00"/km
    period = rnd.uniform(140, 260)
    phase = rnd.uniform(0, 6.28)
    walks = []
    t = rnd.uniform(110, 300)
    while t < target_m / max(2.2, base_v * 0.9):
        walks.append((t, rnd.uniform(15, 40)))
        t += rnd.uniform(150, 320)
    return base_v, walks, period, phase


def walk_speed_at(t, walks):
    for w0, wlen in walks:
        if w0 <= t <= w0 + wlen:
            edge = min(t - w0, w0 + wlen - t)
            f = min(1.0, edge / 6.0)
            return 1.35 + 0.35 * f
    return None


def _gen_gyro(steps_per_point, rnd):
    """60ms 采样的三轴加速度/陀螺仪数据，步态冲击与轨迹步频同步。"""
    interval_ms = 60
    out = []
    t_ms = 0
    phase = 0.0
    for sp in steps_per_point:
        cadence = sp / DT
        step_period = max(3.0, 1.0 / max(cadence, 0.05) / (interval_ms / 1000.0))
        n = int(DT * 1000 / interval_ms)
        for _ in range(n):
            ph = (phase % step_period) / step_period
            heel = math.exp(-((ph - 0.05) * 8) ** 2)
            toe = math.exp(-((ph - 0.55) * 10) ** 2) * 0.5
            az = 9.8 + heel * 3.5 + toe * 1.5 + rnd.uniform(-0.15, 0.15)
            sway = math.sin(phase / step_period * 2 * math.pi) * 0.6
            ax = sway + rnd.uniform(-0.2, 0.2)
            ay = math.cos(phase / step_period * 2 * math.pi) * 0.3 + rnd.uniform(-0.15, 0.15)
            gx = math.sin(phase / step_period * 2 * math.pi) * 0.25 + rnd.uniform(-0.05, 0.05)
            gy = math.cos(phase / step_period * 2 * math.pi) * 0.2 + rnd.uniform(-0.04, 0.04)
            gz = math.sin(phase / (step_period * 2) * 2 * math.pi) * 0.1 + rnd.uniform(-0.03, 0.03)
            out.append({"t": t_ms, "ax": round(ax, 3), "ay": round(ay, 3), "az": round(az, 3),
                        "gx": round(gx, 3), "gy": round(gy, 3), "gz": round(gz, 3)})
            t_ms += interval_ms
            phase += 1
    return out


# ---------------------------------------------------------------- 主生成器
def generate_run(cps, target_m, rnd=None, zone_polygon=None, subset_n=None):
    """生成一次完整的武科大跑步轨迹、打卡点日志、步数与陀螺仪数据。"""
    rnd = rnd or random.Random()
    if zone_polygon is None:
        zone_polygon = parse_zone_polygon(None, fallback_cps=cps)
    order = plan_route_subset(cps, rnd, subset_n) if subset_n else plan_route(cps, rnd)
    perim = sum(
        haversine_m(order[i][0], order[i][1], order[(i + 1) % len(order)][0], order[(i + 1) % len(order)][1])
        for i in range(len(order))
    )
    laps = max(1, math.ceil(target_m / max(perim, 1.0) * 1.18))
    path = build_path(order, rnd, laps, zone_polygon)
    cum = [0.0]
    for i in range(1, len(path)):
        cum.append(cum[-1] + haversine_m(path[i - 1][0], path[i - 1][1], path[i][0], path[i][1]))

    base_v, walks, period, phase = speed_profile(target_m, rnd)
    track = []
    steps_per_point = []
    s = t = 0.0
    i = 0
    jl = jn = 0.0
    while True:
        v = base_v * (1 + 0.10 * math.sin(2 * math.pi * t / period + phase)) + rnd.gauss(0, 0.20)
        if t < 30:
            v *= 0.55 + 0.45 * (t / 30)
        w = walk_speed_at(t, walks)
        if w is not None:
            v = v * 0.25 + w * 0.75

        covered_now = all(
            any(haversine_m(q["a"], q["o"], c[0], c[1]) <= CHECKIN_RADIUS_M for q in track)
            for c in order
        ) if track else False
        remaining = target_m - s
        if remaining < 120 and covered_now:
            v *= max(0.30, 0.30 + 0.70 * remaining / 120.0)

        la, lo_ = route_at(path, cum, s)
        dmin = min(haversine_m(la, lo_, c[0], c[1]) for c in order)
        if dmin < 15 and v > 2.2:
            v *= rnd.uniform(0.70, 0.90)
        v = max(0.02, min(v, 5.4))

        # AR(0.86) 相关漂移 + 罕见跳变
        jl = jl * 0.86 + rnd.gauss(0, 1.5) / 111000.0
        jn = jn * 0.86 + rnd.gauss(0, 1.7) / 111000.0 / math.cos(math.radians(la))
        if rnd.random() < 0.008:
            jl += rnd.uniform(-0.00006, 0.00006)
            jn += rnd.uniform(-0.00006, 0.00006)
        lat, lng = la + jl, lo_ + jn
        if not point_in_zone(lat, lng, zone_polygon):
            for _ in range(4):
                jl *= 0.4
                jn *= 0.4
                lat, lng = la + jl, lo_ + jn
                if point_in_zone(lat, lng, zone_polygon):
                    break
            else:
                lat, lng = la, lo_

        pt = {"a": quantize_geo(lat), "o": quantize_geo(lng)}
        if i > 0 and rnd.random() > 0.004:
            pt["s"] = round(max(0.02, v + rnd.gauss(0, 0.15)), 2)
        if dmin < 20:
            if rnd.random() < 0.80:
                pt["b"] = 2 if rnd.random() < 0.72 else 1
        elif rnd.random() < 0.50:
            pt["b"] = 1 if rnd.random() < 0.67 else 2
        c = rnd.uniform(0.0, 0.04) if i < 8 else min(abs(rnd.gauss(0.067, 0.027)), 0.10)
        pt["c"] = f"{c:.2f}"
        track.append(pt)

        stride = min(1.45, max(0.65, 0.5 + 0.22 * v))
        sps = v / stride if stride > 0 else 0
        steps_per_point.append(sps * (DT + rnd.uniform(-0.02, 0.02)) * (0.9 + 0.2 * rnd.random()))

        s += v * (DT + rnd.uniform(-0.02, 0.02))
        t += DT
        i += 1
        covered = all(
            any(haversine_m(q["a"], q["o"], c[0], c[1]) <= CHECKIN_RADIUS_M for q in track)
            for c in order
        )
        if s >= target_m and covered:
            break
        if i > 1200:
            break

    # 峰值段速限幅 + 收尾两点停止态
    for k in range(1, len(track)):
        a, b_ = track[k - 1], track[k]
        d_seg = haversine_m(a["a"], a["o"], b_["a"], b_["o"])
        if d_seg / DT > 7.3:
            f = (7.3 * DT) / d_seg
            track[k]["a"] = a["a"] + (b_["a"] - a["a"]) * f
            track[k]["o"] = a["o"] + (b_["o"] - a["o"]) * f
    for _ in range(2):
        pt = dict(track[-1])
        pt["a"] = quantize_geo(track[-1]["a"] + rnd.gauss(0, 0.8) / 111000.0)
        pt["o"] = quantize_geo(track[-1]["o"] + rnd.gauss(0, 0.9) / 111000.0)
        pt["s"] = round(rnd.uniform(0.01, 0.06), 2)
        pt["b"] = 2
        pt["c"] = f"{rnd.uniform(0.05, 0.09):.2f}"
        track.append(pt)
        steps_per_point.append(rnd.uniform(0, 0.5))
        t += DT

    dist_m = sum(haversine_m(a["a"], a["o"], b_["a"], b_["o"]) for a, b_ in zip(track, track[1:]))
    used = int(round(t))
    dist_km = round(dist_m / 1000.0, 2)  # 精确 2 位小数

    # log_data: 首过打卡点记录
    cum_d = [0.0]
    for a, b_ in zip(track, track[1:]):
        cum_d.append(cum_d[-1] + haversine_m(a["a"], a["o"], b_["a"], b_["o"]))
    scale = used / max(1e-6, len(track) * DT)
    entries = []
    for cp in order:
        la, lo, pid = cp
        idx = next((k for k in range(len(track))
                    if haversine_m(track[k]["a"], track[k]["o"], la, lo) <= CHECKIN_RADIUS_M), None)
        if idx is None:
            continue
        t_off = max(0.0, min(float(used), idx * DT * scale + rnd.uniform(-3.0, 3.0)))
        d_km = cum_d[idx] / 1000.0
        entries.append({
            "latitude": track[idx]["a"],
            "longitude": track[idx]["o"],
            "longtitude": track[idx]["o"],
            "point_id": str(pid),
            "time": int(t_off),
            "distance": "0.0" if d_km < 0.005 else round(d_km, 2),
        })

    # 关键修复: log_data 必须按打卡时间单调递增。
    # 原实现按 order(环线顺序)遍历, 但 idx 是轨迹中实际首个进入打卡半径的位置,
    # 多圈+扰动跑法下两者顺序不一致 → time 乱序 → 服务器判"跑步时间异常"(record_status=23)。
    entries.sort(key=lambda e: e["time"])

    n_bucket = max(2, used // 60 + 1)
    buckets = [0] * n_bucket
    for k, sp in enumerate(steps_per_point):
        b_i = min(n_bucket - 1, int(k * DT / 60))
        buckets[b_i] += sp
    buckets = [max(0, int(round(b))) for b in buckets]
    step_num = int(sum(buckets))
    gyr = _gen_gyro(steps_per_point, rnd)

    return {
        "track": track,
        "log_data": entries,
        "step_info": {"interval": 60, "list": buckets},
        "step_num": step_num,
        "used_time": used,
        "distance_km": dist_km,
        "gyr": gyr,
        "crossings": sorted(e["point_id"] for e in entries),
        "path_pts": len(track),
        "zone_polygon": zone_polygon,
        "checkpoints": order,
    }


def self_check(res, zone_polygon=None, min_checkpoints=3):
    """按武科大校规与反作弊检测规则自检，返回 {rule: (passed, detail)}。"""
    tr = res["track"]
    poly = zone_polygon if zone_polygon is not None else res.get("zone_polygon")
    speeds = [haversine_m(a["a"], a["o"], b_["a"], b_["o"]) / DT for a, b_ in zip(tr, tr[1:])]
    accs = [abs(speeds[i] - speeds[i - 1]) / DT for i in range(1, len(speeds))]
    m = statistics.mean(speeds)
    arr = [x - m for x in speeds]
    den = sum(a * a for a in arr) or 1e-9
    ac1 = sum(arr[i] * arr[i + 1] for i in range(len(arr) - 1)) / den
    dist_km = res["distance_km"]
    pace = res["used_time"] / dist_km if dist_km > 0 else 9e9
    ratio = (dist_km * 1000) / (res["step_num"] * 0.7) if res["step_num"] else 9e9
    in_zone = all(point_in_zone(p["a"], p["o"], poly, 0) for p in tr) if poly else True
    return {
        "max_speed(<=12)": (max(speeds) <= 12.0, f"{max(speeds):.2f} m/s"),
        "max_acc(<=10)": (max(accs) <= 10.0, f"{max(accs):.2f} m/s2"),
        "speed_var(>=0.1)": (statistics.variance(speeds) >= 0.1, f"{statistics.variance(speeds):.2f}"),
        "autocorr1(>=0.3)": (abs(ac1) >= 0.3, f"{ac1:.3f}"),
        "step_ratio(0.4~2.5)": (0.4 <= ratio <= 2.5, f"{ratio:.2f} (steps={res['step_num']})"),
        f"checkpoints(>={min_checkpoints})": (len(res["crossings"]) >= min_checkpoints, f"{len(res['crossings'])} 个打卡点"),
        "pace(180~660)": (WUST_RULES["pace_lo"] <= pace <= WUST_RULES["pace_hi"], f"{int(pace)} s/km"),
        "zone(100% in)": (in_zone, "all points inside zone polygon"),
        "points": (True, f"{len(tr)} pts, {dist_km}km, {res['used_time']}s, pace={int(pace)}s/km"),
    }
