# -*- coding: utf-8 -*-
"""武汉科技大学乐跑适配测试套件（含单元、离线模拟、线上实测）。"""
import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEPAORUN = os.path.join(ROOT, "lepaorun")
sys.path.insert(0, LEPAORUN)

from lepao import crypto, license_guard, qr_login, wust_track  # noqa: E402
from lepao.v3api import V3Client  # noqa: E402
import driver  # noqa: E402


class TestWustLepao(unittest.TestCase):
    def test_license_intact(self):
        st = license_guard.check_license()
        self.assertEqual(st["status"], "ok", f"LICENSE 完整性校验失败: {st}")

    def test_crypto_roundtrip_and_sign(self):
        payload = {"uid": 123, "school_id": 0, "distance": 2.65, "ostype": 5}
        payload["sign"] = crypto.sign_md5(payload)
        ct = crypto.encrypt_data(json.dumps(payload))
        pt = json.loads(crypto.decrypt_data(ct))
        self.assertEqual(pt["sign"], payload["sign"])
        self.assertEqual(pt["distance"], 2.65)

    def test_quick_login_v339_crypto_protocol(self):
        key_b64, params = crypto.build_quick_login_key(
            openid="oKELnwTestOpenId123",
            access_token="1_TestAccessTokenxyz",
            login_type=3,
            nickname="测试用户",
            avatar_url="https://example.com/a.jpg",
            timestamp=1794916000,
            nonce="543210",
            mobile_model="PLK110",
        )
        # 动态字段名: "lp" + "PLK110"[1].lower() + "1794916000"[3] == "lpl4"
        self.assertIn("lpl4", params)
        self.assertTrue(params["openid"].endswith("\n"))
        self.assertTrue(params["accesstoken"].endswith("\n"))
        # 验证 nick_name, avatar_url, mobileDeviceId 不影响签名
        s1 = params["sign"]
        mutated = dict(params, nick_name="另一个名字", avatar_url="https://other", mobileDeviceId="other-dev")
        s2 = crypto.sign_md5_encrypt_new(mutated, is_login_v339=True)
        self.assertEqual(s1, s2)
        # 验证外层 key= 可用 APP_AES_KEY 解密还原
        decrypted_json = json.loads(crypto.decrypt_app_key(key_b64))
        self.assertEqual(decrypted_json["sign"], s1)
        self.assertEqual(decrypted_json["type"], "3")

    def test_parse_zone_polygon_formats(self):
        p1 = wust_track.parse_zone_polygon("[[114.26,30.44],[114.27,30.44],[114.27,30.45]]")
        self.assertEqual(len(p1), 3)
        p2 = wust_track.parse_zone_polygon("114.26,30.44;114.27,30.44;114.27,30.45")
        self.assertEqual(len(p2), 3)
        p3 = wust_track.parse_zone_polygon([{"lng": 114.26, "lat": 30.44}, {"lng": 114.27, "lat": 30.44}, {"lng": 114.27, "lat": 30.45}])
        self.assertEqual(len(p3), 3)

    def test_simulate_all_wust_zones(self):
        for zk in ("qinhu", "south_track", "north_track"):
            for gender, min_d in (("male", 2.50), ("female", 2.00)):
                out, code = driver.simulate_wust(zone_key=zk, gender=gender)
                self.assertEqual(code, 0)
                self.assertGreaterEqual(out["distance_km"], min_d)
                self.assertGreaterEqual(len(out["crossings"]), 3)
                self.assertTrue(out["crypto_roundtrip_ok"])
                for rule_name, res in out["self_check"].items():
                    self.assertTrue(res["passed"], f"{zk}/{gender} 自检失败: {rule_name} -> {res}")

    def test_live_api2_connectivity(self):
        c = V3Client(uid=0, token="", school_id=-1, host="api2.lptiyu.com", timeout=8)
        ip_res = c.get_server_ip(2)
        self.assertIsInstance(ip_res, dict)
        self.assertIn("api2.lptiyu.com", ip_res.get("ip", ""))

    def test_live_qr_generation_wx_and_qq(self):
        wx = qr_login.WeChatQRLogin()
        wx_info = wx.create_qr()
        self.assertTrue(wx_info["uuid"])
        self.assertGreater(len(wx_info["png_bytes"]), 200)
        self.assertTrue(os.path.isfile(wx_info["png_path"]))

        qq = qr_login.QQQRLogin()
        qq_info = qq.create_qr()
        self.assertTrue(qq_info["qrsig"])
        self.assertTrue(qq_info["png_bytes"].startswith(b"\x89PNG"))
        self.assertTrue(os.path.isfile(qq_info["png_path"]))

    def test_cli_entrypoints(self):
        py = sys.executable
        r1 = subprocess.run([py, os.path.join(LEPAORUN, "driver.py"), "--simulate", "--zone", "qinhu"],
                            capture_output=True, text=True, timeout=30)
        self.assertEqual(r1.returncode, 0, r1.stderr)
        r2 = subprocess.run([py, os.path.join(ROOT, "qr_login.py"), "--wx", "--test"],
                            capture_output=True, text=True, timeout=20)
        self.assertEqual(r2.returncode, 0, r2.stderr)
        r3 = subprocess.run([py, os.path.join(ROOT, "qr_login.py"), "--qq", "--test"],
                            capture_output=True, text=True, timeout=20)
        self.assertEqual(r3.returncode, 0, r3.stderr)
        r4 = subprocess.run([py, os.path.join(ROOT, "wust_panel.py"), "--selfcheck"],
                            capture_output=True, text=True, timeout=20)
        self.assertEqual(r4.returncode, 0, r4.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
