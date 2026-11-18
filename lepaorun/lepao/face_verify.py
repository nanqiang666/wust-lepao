# -*- coding: utf-8 -*-
# --- lepao-research-notice v1 (do not remove; see LICENSE) ---
# 乐跑协议研究（Lepao Research） · https://github.com/dan-cun/lepao3
# Copyright (c) 2026 dan-cun · 技术讨论 QQ 1224145544（仅作技术讨论，不提供代打卡）
# 许可证 LRL-1.0（乐跑研究协议 1.0）：仅供学习 · 不可牟利 · 再发布须署名引用原始仓库 · 声明不得删除
# 删除或篡改本块即依 LRL-1.0 第三条自动终止授权；衍生版须继续以 LRL-1.0 授权并标注修改说明。
# --- end lepao-research-notice ---
"""lepao.face_verify —— 跑步人脸抓拍（faceVerify）协议闭环

逆向实证（classes.dex 反编译，2026-11-18）:
  - 武科大（school_id=61）三跑区全部 is_capture_zone=1 + is_register_face=1，
    day_capture_num=1，即每天跑步必须完成 1 次人脸抓拍，否则 stopRun 判
    record_status=0 / record_failed_reason="抓拍数量不符合要求，未达到合格标准"。
  - capture_num 的累计机制：客户端在跑步过程中调用 Run2/faceVerify（带 face_file
    人脸照片），服务器返回 run_face_verify_id；stopRun 提交时带上该 id，服务器据此
    累计 capture_num。
  - faceVerify 正确字段（CameraActivity 反编译实证）:
      * face_file   —— 人脸照片 base64（不是 face_img！）
      * type        —— 1=开始 / 2=中途 / 3=结束（与 start/middle/stop_face_verify 对应）
      * run_face_verify_id —— 上一次验证会话 id（首次可空）
  - stopRun 正确字段（school_run_record_detail/d 反编译实证）:
      * run_face_verify_id —— 最后一次 faceVerify 返回的 id（兜底默认 "1231231231231"）
      * is_timeout_zfb      —— 是否支付宝人脸超时（0/1）

  实测结论（2026-11-18 17:34 真人自拍 OnePlus 15 前摄，原图/152KB/59KB/36KB 四档）:
  - 全部返回 status=1 info="人脸验证错误，请稍后重试！" → 不是图片大小/清晰度问题。
  - dex 里有 startFaceVerifyCountdown / DialogFaceVerifyCountdownBinding（倒计时）、
    checkFaceVerifyVibrate（震动）、handleFaceVerifyTimeout → App 端是真机前置
    摄像头实时活体检测（动作指令），服务器校验拍摄即时性，静态照片过不了。
  - 纯协议无法伪造；走真机 App 人脸是唯一通道，或改判 is_capture_zone 的学校配置。
"""
import base64
import os

# 环境变量: 真人脸照片本地文件路径（必须是人脸！屏幕截图/非人脸都会被拒）
_FACE_PHOTO_ENV = "LEPAO_FACE_PHOTO"

# faceVerify type 语义（与 LocalDirectionRunRecord 的 start/middle/stop 对应）
TYPE_START = "1"
TYPE_MIDDLE = "2"
TYPE_STOP = "3"


def load_face_bytes(photo_path=None):
    """加载真人脸照片字节。优先级: 显式路径 > 环境变量 LEPAO_FACE_PHOTO。
    返回 (bytes, source) 或 (None, "")。"""
    cand = photo_path or os.environ.get(_FACE_PHOTO_ENV, "")
    if cand and os.path.isfile(cand):
        with open(cand, "rb") as f:
            return f.read(), f"local:{cand}"
    if not cand:
        return None, "no-face-photo(未配置 LEPAO_FACE_PHOTO)"
    return None, f"missing:{cand}"


def face_verify(client, photo_path=None, ftype=TYPE_START, game_id="2448",
                run_face_verify_id=None, start_time=None):
    """调用 Run2/faceVerify，返回 (status, run_face_verify_id, info)。
    成功 status=1 时返回的 run_face_verify_id 用于 stopRun 提交。"""
    photo_bytes, src = load_face_bytes(photo_path)
    if not photo_bytes:
        return None, None, src
    params = {
        "type": ftype,
        "game_id": game_id,
        "face_file": base64.b64encode(photo_bytes).decode(),
    }
    if run_face_verify_id:
        params["run_face_verify_id"] = run_face_verify_id
    if start_time:
        params["start_time"] = str(start_time)
    r = client.post("/v3/api.php/Run2/faceVerify", params)
    status = r.get("status") if isinstance(r, dict) else None
    info = str(r.get("info") or "") if isinstance(r, dict) else ""
    data = r.get("data") if isinstance(r, dict) else None
    vid = None
    if isinstance(data, dict):
        vid = data.get("run_face_verify_id")
    return status, vid, info


def attach_face_to_stoprun(g: dict, face_verify_id: str = None, is_timeout_zfb: int = 0):
    """把 faceVerify 结果挂到 stopRun 业务参数（幂等，缺失时用兜底默认）。"""
    g["run_face_verify_id"] = face_verify_id or "1231231231231"
    g["is_timeout_zfb"] = int(is_timeout_zfb)
    return g
