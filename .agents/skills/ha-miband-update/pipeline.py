#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小米手环设备更新流水线。

流程（与项目更新流程一致）:
  step1 - devices:   用 get_config_info_by_category 抓取设备列表, 找出新增设备。
  step2 - objectids: 对每个新设备通过 miot-spec 计算 objectid, 识别有意义的(eiid>1000)对象。
  step3 - generate:  根据有意义的 objectid 生成 device.py 的 DeviceEntry 代码块。

持久化(由流水线自动读写更新, 单文件 known_devices.json, 两个分区):
  known_devices  - 确认无需入库的设备(404/无有意义objectid), step1 据此跳过。
  not_supported  - 不支持的设备明细及原因(not_registered=miot-spec 404,
                   no_objectids=无 eiid>1000 的有意义对象)。
  有有意义 objectid 但未 --apply 的设备不登记, 下次仍作为新设备出现,
  直到 apply 写入 device.py 后由 existing 自然过滤。

用法:
  python3 pipeline.py            # dry-run, 只打印新设备与将要生成的代码, 不写文件
  python3 pipeline.py --apply    # 真正写入 device.py
  python3 pipeline.py --only devices|objectids|generate   # 只跑某一步
  python3 pipeline.py --model miwear.watch.q66nfc        # 只处理指定 model

校验: 对照上一次提交("新增 小米手环11"), 本流水线应能复现其 device.py 改动。
"""

import argparse
import json
import os
import re
import sys

import get_config_info_by_category

# ---------------------------------------------------------------------------
# 路径解析: 允许从任意目录(SKILL/ 或项目根目录)运行本脚本。
#   SCRIPT_DIR - 本脚本所在目录(SKILL/), 存放 json 数据文件。
#   ROOT_DIR   - 项目根目录(含 device.py/parser.py 的目录), 向上查找得到。
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = SCRIPT_DIR
while not os.path.exists(os.path.join(ROOT_DIR, "device.py")) or \
        not os.path.exists(os.path.join(ROOT_DIR, "parser.py")):
    parent = os.path.dirname(ROOT_DIR)
    if parent == ROOT_DIR:
        sys.exit("无法定位项目根目录(未找到 device.py / parser.py)")
    ROOT_DIR = parent

DEVICE_FILE = os.path.join(ROOT_DIR, "device.py")
PARSER_FILE = os.path.join(ROOT_DIR, "parser.py")

# 持久化文件(单文件, 内含 known_devices / not_supported 两个分区)
DEVICES_JSON = os.path.join(SCRIPT_DIR, "known_devices.json")

# ---------------------------------------------------------------------------
# 反向映射: parser.py 里 converter 函数名 -> (类型, 设备类枚举成员)
# 类型: binary / event / sensor 对应 DeviceEntry 的三个字段。
# ---------------------------------------------------------------------------
FUNC_TO_CLASS = {
    "eiid1016": ("binary", "MiBandBinarySensorDeviceClass.SLEEP"),
    "eiid1034": ("sensor", "MiBandSensorDeviceClass.BATTERY_CHARGING"),
    "eiid1086": ("event", "MiBandEventDeviceClass.HAND_GESTURE"),
    "eiid1091": ("event", "MiBandEventDeviceClass.SPORTS"),
    "eiid1092": ("event", "MiBandEventDeviceClass.ABNORMAL_SIGNS"),
    "eiid1094": ("event", "MiBandEventDeviceClass.DAILY_VITALITY_INDEX"),
    "eiid1097": ("binary", "MiBandBinarySensorDeviceClass.WEARING"),
    "eiid1105": ("event", "MiBandEventDeviceClass.MODE"),
}

# MODE 事件存在时, DeviceEntry 额外带出的 binary sensor
MODE_EXTRA_BINARY = "MiBandBinarySensorDeviceClass.NODISTURB"

MIOT_SPEC_URL = (
    "https://miot-spec.org/miot-spec-v2/instance"
    "?type=urn:miot-spec-v2:device:watch:0000A07C:{model_dashed}:1"
)


# ---------------------------------------------------------------------------
# 读取现有文件
# ---------------------------------------------------------------------------
def load_device_entries() -> dict[int, dict]:
    """解析 device.py, 返回 {device_id_hex:int -> {model, name, ...}}."""
    src = open(DEVICE_FILE).read()
    # 匹配 0xXXXX: DeviceEntry(\n model="...",\n name="...", ...
    block_re = re.compile(
        r"\n    (0x[0-9A-Fa-f]+): DeviceEntry\(\n"
        r'        model="([^"]*)",\n'
        r'        name="([^"]*)",',
        re.M,
    )
    entries = {}
    for m in block_re.finditer(src):
        pid = int(m.group(1), 16)
        entries[pid] = {"model": m.group(2), "name": m.group(3)}
    return entries


def load_xiaomi_objectid_dict() -> dict[int, str]:
    """解析 parser.py 的 xiaomi_dataobject_dict, 返回 {objectid:int -> func_name:str}."""
    src = open(PARSER_FILE).read()
    # 提取 xiaomi_dataobject_dict 字典体
    m = re.search(r"xiaomi_dataobject_dict\s*=\s*\{(.*?)\n\}", src, re.S)
    if not m:
        sys.exit("无法在 parser.py 中找到 xiaomi_dataobject_dict")
    body = m.group(1)
    obj_re = re.compile(r"0x([0-9A-Fa-f]+)\s*:\s*([A-Za-z_][A-Za-z0-9_]*)")
    d = {}
    for om, fn in obj_re.findall(body):
        d[int(om, 16)] = fn
    return d


# ---------------------------------------------------------------------------
# 持久化 JSON 读写
# ---------------------------------------------------------------------------
def load_json(path: str, default) -> dict:
    """读取 JSON; 不存在或损坏时返回 default."""
    if not os.path.exists(path):
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:  # noqa: BLE001
        print(f"    [警告] 读取 {path} 失败({e}), 从空开始。", file=sys.stderr)
        return default


def save_json(path: str, data: dict) -> None:
    """写 JSON; 保证键为字符串(JSON 键只能是字符串)."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


# ---------------------------------------------------------------------------
# step1 - 发现新设备
# ---------------------------------------------------------------------------
def step1_devices(config_zh, config_en, existing) -> list[dict]:
    """返回新设备列表: {pd_id, model, pd_name_en, pd_name_zh, blt_name}."""
    by_pd = {}
    for it in config_zh["result"]["list"]:
        if "pd_id" in it:
            by_pd[it["pd_id"]] = it
    by_pd_en = {}
    for it in config_en["result"]["list"]:
        if "pd_id" in it:
            by_pd_en[it["pd_id"]] = it

    new_devices = []
    for pid, item in sorted(by_pd.items()):
        if pid in existing:
            continue
        en = by_pd_en.get(pid, {})
        new_devices.append(
            {
                "pd_id": pid,
                "model": item.get("model"),
                "blt_name": item.get("blt_name"),
                "pd_name_zh": item.get("pd_name"),
                "pd_name_en": en.get("pd_name"),
            }
        )
    return new_devices


def strip_brand(name: str | None) -> str | None:
    """去掉英文名开头的品牌前缀(Xiaomi/Mi/Redmi), 与现有 device.py 命名一致."""
    if not name:
        return name
    name = name.strip()
    for brand in ("Xiaomi", "Mi", "Redmi"):
        if name.startswith(brand + " ") or name == brand:
            return name[len(brand):].lstrip()
    return name


# ---------------------------------------------------------------------------
# step2 - 计算 objectid
# ---------------------------------------------------------------------------
def model_to_url(model: str) -> str:
    """把 device model 转成 miot-spec URL 的 model 段。

    device model 形如 <brand>.<category>.<model> (如 miwear.watch.q66nfc)。
    去掉中间的 category 段: miwear.watch.q66nfc -> miwear-q66nfc (brand-model)。
    """
    parts = model.split(".")
    if len(parts) >= 3:
        brand, model_part = parts[0], parts[-1]
        model_dashed = f"{brand}-{model_part}"
    else:
        model_dashed = model.replace(".", "-")
    return MIOT_SPEC_URL.format(model_dashed=model_dashed)


def fetch_instance(model: str) -> dict | None:
    """抓取 miot-spec instance JSON; 失败返回 None."""
    import urllib.request

    url = model_to_url(model)
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:  # noqa: BLE001
        print(f"    [警告] 抓取 {model} 的 miot-spec 失败: {e}", file=sys.stderr)
        return None


def compute_objectids(instance: dict) -> list[dict]:
    """按 objectid.js 公式为 instance 计算每个有意义的(eiid>1000)对象的 objectid.

    返回 [{objectid, siid, eiid, kind, description}].
    """
    out = []
    for service in instance.get("services", []):
        siid = service.get("iid")
        for key, base, kind in (
            ("properties", 0x3C18, "property"),
            ("actions", 0x3D18, "action"),
            ("events", 0x3E18, "event"),
        ):
            for obj in service.get(key) or []:
                eiid = obj.get("iid")
                if not eiid:
                    continue
                # 只关心有意义的(eiid>1000)对象
                if eiid <= 1000:
                    continue
                objectid = eiid + 0x400 * siid + base
                out.append(
                    {
                        "objectid": objectid,
                        "siid": siid,
                        "eiid": eiid,
                        "kind": kind,
                        "description": obj.get("description"),
                    }
                )
    return out


# ---------------------------------------------------------------------------
# step3 - 生成 DeviceEntry 代码块
# ---------------------------------------------------------------------------
def objectid_to_entry(obj_dict: dict[int, str]) -> tuple[set, set, set]:
    """把某设备的有意义 objectid 集合映射到 (binary, event, sensor) 类集合.

    未识别的 objectid 会单独返回, 交由调用方提醒人工补全。
    """
    binary, event, sensor = set(), set(), set()
    unknown = []
    for objectid, func in obj_dict.items():
        info = FUNC_TO_CLASS.get(func)
        if info is None:
            unknown.append(objectid)
            continue
        kind, member = info
        if kind == "binary":
            binary.add(member)
        elif kind == "event":
            event.add(member)
        elif kind == "sensor":
            sensor.add(member)
    # MODE 事件存在 -> 额外带出 NODISTURB binary sensor
    if "MiBandEventDeviceClass.MODE" in event:
        binary.add(MODE_EXTRA_BINARY)
    return binary, event, sensor, unknown


def render_entry(pid: int, model: str, name: str, binary, event, sensor) -> str:
    def lst(vals: set) -> str:
        # 与 device.py 既有格式一致: 空列表/单元素用紧凑单行, 多元素用多行。
        vals = sorted(vals)
        if not vals:
            return "[]"
        if len(vals) == 1:
            return f"[{vals[0]}]"
        inner = ",\n".join("            " + v for v in vals)
        return "[\n" + inner + ",\n        ]"

    return (
        f"    0x{pid:04X}: DeviceEntry(\n"
        f'        model="{model}",\n'
        f'        name="{name}",\n'
        f"        binary_sensor={lst(binary)},\n"
        f"        event={lst(event)},\n"
        f"        sensor={lst(sensor)},\n"
        f"    ),"
    )


# ---------------------------------------------------------------------------
# 写回 device.py
# ---------------------------------------------------------------------------
ENTRY_START_RE = re.compile(r"\n    (0x[0-9A-Fa-f]+): DeviceEntry\(")


def insert_entry_sorted(src: str, pid: int, block: str) -> str:
    """把 block 按 key 升序插入 src: 放在第一个更大 key 的条目之前;
    没有更大的 key 时追加到最后一个条目之后、dict 结尾 "}" 之前。"""
    for m in ENTRY_START_RE.finditer(src):
        if int(m.group(1), 16) > pid:
            p = m.start() + 1  # 跳过条目前导换行, 保持既有缩进
            return src[:p] + block + "\n" + src[p:]
    marker = re.compile(r"(\n    (?:0x[0-9A-Fa-f]+): DeviceEntry\(.*?\n    \),\n)(\})", re.S)
    m = marker.search(src)
    if not m:
        sys.exit("无法定位 device.py 的插入点")
    return src[: m.end(1)] + block + "\n" + src[m.end(1):]


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="小米手环设备更新流水线")
    ap.add_argument("--apply", action="store_true", help="真正写入 device.py (默认 dry-run)")
    ap.add_argument("--only", choices=["devices", "objectids", "generate"], help="只跑某一步")
    ap.add_argument("--model", help="只处理指定 model")
    ap.add_argument("--zh", default=os.path.join(SCRIPT_DIR, "get_config_info_by_category.json"),
                    help="中文配置 JSON 路径")
    ap.add_argument("--en", default=os.path.join(SCRIPT_DIR, "get_config_info_by_category_en.json"),
                    help="英文配置 JSON 路径")
    args = ap.parse_args()

    # ---- 准备: 抓取并更新配置 JSON(每次运行都刷新) ----
    if not os.path.exists(args.zh) or not os.path.exists(args.en):
        print("配置 JSON 缺失, 先抓取...")
    for lang, path in (("zh", args.zh), ("en", args.en)):
        data = get_config_info_by_category.fetch(lang)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        res = data.get("result", {})
        print(f"[{lang}] 已更新 {path}: list={len(res.get('list') or [])}")

    config_zh = json.load(open(args.zh, encoding="utf-8"))
    config_en = json.load(open(args.en, encoding="utf-8"))

    existing = load_device_entries()
    objid_to_func = load_xiaomi_objectid_dict()

    # 设备状态清单(单文件两分区, 自动读写)
    devices_state = load_json(
        DEVICES_JSON, {"known_devices": {}, "not_supported": {}}
    )
    known = devices_state.setdefault("known_devices", {})
    not_supported = devices_state.setdefault("not_supported", {})

    # ---- step1 ----
    # 只跳过"确认无需入库"的设备(known_devices 分区);
    # 有有意义 objectid 但未 apply 的设备不在其中, 下次仍作为新设备出现。
    known_pids = {v["pd_id"] for v in known.values()}
    new_devices = step1_devices(
        config_zh, config_en, set(existing) | known_pids
    )
    print(f"[step1] 配置中共 {len(existing)} 个已入库设备, "
          f"{len(known_pids)} 个确认无需入库, 发现 {len(new_devices)} 个新设备:")
    for d in new_devices:
        print(f"  0x{d['pd_id']:04X}  {d['model']:<28} en={d['pd_name_en']!r} zh={d['pd_name_zh']!r}")

    if not new_devices:
        print("  没有新增设备, 结束。")
        return 0

    if args.only == "devices":
        return 0

    # ---- step2 ----
    # 限制到指定 model(用于校验上一次提交时只处理 q66nfc)
    targets = new_devices
    if args.model:
        targets = [d for d in new_devices if d["model"] == args.model]

    analyzed = []
    newly_unsupported = {}
    unsupported_models = {v["model"] for v in not_supported.values()}
    for d in targets:
        model = d["model"]
        if model in unsupported_models:
            print(f"\n[step2] 跳过 {model}: 已记录为不支持({not_supported.get(str(d['pd_id']), {}).get('reason')})。")
            continue
        print(f"\n[step2] 分析 {model}:")
        inst = fetch_instance(model)
        if inst is None:
            # miot-spec 未注册(404) -> 确认无需入库
            newly_unsupported[str(d["pd_id"])] = {
                "pd_id": d["pd_id"], "model": model,
                "pd_name_zh": d["pd_name_zh"], "pd_name_en": d["pd_name_en"],
                "reason": "not_registered",
            }
            print(f"    ⚠ {model} 未在 miot-spec 注册, 已记入 not_supported。")
            continue
        objs = compute_objectids(inst)
        if not objs:
            # 无有意义(eiid>1000)对象 -> 确认无需入库
            newly_unsupported[str(d["pd_id"])] = {
                "pd_id": d["pd_id"], "model": model,
                "pd_name_zh": d["pd_name_zh"], "pd_name_en": d["pd_name_en"],
                "reason": "no_objectids",
            }
            print("    没有 eiid>1000 的有意义对象, 已记入 not_supported。")
            continue
        obj_dict = {}
        for o in objs:
            func = objid_to_func.get(o["objectid"])
            mark = " [已识别]" if func else " [NEW-需人工补全]"
            obj_dict[o["objectid"]] = func
            print(
                f"    0x{o['objectid']:04X} siid={o['siid']} eiid={o['eiid']} "
                f"{o['kind']:<8} {o['description']}{mark}"
            )
        binary, event, sensor, unknown = objectid_to_entry(obj_dict)
        if unknown:
            print(
                f"    ⚠ 存在 {len(unknown)} 个未识别的 objectid, "
                f"需要人工补全 parser.py: {['0x%04X' % u for u in unknown]}"
            )
        d.update(binary=binary, event=event, sensor=sensor, unknown=unknown)
        analyzed.append(d)

    # 确认无需入库的设备: 记入 not_supported(原因) + known_devices(跳过清单)。
    # 有有意义 objectid 的设备(analyzed)不登记, apply 成功后由 device.py 过滤。
    if newly_unsupported:
        not_supported.update(newly_unsupported)
        for pid_str, info in newly_unsupported.items():
            known[pid_str] = {
                "pd_id": info["pd_id"], "model": info["model"],
                "pd_name_zh": info["pd_name_zh"], "pd_name_en": info["pd_name_en"],
            }
        save_json(DEVICES_JSON, devices_state)
        print(f"\n[step2] 已更新 {os.path.basename(DEVICES_JSON)}: "
              f"新增 {len(newly_unsupported)} 个不支持设备, "
              f"共 {len(not_supported)} 个(not_supported) / {len(known)} 个(known_devices)。")

    if args.only == "objectids":
        return 0

    # ---- step3 ----
    print("\n[step3] 生成的 DeviceEntry 代码块:")
    generated = []
    for d in analyzed:
        en_name = strip_brand(d["pd_name_en"])
        if en_name is None:
            en_name = d["blt_name"] or d["model"]
            print(f"    ⚠ {d['model']} 英文 pd_name 缺失, 用 blt_name/model 兜底: {en_name}")
        block = render_entry(
            d["pd_id"], d["model"], en_name, d["binary"], d["event"], d["sensor"]
        )
        print(block)
        generated.append((d["pd_id"], block))

    if args.only == "generate":
        return 0

    # ---- 写回 device.py ----
    if not args.apply:
        print("\n[dry-run] 未写入 device.py (加 --apply 才会真正写入)。")
        return 0

    src = open(DEVICE_FILE).read()
    # 按 dict key 升序插入到各自正确的位置
    for pid, block in sorted(generated):
        src = insert_entry_sorted(src, pid, block)
    open(DEVICE_FILE, "w").write(src)
    print(f"\n[apply] 已按 key 升序写入 {len(generated)} 个新设备到 device.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())