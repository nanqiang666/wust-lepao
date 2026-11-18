# -*- coding: utf-8 -*-
"""调试 OSS callback 上传的 policy 生成"""
import sys
import json
import base64
import random
import datetime

sys.path.insert(0, ".")
from lepao import record as R


def main():
    rnd = random.Random()
    now_ms = int(datetime.datetime.now().timestamp() * 1000)

    # 模拟 upload_oss_content 里的 policy 生成
    conds = [["content-length-range", 0, 1073741824], ["starts-with", "$callback", ""]]
    policy_src = '{"expiration":"%s","conditions":%s}' % (
        R.iso_utc_ms(now_ms + 3600000), json.dumps(conds))
    print("policy 源码:")
    print(policy_src)

    # 解码看 callback JSON 内容
    cb = "eyJjYWxsYmFja1VybCI6Imh0dHBzOlwvXC9hcGkyLmxwdGl5dS5jb21cL3YzXC9hcGkucGhwXC9XcEluZGV4XC9vc3NDYWxsYmFjayIsImNhbGxiYWNrQm9keSI6ImJ1Y2tldD0ke2J1Y2tldH0mb2JqZWN0PSR7b2JqZWN0fSZldGFnPSR7ZXRhZ30mc2l6ZT0ke3NpemV9Jm1pbWVUeXBlPSR7bWltZVR5cGV9JmltYWdlSW5mby5oZWlnaHQ9JHtpbWFnZUluZm8uaGVpZ2h0fSZpbWFnZUluZm8ud2lkdGg9JHtpbWFnZUluZm8ud2lkdGh9JmltYWdlSW5mby5mb3JtYXQ9JHtpbWFnZUluZm8uZm9ybWF0fSIsImNhbGxiYWNrQm9keVR5cGUiOiJhcHBsaWNhdGlvblwveC13d3ctZm9ybS11cmxlbmNvZGVkIn0="
    decoded = base64.b64decode(cb).decode()
    print("\ncallback 解码:")
    print(decoded)


if __name__ == "__main__":
    main()
