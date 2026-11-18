# 武汉科技大学（WUST）校园乐跑协议适配工具

> **出处署名（LRL-1.0 要求，不可删除）**
> 本项目是基于 **dan-cun / Lepao Research（乐跑协议研究）** 与 **2422725977 / ctbu-lepao** 的衍生适配版：
> - 原作者：**dan-cun**，原始仓库：https://github.com/dan-cun/lepao3
> - 参考衍生仓：https://github.com/2422725977/ctbu-lepao
> - 原许可：**乐跑研究协议 1.0（LRL-1.0）** —— 本项目继续以 **LRL-1.0** 授权，仅限个人学习与协议研究，**严禁任何商业用途与收费代打卡**。
>
> **相对上游修改说明**：
> 1. 将学校规则与跑区适配为**武汉科技大学（WUST）**（依据《2026-2027 学年第一学期课外环湖健康跑规程》：沁湖环道跑区、南区田径场跑区、北区田径场跑区；男生 ≥2.5km / 女生 ≥2.0km；≥3 个打卡点；配速 3–11 min/km；外网生产服 `api2.lptiyu.com`）；
> 2. 新增 `lepaorun/lepao/wust_track.py`：支持在线自动读取 `beforeRunV260.run_zone_latlng` 官方电子围栏，并提供黄家湖校区三跑区离线模拟与 8 项反作弊自检；
> 3. 新增 `lepaorun/lepao/qr_login.py` 与 `qr_login.py`：接入步道乐跑官方 App（`com.lptiyu.tanke`）的**微信开放平台 SDK 扫码登录（`wx5a2e1ff396785475`）**与 **QQ 互联扫码登录（`1105660458`）**；
> 4. 新增 Windows 桌面图形化控制台 `wust_panel.py` 与双击入口 `启动武科大乐跑.bat`（内置二维码展示与跑区轨迹预览画布），并移除 `/tmp` 硬编码；
> 5. 适配 `driver.py --simulate`（离线模拟）、`--probe-host`（线上接口探测）、`capture/token_addon.py` 与 `automation/`。
>
> **风险自负**：按「现状（AS IS）」提供，无任何担保。账号限制、成绩作废等后果由使用者自行承担。完整条款见 `lepaorun/LICENSE`。

---

## 快速开始

### 1. 环境准备

```bash
python -m venv .venv
.venv\Scripts\pip install pycryptodome requests pillow qrcode
```

### 2. 图形化控制台（推荐）

直接双击 **`启动武科大乐跑.bat`**，或运行：

```bash
.venv\Scripts\python.exe wust_panel.py
```

在界面中可直接使用：
- **微信扫码登录 / QQ 扫码登录**：直接显示官方授权二维码并轮询获取 `openid / unionid / 昵称`
- **测试线上接口连通性**：探测 `api2.lptiyu.com` 服务状态
- **离线模拟跑**：选择「沁湖环道跑区 / 南区田径场跑区 / 北区田径场跑区」与男女生标准，生成反检测轨迹并在右侧画布实时绘制电子围栏、打卡点与路线图

### 3. 命令行用法

```bash
# ① 实测线上接口连通性
.venv\Scripts\python.exe lepaorun/driver.py --probe-host

# ② 离线模拟跑（零联网，测试武科大三跑区与防封自检）
.venv\Scripts\python.exe lepaorun/driver.py --simulate --zone qinhu --gender male
.venv\Scripts\python.exe lepaorun/driver.py --simulate --zone south_track --gender female

# ③ 微信 / QQ 二维码扫码登录
.venv\Scripts\python.exe qr_login.py --wx
.venv\Scripts\python.exe qr_login.py --qq

# ④ ADB 一键从已 root 手机同步登录会话（推荐，免改手机代理）或抓包提取 token
.venv\Scripts\python.exe adb_capture.py --mmkv
# 若手机未 root，可用 ADB 反向代理抓包或 Wi-Fi 代理指向 8888 端口：
# .venv\Scripts\python.exe adb_capture.py --mitm

# ⑤ 在线 Dry-Run（真门校验 + 拉取官方跑区/围栏/额度，零写入）
.venv\Scripts\python.exe lepaorun/driver.py

# ⑥ 正式提交（需已配置有效 token）
.venv\Scripts\python.exe lepaorun/driver.py --submit
```

---

## 武汉科技大学适配参数汇总

| 项目 | 参数值 / 说明 |
|---|---|
| 生产 API 域名 | `api2.lptiyu.com`（外网直连）；校内系统域名 `zhty.wust.edu.cn`（需校内网/aTrust VPN） |
| 学校 ID (`school_id`) | `61`（武汉科技大学，真机实测确认；默认跑区 `run_zone_id=1963`，学期 `term_id=13286`） |
| 微信 AppID | `wx5a2e1ff396785475`（官方 APK `com.lptiyu.tanke` 实证） |
| QQ AppID | `1105660458`（官方 APK `assets/ShareSDK.xml` 实证） |
| 加解密算法 | AES-128-CBC（`KEY=Wet2C8d34f62ndi3`, `IV=K6iv85jBD8jgf32D`）+ `SignMD5(rDJiNB9j7vD2)` |
| 跑区（黄家湖） | 沁湖环道跑区（4点/2.6km）、南区田径场（3点/400m）、北区田径场（3点/400m） |
| 距离/配速要求 | 男生 ≥2.5km，女生 ≥2.0km；≥3 个打卡点；配速 3–11 min/km（180–660 s/km） |
| 每日成绩上限 | 1 次有效成绩 |

## 关于微信/QQ 扫码登录与纯脱机兑换 Token 的说明

- `qr_login.py` 与 `wust_panel.py` 已完整打通**官方微信 SDK 扫码（`open.weixin.qq.com/connect/sdk/qrconnect`）**、**官方 QQ 互联扫码（`ssl.ptlogin2.qq.com/ptqrshow` + `graph.qq.com/oauth2.0/authorize`）**以及 **`Login/quickLoginV339` 纯脱机兑换协议**。
- 通过逆向解开新版步道乐跑 App（v4.3.x）`ijiami` 壳的 DEX 头部混淆（`ROR32(w ^ key32, 6)`），已完整还原 `Login/quickLoginV339` 的四层校验机制：
  1. `openid` 与 `accesstoken` 按 `int(nonce) % 10` 从 `Lo9/c;->a9` 动态密钥表取 `(KEY, IV)` 进行内层 `AES-128-CBC` 加密（对齐 Android `Base64.DEFAULT` 76 字符换行与末尾 `\n`）；
  2. 动态防篡改字段名 `lp + mobileModel[1].lower() + timestamp[3]`，其值为 `umid ("4x7y0z3a6b9c2d5e8f1g4h7i0j3k6l9m") + MD5(timestamp)` 按 `int(timestamp) % 15` 从 `Lo9/c;->c9` 动态密钥表加密；
  3. `isEncryptNew` 签名盐 `eFoqdHOdDy6ViJ0i` 前置拼接，且排除 `mobileDeviceId`、`nick_name`、`avatar_url` 三个字段参与 MD5；
  4. 整体 JSON 以 `PARAMS_NEW_GAME`（`KEY=goMEzJ1pDpncNHb9, IV=ZUrAS2lUidjyY2gK`）加密为 `key=` 表单提交，并在兑换成功后自动调用 `User/User` 与 `beforeRunV260` 补全学号、学校 ID、性别和跑区信息写入 `lepaorun/config.json`，**全程零手机/零模拟器/零抓包依赖**。
