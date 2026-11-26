#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
获取小米运动健康 get_config_info_by_category 数据（区域与语言分别指定）。

产品目录按地区和语言返回可穿戴设备，无需用户登录。

用法:
  python3 get_config_info_by_category.py            # 中国区，中英两种都拉取并保存
  python3 get_config_info_by_category.py --lang zh  # 只拉中文, 存 get_config_info_by_category.json
  python3 get_config_info_by_category.py --lang en  # 只拉英文, 存 get_config_info_by_category_en.json
"""

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request

API = "https://hlth.io.mi.com/app/v1/product/get_config_info_by_category"
AUTH_KEY = "rwelJuWBFJxmbMKD"
CATEGORY = "wearable"
# 与 cloud.py 的 SERVERS 一致。中国区使用不带前缀的域名。
REGIONS = ("cn", "de", "us", "ru", "sg", "i2")


def fetch(lang: str, *, region: str = "cn") -> dict:
    locale = "en_us" if lang == "en" else "zh_cn"
    params = {"locale": locale, "data": json.dumps({"category": CATEGORY}, separators=(",", ":"))}
    api = API if region == "cn" else API.replace("://", f"://{region}.", 1)
    url = f"{api}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        url,
        headers={
            "Cookie": f"auth_key={AUTH_KEY}",
            "Accept-Encoding": "gzip",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip":
            import gzip

            raw = gzip.decompress(raw)
        return json.loads(raw)


def has_chinese_name(name: str | None) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", name or ""))


def fetch_catalog(lang: str) -> dict:
    """按 PID 合并各区目录；任一区抓取失败就不返回部分结果。"""
    by_pid = {}
    modified_times = []
    for region in REGIONS:
        try:
            data = fetch(lang, region=region)
            if data.get("code") not in (None, 0):
                raise ValueError(f"接口返回 code={data.get('code')}")
            result = data.get("result") or {}
            if not result.get("list"):
                raise ValueError("接口未返回设备列表")
        except Exception as e:
            raise RuntimeError(f"{region}/{lang}: {e}") from e

        if (modified := result.get("last_modify_time")) is not None:
            modified_times.append(modified)
        for item in result["list"]:
            if "pd_id" not in item:
                continue
            current = by_pid.setdefault(item["pd_id"], item.copy())
            name = item.get("pd_name")
            current_name = current.get("pd_name")
            if name and (not current_name or (
                lang == "zh" and has_chinese_name(name) and not has_chinese_name(current_name)
            )):
                current["pd_name"] = name

    return {"code": 0, "result": {
        "list": list(by_pid.values()),
        "last_modify_time": max(modified_times, default=None),
    }}


def main() -> int:
    ap = argparse.ArgumentParser(description="非登录获取 get_config_info_by_category")
    ap.add_argument("--lang", choices=["zh", "en"], default=None,
                    help="只拉取并保存指定语言; 不填则中英都拉取并保存")
    args = ap.parse_args()

    langs = [args.lang] if args.lang else ["zh", "en"]
    for lang in langs:
        try:
            data = fetch(lang)
        except Exception as e:
            print(f"[{lang}] 请求失败: {e}", file=sys.stderr)
            return 1
        if data.get("code") != 0:
            print(f"[{lang}] 接口返回错误: {json.dumps(data, ensure_ascii=False)}", file=sys.stderr)
            return 1
        path = "get_config_info_by_category_en.json" if lang == "en" else "get_config_info_by_category.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        res = data.get("result", {})
        print(f"[{lang}] 已保存 {path}: code={data.get('code')} list={len(res.get('list') or [])} "
              f"last_modify_time={res.get('last_modify_time')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
