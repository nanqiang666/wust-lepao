# -*- coding: utf-8 -*-
# --- lepao-research-notice v1 (do not remove; see LICENSE) ---
# 乐跑协议研究（Lepao Research） · https://github.com/dan-cun/lepao3
# Copyright (c) 2026 dan-cun · 技术讨论 QQ 1224145544（仅作技术讨论，不提供代打卡）
# 许可证 LRL-1.0（乐跑研究协议 1.0）：仅供学习 · 不可牟利 · 再发布须署名引用原始仓库 · 声明不得删除
# 删除或篡改本块即依 LRL-1.0 第三条自动终止授权；衍生版须继续以 LRL-1.0 授权并标注修改说明。
# --- end lepao-research-notice ---
"""武汉科技大学校园乐跑控制台（tkinter 桌面端）

功能:
  1. 微信 / QQ 官方 OAuth 二维码扫码登录（直接展示二维码图片并轮询授权状态）
  2. api2.lptiyu.com 接口连通性探测与 Token 手动注入/真门检验
  3. 武科大三跑区（沁湖环道 / 南区田径场 / 北区田径场）离线模拟 + Canvas 轨迹可视化
  4. 在线 Dry-Run / 正式提交（带二次确认）
"""
import io
import json
import os
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

_HERE = os.path.dirname(os.path.abspath(__file__))
_LEPAORUN = os.path.join(_HERE, "lepaorun")
if _LEPAORUN not in sys.path:
    sys.path.insert(0, _LEPAORUN)

import driver as DRV  # noqa: E402
from lepao import license_guard as LG  # noqa: E402
from lepao import qr_login as QRL  # noqa: E402
from lepao import wust_track as WT  # noqa: E402

BG = "#0b0f14"
PANEL = "#111922"
CARD = "#16202c"
BORDER = "#22303f"
TXT = "#d9e4ef"
DIM = "#8aa0b6"
OK = "#2dd489"
WARN = "#ffc24b"
ERR = "#ff6b6b"
CYAN = "#3ddad7"
BLUE = "#4f8cff"


class WustApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(
            f"武科大校园乐跑助手 · 基于 {LG.AUTHOR}/lepao3 ({LG.LICENSE_ID} 仅供学习不可牟利)"
        )
        self.root.geometry("960x680")
        self.root.configure(bg=BG)
        self.q = queue.Queue()
        self._qr_photo = None
        self._polling_stop = threading.Event()
        self._build_ui()
        self._pump()
        for ln in LG.attribution_block("[声明] "):
            self._log(ln)

    def _log(self, msg: str):
        self.q.put(("log", msg))

    def _pump(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "log":
                    self.log_box.configure(state="normal")
                    self.log_box.insert("end", f"[{time.strftime('%H:%M:%S')}] {payload}\n")
                    self.log_box.see("end")
                    self.log_box.configure(state="disabled")
                elif kind == "qr_img":
                    self._render_qr_bytes(payload)
                elif kind == "qr_status":
                    self.qr_status_var.set(payload)
                elif kind == "oauth_done":
                    lp = payload.get("lepao") or {}
                    self.oauth_info_var.set(
                        f"已授权并脱机兑换: {payload.get('provider', '').upper()} | "
                        f"姓名={lp.get('name') or payload.get('nickname') or '-'} | "
                        f"学号={lp.get('student_num') or '-'}"
                    )
                    if lp.get("student_num"):
                        self.var_sn.set(str(lp["student_num"]))
                    if lp.get("uid"):
                        self.var_uid.set(str(lp["uid"]))
                    if lp.get("school_id"):
                        self.var_sid.set(str(lp["school_id"]))
                    if lp.get("token"):
                        self.var_tok.set(str(lp["token"]))
                elif kind == "draw_sim":
                    self._draw_track_canvas(payload)
        except queue.Empty:
            pass
        self.root.after(80, self._pump)

    def _build_ui(self):
        # 顶部横幅
        top = tk.Frame(self.root, bg=PANEL, pady=8, padx=14)
        top.pack(fill="x")
        tk.Label(
            top,
            text="武汉科技大学 · 校园乐跑控制台 (WUST)",
            font=("Microsoft YaHei UI", 14, "bold"),
            bg=PANEL,
            fg=CYAN,
        ).pack(side="left")
        tk.Label(
            top,
            text=f"基于 dan-cun/lepao3 & ctbu-lepao · {LG.LICENSE_ID} 非商业研究",
            font=("Microsoft YaHei UI", 9),
            bg=PANEL,
            fg=DIM,
        ).pack(side="right")

        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
            style.configure("TNotebook", background=BG, borderwidth=0)
            style.configure("TNotebook.Tab", background=CARD, foreground=TXT, padding=(14, 6))
            style.map("TNotebook.Tab", background=[("selected", BLUE)], foreground=[("selected", "#fff")])
        except Exception:
            pass

        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=10, pady=(6, 4))

        self.tab_login = tk.Frame(nb, bg=BG)
        self.tab_sim = tk.Frame(nb, bg=BG)
        self.tab_about = tk.Frame(nb, bg=BG)
        nb.add(self.tab_login, text="1. 扫码登录与账号")
        nb.add(self.tab_sim, text="2. 跑区模拟与提交")
        nb.add(self.tab_about, text="3. 关于与 LRL-1.0 声明")

        self._build_login_tab()
        self._build_sim_tab()
        self._build_about_tab()

        # 底部共用日志框
        log_frame = tk.Frame(self.root, bg=PANEL)
        log_frame.pack(fill="x", padx=10, pady=(0, 8))
        tk.Label(log_frame, text="运行日志:", bg=PANEL, fg=DIM, font=("Microsoft YaHei UI", 9)).pack(
            anchor="w", padx=6, pady=(4, 0)
        )
        self.log_box = tk.Text(
            log_frame, height=8, bg="#070a0e", fg="#a5d6a7", font=("Consolas", 9), state="disabled", bd=0
        )
        self.log_box.pack(fill="x", padx=6, pady=6)

    # ---------------- Tab 1: 扫码登录 ----------------
    def _build_login_tab(self):
        left = tk.Frame(self.tab_login, bg=PANEL, padx=14, pady=12)
        left.pack(side="left", fill="both", expand=True, padx=(4, 4), pady=6)

        tk.Label(left, text="微信 / QQ 官方授权扫码", bg=PANEL, fg=TXT, font=("Microsoft YaHei UI", 11, "bold")).pack(
            anchor="w", pady=(0, 8)
        )
        btn_row = tk.Frame(left, bg=PANEL)
        btn_row.pack(fill="x", pady=4)
        tk.Button(
            btn_row, text="微信扫码登录", command=lambda: self._start_qr("wx"),
            bg="#07c160", fg="#fff", font=("Microsoft YaHei UI", 10, "bold"), relief="flat", padx=14, pady=6, cursor="hand2"
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            btn_row, text="QQ 扫码登录", command=lambda: self._start_qr("qq"),
            bg=BLUE, fg="#fff", font=("Microsoft YaHei UI", 10, "bold"), relief="flat", padx=14, pady=6, cursor="hand2"
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            btn_row, text="脱机兑换 Token", command=self._exchange_existing_oauth,
            bg=CARD, fg=OK, font=("Microsoft YaHei UI", 10, "bold"), relief="flat", padx=12, pady=6, cursor="hand2"
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            btn_row, text="测试线上连通性", command=self._probe_online,
            bg=CARD, fg=CYAN, font=("Microsoft YaHei UI", 10), relief="flat", padx=12, pady=6, cursor="hand2"
        ).pack(side="left")

        self.oauth_info_var = tk.StringVar(value="当前 OAuth 状态: 未扫码")
        tk.Label(left, textvariable=self.oauth_info_var, bg=PANEL, fg=WARN, font=("Microsoft YaHei UI", 9)).pack(
            anchor="w", pady=(10, 8)
        )

        # 手动 Token / 账号配置区
        tk.Label(left, text="账号配置（可扫码/抓包自动回填，或手动填入）", bg=PANEL, fg=TXT,
                 font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w", pady=(8, 4))

        cfg = DRV.load_config()
        accs = cfg.get("accounts") or {}
        ak = cfg.get("active") if cfg.get("active") in accs else (list(accs.keys())[0] if accs else "")
        cur = accs.get(ak, {})

        self.var_sn = tk.StringVar(value=str(cur.get("student_num", "")))
        self.var_uid = tk.StringVar(value=str(cur.get("uid", "")))
        self.var_sid = tk.StringVar(value=str(cur.get("school_id", "")))
        self.var_tok = tk.StringVar(value=str((cur.get("auth") or {}).get("token", "")))

        for lbl, var in [("学号:", self.var_sn), ("UID:", self.var_uid), ("学校ID:", self.var_sid), ("Token:", self.var_tok)]:
            r = tk.Frame(left, bg=PANEL)
            r.pack(fill="x", pady=3)
            tk.Label(r, text=lbl, width=8, anchor="w", bg=PANEL, fg=DIM, font=("Microsoft YaHei UI", 9)).pack(side="left")
            tk.Entry(r, textvariable=var, bg=CARD, fg=TXT, insertbackground=TXT, relief="flat", font=("Consolas", 9)).pack(
                side="left", fill="x", expand=True, ipady=4
            )

        act_row = tk.Frame(left, bg=PANEL)
        act_row.pack(fill="x", pady=10)
        tk.Button(
            act_row, text="保存账号配置", command=self._save_account_cfg,
            bg=CARD, fg=OK, font=("Microsoft YaHei UI", 9, "bold"), relief="flat", padx=12, pady=5, cursor="hand2"
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            act_row, text="真门探测 Token", command=self._probe_token,
            bg=CARD, fg=CYAN, font=("Microsoft YaHei UI", 9, "bold"), relief="flat", padx=12, pady=5, cursor="hand2"
        ).pack(side="left")

        right = tk.Frame(self.tab_login, bg=PANEL, width=310, padx=14, pady=12)
        right.pack(side="right", fill="y", padx=(4, 4), pady=6)
        right.pack_propagate(False)
        tk.Label(right, text="授权二维码", bg=PANEL, fg=TXT, font=("Microsoft YaHei UI", 11, "bold")).pack(pady=(0, 8))
        self.qr_label = tk.Label(right, text="点击左侧\n「微信扫码登录」或「QQ 扫码登录」\n获取官方授权二维码",
                                 bg=CARD, fg=DIM, width=30, height=13, font=("Microsoft YaHei UI", 9))
        self.qr_label.pack(pady=6)
        self.qr_status_var = tk.StringVar(value="就绪")
        tk.Label(right, textvariable=self.qr_status_var, bg=PANEL, fg=OK, wraplength=270, font=("Microsoft YaHei UI", 9)).pack(
            pady=8
        )

    # ---------------- Tab 2: 模拟与运行 ----------------
    def _build_sim_tab(self):
        ctrl = tk.Frame(self.tab_sim, bg=PANEL, padx=12, pady=10)
        ctrl.pack(side="left", fill="y", padx=(4, 4), pady=6)

        tk.Label(ctrl, text="跑区与规程参数", bg=PANEL, fg=TXT, font=("Microsoft YaHei UI", 11, "bold")).pack(
            anchor="w", pady=(0, 8)
        )
        tk.Label(ctrl, text="选择武科大跑区:", bg=PANEL, fg=DIM, font=("Microsoft YaHei UI", 9)).pack(anchor="w")
        self.zone_var = tk.StringVar(value="qinhu")
        for k, z in WT.WUST_ZONES.items():
            tk.Radiobutton(
                ctrl, text=f"{z['name']} ({k})", variable=self.zone_var, value=k,
                bg=PANEL, fg=TXT, selectcolor=CARD, activebackground=PANEL, activeforeground=CYAN,
                font=("Microsoft YaHei UI", 9)
            ).pack(anchor="w", pady=2)

        tk.Label(ctrl, text="性别距离标准:", bg=PANEL, fg=DIM, font=("Microsoft YaHei UI", 9)).pack(anchor="w", pady=(10, 2))
        self.gender_var = tk.StringVar(value="male")
        g_row = tk.Frame(ctrl, bg=PANEL)
        g_row.pack(fill="x")
        tk.Radiobutton(
            g_row, text="男生 (>=2.5km)", variable=self.gender_var, value="male",
            bg=PANEL, fg=TXT, selectcolor=CARD, activebackground=PANEL, font=("Microsoft YaHei UI", 9)
        ).pack(side="left")
        tk.Radiobutton(
            g_row, text="女生 (>=2.0km)", variable=self.gender_var, value="female",
            bg=PANEL, fg=TXT, selectcolor=CARD, activebackground=PANEL, font=("Microsoft YaHei UI", 9)
        ).pack(side="left", padx=(8, 0))

        tk.Button(
            ctrl, text="▶ 离线模拟跑（零风险自检）", command=self._run_offline_sim,
            bg=BLUE, fg="#fff", font=("Microsoft YaHei UI", 10, "bold"), relief="flat", pady=8, cursor="hand2"
        ).pack(fill="x", pady=(16, 6))
        tk.Button(
            ctrl, text="在线 Dry-Run（真门+官方跑区）", command=lambda: self._run_online(False),
            bg=CARD, fg=CYAN, font=("Microsoft YaHei UI", 10), relief="flat", pady=7, cursor="hand2"
        ).pack(fill="x", pady=4)
        tk.Button(
            ctrl, text="正式提交跑步记录 (--submit)", command=lambda: self._run_online(True),
            bg=CARD, fg=WARN, font=("Microsoft YaHei UI", 10), relief="flat", pady=7, cursor="hand2"
        ).pack(fill="x", pady=4)

        self.sim_summary_var = tk.StringVar(value="点击「离线模拟跑」查看轨迹与 8 项反作弊自检结果")
        tk.Label(ctrl, textvariable=self.sim_summary_var, bg=PANEL, fg=OK, wraplength=240, justify="left",
                 font=("Microsoft YaHei UI", 9)).pack(anchor="w", pady=(12, 0))

        right = tk.Frame(self.tab_sim, bg=PANEL, padx=10, pady=10)
        right.pack(side="right", fill="both", expand=True, padx=(4, 4), pady=6)
        tk.Label(right, text="跑区围栏 / 打卡点 / 模拟轨迹预览", bg=PANEL, fg=TXT,
                 font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w")
        self.canvas = tk.Canvas(right, bg="#070a0e", highlightthickness=1, highlightbackground=BORDER)
        self.canvas.pack(fill="both", expand=True, pady=(6, 0))

    # ---------------- Tab 3: 关于 ----------------
    def _build_about_tab(self):
        rows = LG.attribution_block() + [
            "",
            "衍生修改说明：",
            "  - 参考仓库：https://github.com/2422725977/ctbu-lepao",
            "  - 本项目面向武汉科技大学（WUST）进行学校规则、三跑区自适应（沁湖/南区/北区）、",
            "    微信/QQ 官方 OAuth 扫码登录与 Windows 桌面图形化控制台适配。",
            "",
            "许可与风险声明（LRL-1.0）：",
            "  1) 仅供协议研究与个人学习，严禁任何商业牟利与代打卡服务。",
            "  2) 本工具按「现状」提供，使用风险由使用者自行承担。",
        ]
        txt = tk.Text(self.tab_about, bg="#070a0e", fg=TXT, font=("Consolas", 10), bd=0, wrap="word")
        txt.insert("1.0", "\n".join(rows))
        txt.configure(state="disabled")
        txt.pack(fill="both", expand=True, padx=12, pady=12)

    # ---------------- 业务逻辑 ----------------
    def _render_qr_bytes(self, png_bytes: bytes):
        img = Image.open(io.BytesIO(png_bytes)).resize((220, 220), Image.Resampling.NEAREST)
        self._qr_photo = ImageTk.PhotoImage(img)
        self.qr_label.configure(image=self._qr_photo, text="", width=220, height=220)

    def _start_qr(self, mode: str):
        self._polling_stop.set()
        time.sleep(0.1)
        self._polling_stop = threading.Event()
        stop_ev = self._polling_stop

        def worker():
            try:
                if mode == "wx":
                    self.q.put(("qr_status", "正在向微信开放平台请求二维码…"))
                    cli = QRL.WeChatQRLogin()
                    info = cli.create_qr()
                    self.q.put(("qr_img", info["png_bytes"]))
                    self.q.put(("qr_status", f"请用微信扫码（授权：{info['appname']}）"))
                    self._log(f"[微信扫码] 已生成二维码 {info['qr_url']}")
                    last = ""
                    t0 = time.time()
                    while not stop_ev.is_set() and time.time() - t0 < 180:
                        st, payload = cli.poll_once(last_code=last)
                        if st == "scanned":
                            last = "404"
                            self.q.put(("qr_status", "已扫码，请在手机微信点击「允许」…"))
                        elif st == "confirmed":
                            res = cli.exchange_code(payload.get("wx_code", ""))
                            self.q.put(("qr_status", "微信授权成功，正在脱机兑换乐跑 Token…"))
                            lp = QRL.exchange_lepao_token(res, sync_config=True)
                            res["lepao"] = lp
                            self.q.put(("qr_status", f"脱机兑换成功! 姓名={lp['name']} 学号={lp['student_num']}"))
                            self.q.put(("oauth_done", res))
                            self._log(
                                f"[微信脱机兑换] 成功! 姓名={lp['name']} 学号={lp['student_num']} "
                                f"uid={lp['uid']} school_id={lp['school_id']} token={lp['token'][:10]}…"
                            )
                            return
                        elif st in ("cancelled", "expired"):
                            self.q.put(("qr_status", f"二维码状态: {st}，请重新获取"))
                            return
                        time.sleep(1.5)
                else:
                    self.q.put(("qr_status", "正在向 QQ 互联请求二维码…"))
                    cli = QRL.QQQRLogin()
                    info = cli.create_qr()
                    self.q.put(("qr_img", info["png_bytes"]))
                    self.q.put(("qr_status", f"请用手机 QQ 扫码（AppID={info['client_id']}）"))
                    self._log(f"[QQ扫码] 已生成二维码 (AppID={info['client_id']})")
                    t0 = time.time()
                    while not stop_ev.is_set() and time.time() - t0 < 180:
                        st, payload = cli.poll_once()
                        if st == "scanned":
                            self.q.put(("qr_status", "已扫码，请在手机 QQ 确认登录…"))
                        elif st == "confirmed":
                            res = cli.exchange_oauth(payload.get("jump_url", ""), payload.get("nickname", ""))
                            self.q.put(("qr_status", "QQ 授权成功，正在脱机兑换乐跑 Token…"))
                            lp = QRL.exchange_lepao_token(res, sync_config=True)
                            res["lepao"] = lp
                            self.q.put(("qr_status", f"脱机兑换成功! 姓名={lp['name']} 学号={lp['student_num']}"))
                            self.q.put(("oauth_done", res))
                            self._log(
                                f"[QQ脱机兑换] 成功! 姓名={lp['name']} 学号={lp['student_num']} "
                                f"uid={lp['uid']} school_id={lp['school_id']} token={lp['token'][:10]}…"
                            )
                            return
                        elif st in ("expired", "error"):
                            self.q.put(("qr_status", f"QQ 扫码失败: {payload}"))
                            return
                        time.sleep(2.0)
            except Exception as e:
                self.q.put(("qr_status", f"出码/轮询失败: {e}"))
                self._log(f"[QR错误] {e}")

        threading.Thread(target=worker, daemon=True).start()

    def _exchange_existing_oauth(self):
        def worker():
            try:
                sess = QRL.load_oauth_session()
                if not sess.get("openid"):
                    self._log("[脱机兑换] state/oauth_session.json 暂无 OAuth 凭据，请先点击微信或 QQ 扫码登录")
                    return
                lp = QRL.exchange_lepao_token(sess, sync_config=True)
                sess["lepao"] = lp
                self.q.put(("oauth_done", sess))
                self.q.put(("qr_status", f"脱机兑换成功! 姓名={lp['name']} 学号={lp['student_num']}"))
                self._log(
                    f"[脱机兑换] 成功! 姓名={lp['name']} 学号={lp['student_num']} "
                    f"uid={lp['uid']} school={lp['school_name']}({lp['school_id']}) token={lp['token'][:10]}…"
                )
            except Exception as e:
                self._log(f"[脱机兑换失败] {e}")

        threading.Thread(target=worker, daemon=True).start()

    def _probe_online(self):
        def worker():
            try:
                res = DRV.probe_host("api2.lptiyu.com")
                self._log(f"[线上探测] api2.lptiyu.com System/getIp -> {res}")
            except Exception as e:
                self._log(f"[线上探测失败] {e}")

        threading.Thread(target=worker, daemon=True).start()

    def _save_account_cfg(self):
        sn = self.var_sn.get().strip() or "wust_user"
        uid = int(self.var_uid.get().strip() or 0)
        sid = int(self.var_sid.get().strip() or 0)
        tok = self.var_tok.get().strip()
        cfg = DRV.load_config()
        accs = cfg.setdefault("accounts", {})
        acc = accs.setdefault(sn, {
            "uid": uid, "school_id": sid, "student_num": sn, "card_id": sn,
            "name": sn, "alias": sn, "enabled": True, "policy": {}, "auth": {},
        })
        acc["uid"] = uid
        acc["school_id"] = sid
        acc.setdefault("auth", {})["token"] = tok
        acc["auth"]["consumed_at"] = ""
        cfg["active"] = sn
        with open(DRV.CFG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        self._log(f"[配置] 已保存账号 {sn} (uid={uid}, school_id={sid}) 至 {DRV.CFG_PATH}")

    def _probe_token(self):
        self._save_account_cfg()

        def worker():
            try:
                cfg = DRV.load_config()
                ak = cfg["active"]
                acc = DRV.Account(cfg["accounts"][ak], cfg)
                if not acc.token:
                    self._log("[真门] 未填写 token")
                    return
                c = acc.make_client()
                r = c.get_term_list()
                if isinstance(r, dict) and r.get("status") == 101:
                    self._log("[真门] 返回 status=101，token 已失效")
                else:
                    s = c.get_school_info()
                    self._log(f"[真门] token 有效! 学校={s.get('school_name')} 学期数={len(r) if isinstance(r, list) else r}")
            except Exception as e:
                self._log(f"[真门异常] {e}")

        threading.Thread(target=worker, daemon=True).start()

    def _run_offline_sim(self):
        zk = self.zone_var.get()
        gender = self.gender_var.get()

        def worker():
            try:
                out, code = DRV.simulate_wust(zone_key=zk, gender=gender)
                self._log(
                    f"[离线模拟] {out['zone_name']} ({out['gender']}) -> "
                    f"{out['distance_km']}km / {out['used_time']}s / 配速={out['pace_s_per_km']}s/km / "
                    f"步数={out['step_num']} / 打卡点={len(out['crossings'])} / 加密自验={out['crypto_roundtrip_ok']}"
                )
                for k, v in out["self_check"].items():
                    self._log(f"  自检 {k}: {'PASS' if v['passed'] else 'FAIL'} ({v['detail']})")
                self.sim_summary_var.set(
                    f"跑区: {out['zone_name']}\n距离: {out['distance_km']} km\n"
                    f"用时: {out['used_time']} s (配速 {out['pace_s_per_km']} s/km)\n"
                    f"步数: {out['step_num']} | 打卡点: {len(out['crossings'])}\n"
                    f"开放状态: {'开放中' if out['open_now'] else '非开放时段'}"
                )
                self.q.put(("draw_sim", out))
            except Exception as e:
                self._log(f"[离线模拟失败] {e}")

        threading.Thread(target=worker, daemon=True).start()

    def _draw_track_canvas(self, out: dict):
        c = self.canvas
        c.delete("all")
        w = max(320, c.winfo_width())
        h = max(240, c.winfo_height())
        poly = out.get("zone_polygon") or []
        pts = out.get("track") or []
        cps = out.get("checkpoints") or []
        all_lats = [p[1] for p in poly] + [p["a"] for p in pts] + [cp[0] for cp in cps]
        all_lngs = [p[0] for p in poly] + [p["o"] for p in pts] + [cp[1] for cp in cps]
        if not all_lats or not all_lngs:
            return
        lat_min, lat_max = min(all_lats), max(all_lats)
        lng_min, lng_max = min(all_lngs), max(all_lngs)
        d_lat = max(lat_max - lat_min, 1e-5)
        d_lng = max(lng_max - lng_min, 1e-5)
        pad = 24

        def to_xy(lat, lng):
            x = pad + (lng - lng_min) / d_lng * (w - 2 * pad)
            y = h - pad - (lat - lat_min) / d_lat * (h - 2 * pad)
            return x, y

        if len(poly) >= 3:
            coords = []
            for lng, lat in poly:
                coords.extend(to_xy(lat, lng))
            c.create_polygon(*coords, outline=WARN, fill="", dash=(4, 4), width=1.5)

        if len(pts) >= 2:
            line_coords = []
            for p in pts:
                line_coords.extend(to_xy(p["a"], p["o"]))
            c.create_line(*line_coords, fill=CYAN, width=2)
            sx, sy = to_xy(pts[0]["a"], pts[0]["o"])
            ex, ey = to_xy(pts[-1]["a"], pts[-1]["o"])
            c.create_oval(sx - 5, sy - 5, sx + 5, sy + 5, fill=OK, outline="#fff")
            c.create_oval(ex - 5, ey - 5, ex + 5, ey + 5, fill=BLUE, outline="#fff")

        for idx, cp in enumerate(cps, 1):
            cx, cy = to_xy(cp[0], cp[1])
            c.create_oval(cx - 6, cy - 6, cx + 6, cy + 6, fill=ERR, outline="#fff")
            c.create_text(cx + 12, cy - 10, text=f"P{idx}", fill=TXT, font=("Consolas", 9, "bold"))

    def _run_online(self, submit: bool):
        if submit and not messagebox.askyesno("确认提交", "确定要向服务器真实提交一次跑步记录吗？"):
            return
        self._save_account_cfg()
        gender = self.gender_var.get()

        def worker():
            try:
                cfg = DRV.load_config()
                ak = cfg.get("active")
                if not ak or ak not in (cfg.get("accounts") or {}):
                    self._log("[在线运行] 未配置账号")
                    return
                acc = DRV.Account(cfg["accounts"][ak], cfg)
                acc.gender = gender
                summary, code = DRV.run_for_account(acc, submit=submit)
                self._log(f"[在线运行] EXIT={code} summary={json.dumps(summary, ensure_ascii=False)}")
            except Exception as e:
                self._log(f"[在线运行异常] {e}")

        threading.Thread(target=worker, daemon=True).start()


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        print(json.dumps({"license": LG.summary(), "zones": list(WT.WUST_ZONES.keys())}, ensure_ascii=False))
        sys.exit(0)
    root = tk.Tk()
    WustApp(root)
    root.mainloop()
