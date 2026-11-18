# -*- coding: utf-8 -*-
"""武科大乐跑自动打卡 tick：由系统计划任务/cron 每 5 分钟触发一次。

窗口对齐《武汉科技大学课外环湖健康跑规程》三个跑区共同开放时段:
  - morning: 06:15 - 07:20
  - noon:    12:05 - 13:50
  - evening: 20:05 - 22:40
"""
import datetime
import hashlib
import json
import os
import random
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)

if sys.platform == "win32":
    _VENV_PY = os.path.join(_ROOT, ".venv", "Scripts", "python.exe")
else:
    _VENV_PY = os.path.join(_ROOT, ".venv", "bin", "python")
PY = _VENV_PY if os.path.isfile(_VENV_PY) else sys.executable
DRIVER = os.path.join(_ROOT, "lepaorun", "driver.py")
STATE = os.path.join(_ROOT, "state", "auto_state.json")
LOGDIR = os.path.join(_ROOT, "logs")

WINDOWS = {
    "morning": (6, 15, 7, 20),
    "noon": (12, 5, 13, 50),
    "evening": (20, 5, 22, 40),
}


def log(msg):
    os.makedirs(LOGDIR, exist_ok=True)
    with open(os.path.join(LOGDIR, f"tick_{datetime.date.today():%Y%m%d}.log"), "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now():%H:%M:%S} {msg}\n")


def load_state():
    try:
        with open(STATE, encoding="utf-8") as f:
            st = json.load(f)
    except Exception:
        st = {}
    if st.get("date") != str(datetime.date.today()):
        st = {"date": str(datetime.date.today()), "done": False, "dead_notified": False}
    return st


def save_state(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)


def target_minutes(win, date_str):
    h0, m0, h1, m1 = WINDOWS[win]
    lo, hi = h0 * 60 + m0, h1 * 60 + m1
    seed = int(hashlib.sha256(f"{date_str}|{win}|wust_lepao".encode()).hexdigest()[:12], 16)
    return random.Random(seed).randint(lo, max(lo, hi - 5))


def current_window(now_min):
    for name, (h0, m0, h1, m1) in WINDOWS.items():
        if h0 * 60 + m0 <= now_min <= h1 * 60 + m1:
            return name
    return None


def main():
    now = datetime.datetime.now()
    win = current_window(now.hour * 60 + now.minute)
    if win is None:
        return
    st = load_state()
    if st.get("done") or st.get("dead_notified"):
        return

    tgt = target_minutes(win, st["date"])
    st.setdefault("targets", {})[win] = f"{tgt // 60:02d}:{tgt % 60:02d}"
    save_state(st)
    if (now.hour * 60 + now.minute) < tgt and os.environ.get("LEPAO_FORCE") != "1":
        log(f"{win} tick: 等待随机时刻 {st['targets'][win]}")
        return

    p = subprocess.run([PY, DRIVER, "--submit"], cwd=os.path.dirname(DRIVER),
                       capture_output=True, text=True, timeout=420)
    out = p.stdout
    code = p.returncode
    log(f"{win}: exit={code} tail={out[-240:]}")
    st["last_run"] = now.strftime("%Y-%m-%d %H:%M")
    st["last_exit"] = code

    if code == 2 or "TOKEN_DEAD" in out or "TOKEN_MISSING" in out:
        st["dead_notified"] = True
        save_state(st)
        print("⚠️ 武科大乐跑自动打卡：token 已失效/缺失，请重新扫码或抓包。")
        return
    if code == 3:
        st["done"] = True
        save_state(st)
        return
    if code == 0:
        st["done"] = True
        save_state(st)
        print(f"🏃 武科大乐跑自动打卡完成 ({now:%m-%d %H:%M})")


if __name__ == "__main__":
    main()
