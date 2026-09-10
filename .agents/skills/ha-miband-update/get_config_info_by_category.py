#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
获取小米运动健康 get_config_info_by_category 数据（中/英文）。

抓包分析结论:
  * 该接口存在未登录分支: 仅凭 cookie auth_key=rwelJuWBFJxmbMKD 即可返回 code:0 明文 JSON。
  * auth_key 是全局固定值, 服务端只校验它。
  * data 参数必需, 但其内部只有 category 字段是真正必要的。
  * 语言由 URL 参数 locale 决定: zh_cn -> 中文, en_us -> 英文。

用法:
  python3 get_config_info_by_category_fetch.py            # 中英两种都拉取并保存
  python3 get_config_info_by_category_fetch.py --lang zh  # 只拉中文, 存 get_config_info_by_category.json
  python3 get_config_info_by_category_fetch.py --lang en  # 只拉英文, 存 get_config_info_by_category_en.json
"""

import argparse
import json
import sys
import urllib.parse
import urllib.request

API = "https://hlth.io.mi.com/app/v1/product/get_config_info_by_category"
AUTH_KEY = "rwelJuWBFJxmbMKD"
CATEGORY = "wearable"


def fetch(lang: str) -> dict:
    locale = "en_us" if lang == "en" else "zh_cn"
    params = {"locale": locale, "data": json.dumps({"category": CATEGORY}, separators=(",", ":"))}
    url = f"{API}?{urllib.parse.urlencode(params)}"
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
