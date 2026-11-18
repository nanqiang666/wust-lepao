# -*- coding: utf-8 -*-
# --- lepao-research-notice v1 (do not remove; see LICENSE) ---
# 乐跑协议研究（Lepao Research） · https://github.com/dan-cun/lepao3
# Copyright (c) 2026 dan-cun · 技术讨论 QQ 1224145544（仅作技术讨论，不提供代打卡）
# 许可证 LRL-1.0（乐跑研究协议 1.0）：仅供学习 · 不可牟利 · 再发布须署名引用原始仓库 · 声明不得删除
# 删除或篡改本块即依 LRL-1.0 第三条自动终止授权；衍生版须继续以 LRL-1.0 授权并标注修改说明。
# --- end lepao-research-notice ---
# Copyright (c) 2026 dan-cun · 许可协议见项目根目录 LICENSE
"""lepao.capture_photo —— 抓拍照片内容提供与上传

背景:
  武科大沁湖环道跑区(game_id=1963)是强制抓拍跑区, beforeRunV260 返回
  is_capture_zone=1 / is_register_face=1 / capture_config.config[0].day_capture_num="1"。
  提交 stopRun 时 record_img/file_img 若为空, 服务器判 record_status=53
  "抓拍数量不符合要求，未达到合格标准", 不计成绩。

  本模块提供抓拍照片内容(优先本地真实照片, 否则生成合法占位 PNG)与上传。
"""
import io
import os

try:
    from PIL import Image, ImageGrab
except ImportError:
    Image = None
    ImageGrab = None

# 环境变量: 抓拍照片本地文件路径(优先使用真实照片)
_PHOTO_ENV = "LEPAO_CAPTURE_PHOTO"


def screen_shot_bytes(quality=80):
    """截取电脑当前屏幕, 转成 JPEG bytes(手机拍照同为 JPEG, 更接近真实抓拍)。
    返回 (bytes, source) 或 (None, "") 失败时。
    """
    if ImageGrab is None:
        return None, ""
    try:
        img = ImageGrab.grab()
        if img is None:
            return None, ""
        if img.mode != "RGB":
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        return buf.getvalue(), f"screenshot:{img.width}x{img.height}"
    except Exception as e:
        return None, f"error:{e}"


def load_capture_photo_bytes(photo_path=None):
    """返回抓拍照片字节(bytes)与来源说明(str)。

    优先级:
      1. 显式 photo_path 参数(存在的本地文件)
      2. 环境变量 LEPAO_CAPTURE_PHOTO 指定的本地文件
      3. 电脑屏幕截图(真实内容, JPEG, 最接近真实抓拍)
      4. Pillow 生成一张合法占位 PNG(640x480, 带随机噪点)
    """
    cand = photo_path or os.environ.get(_PHOTO_ENV, "")
    if cand and os.path.isfile(cand):
        with open(cand, "rb") as f:
            return f.read(), f"local:{cand}"

    # 电脑屏幕截图(优先于占位图)
    shot, src = screen_shot_bytes()
    if shot:
        return shot, src

    if Image is None:
        # 无 Pillow: 返回一张 1x1 合法 PNG(极小占位, 仍是非空合法 PNG)
        png = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
               b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDAT"
               b"\x08\xd7c\xf8\xcf\xc0\xf0\x1f\x00\x05\x00\x01\xff\xff\xff"
               b"\x00\x00\x00\x00IEND\xaeB`\x82")
        return png, "builtin:1x1"

    import random as _rnd
    rnd = _rnd.Random()
    w, h = 640, 480
    img = Image.new("RGB", (w, h))
    px = img.load()
    base_r = rnd.randint(40, 180)
    base_g = rnd.randint(40, 180)
    base_b = rnd.randint(40, 180)
    for y in range(h):
        for x in range(w):
            v = int((x / w) * 60) + rnd.randint(-18, 18)
            px[x, y] = (
                max(0, min(255, base_r + v)),
                max(0, min(255, base_g + v)),
                max(0, min(255, base_b + v)),
            )
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue(), "generated:640x480"


def capture_photo_for_submit(sts, photo_path=None, rnd=None):
    """提交链调用入口: 取照片内容 → 上传 OSS → 返回 (status, rel_path, source)。

    rel_path 为 stopRun file_img 字段应填的纯路径(对齐 record_file 纯路径规律)。
    失败不抛异常, 返回 (None, "", 原因), 由调用方决定是否降级(不中断提交)。
    """
    from . import record as REC
    try:
        photo_bytes, src = load_capture_photo_bytes(photo_path)
        status, rel_path, url, body = REC.upload_capture_photo(sts, photo_bytes, rnd=rnd)
        return status, rel_path, src
    except Exception as e:
        return None, "", f"error:{e}"
