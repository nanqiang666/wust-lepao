# -*- coding: utf-8 -*-
"""汇总账号当天的跑量/学期进度（只读，供 tick 与面板汇报用）。"""
import datetime
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_ROOT, "lepaorun"))


def term_stats():
    try:
        import driver

        cfg = driver.load_config()
        accounts = cfg.get("accounts") or {}
        if not accounts:
            return {"error": "accounts 表为空"}
        ak = cfg.get("active") if cfg.get("active") in accounts else list(accounts.keys())[0]
        acc = driver.Account(accounts[ak], cfg)
        if not acc.token:
            return {"error": "未配置 token"}
        c = acc.make_client()
        terms = c.post("/v3/api.php/WpRun/getTermList", {})
        if isinstance(terms, dict) and terms.get("status") == 101:
            return {"error": "token 已失效 (101)"}
        tid = str(terms[0]["term_id"]) if isinstance(terms, list) and terms else "0"
        rr = c.post("/v3/api.php/WpRun/getTermRunRecord", {"term_id": tid, "page": 1}) or {}
        lst = rr.get("list") or []
        day0 = int(datetime.datetime.combine(datetime.date.today(), datetime.time(0, 0)).timestamp())
        today = [r for r in lst if str(r.get("start_time", "0")).isdigit() and int(r["start_time"]) >= day0]
        return {
            "term_name": terms[0].get("term_name") if isinstance(terms, list) and terms else "",
            "today_count": len(today),
            "term_count": rr.get("total_num"),
            "term_distance": rr.get("total_distance"),
            "term_ok_count": rr.get("total_score_num"),
            "term_ok_distance": rr.get("total_score_distance"),
        }
    except Exception as e:
        return {"error": str(e)[:120]}


if __name__ == "__main__":
    print(json.dumps(term_stats(), ensure_ascii=False))
