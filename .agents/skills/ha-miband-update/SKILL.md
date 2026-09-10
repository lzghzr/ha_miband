---
name: ha-miband-update
description: 小米手环 HA 集成的设备更新流水线：抓取小米运动健康设备列表、经 miot-spec 计算 objectid、生成 DeviceEntry 并按 key 升序写入 device.py。当用户提到检查/更新手环手表设备、有新设备、跑设备更新流水线、新增小米手环/手表/Redmi Watch 支持、处理 miot-spec objectid、或询问设备为什么不被支持时使用；即使用户只说"看看有没有新设备"也应触发。
---

# 小米手环设备更新流水线

更新 ha_miband Home Assistant 集成的设备支持列表。三步流程与人工更新历史完全一致：

1. **step1 发现**：用 get_config_info_by_category 接口抓取可穿戴设备列表（中英双语，每次运行自动刷新），与已入库（device.py）和确认无需入库（known_devices 分区）的设备求差，得到新设备。
2. **step2 分析**：对每个新设备按 objectid.js 公式（`objectid = eiid + 0x400*siid + base`，property/action/event 的 base 分别为 0x3C18/0x3D18/0x3E18）从 miot-spec 计算有意义的（eiid>1000）objectid。
3. **step3 生成**：把 objectid 映射为 DeviceEntry 代码块，按 dict key 升序插入 device.py 的正确位置。

## 文件布局

本 skill 目录（项目 `SKILL/`）含全部工具与状态；写入目标在项目根（脚本自动向上查找定位，从任意目录运行均可）：

- `pipeline.py` — 流水线主脚本
- `get_config_info_by_category.py` — 设备列表抓取（被 pipeline 导入）
- `known_devices.json` — 设备状态，单文件两分区（结构见下）
- `get_config_info_by_category*.json` — 每次运行刷新的原始抓取数据，已 gitignore，不提交
- 项目根 `device.py`（apply 写入）/ `parser.py`（人工补全）/ `const.py`（设备类枚举）

## 标准流程

```bash
python3 SKILL/pipeline.py             # dry-run：刷新配置、发现新设备、生成代码块，不写文件
python3 SKILL/pipeline.py --apply     # 真正写入 device.py
python3 SKILL/pipeline.py --model miwear.watch.q66nfc   # 只处理指定 model
python3 SKILL/pipeline.py --only devices|objectids|generate   # 只跑某一步
```

1. 先跑 dry-run，向用户报告：新设备清单、每个设备的 objectid 识别情况、将生成的代码块。
2. 经用户确认后 `--apply`。
3. 验证：再跑一次 dry-run 应报"发现 0 个新设备"；`git diff device.py` 检查插入位置与格式。
4. 提交：`git add device.py SKILL/known_devices.json`，提交信息沿用项目惯例 `新增 <中文名>`（如"新增 小米手环11"）。

## 状态文件 known_devices.json

JSON 键因格式限制存的是 `str(pd_id)`，判断一律以条目内的 `pd_id` 字段（int）为准：

```json
{
  "known_devices": {
    "1289": {"pd_id": 1289, "model": "midr.watch.ds", "pd_name_zh": "...", "pd_name_en": "..."}
  },
  "not_supported": {
    "1289": {"pd_id": 1289, "model": "...", "pd_name_zh": "...", "pd_name_en": "...", "reason": "not_registered"}
  }
}
```

- `not_supported.reason` 取值：`not_registered`（miot-spec 404，属正常现象）/ `no_objectids`（无 eiid>1000 对象，集成不支持）。
- step1 只跳过 `known_devices` 里的设备；step2 把确认 404/无 objectid 的设备同时写入两个分区。
- **有有意义 objectid 但未 apply 的设备不登记**（如曾因 dry-run 未写入的设备）——下次仍作为新设备出现，直到 apply 成功后由 device.py 自然过滤。dry-run 永远不改变状态。

## 未知 objectid 的人工补全

pipeline 打印 `存在 N 个未识别的 objectid` 时，该设备不会生成完整代码，需三处手工修改后重跑：

1. `parser.py` 的 `xiaomi_dataobject_dict` 加 `0xXXXX: eiidYYYY,`，并实现 converter 函数（签名 `def eiidYYYY(xobj: bytes, device: XiaomiBluetoothDeviceData, device_type: str) -> dict[str, Any]`，参考同文件的 `eiid1016`（binary sensor）、`eiid1105`（event）、`eiid1034`（sensor））。
2. `SKILL/pipeline.py` 的 `FUNC_TO_CLASS` 加 `"eiidYYYY": ("binary|event|sensor", "MiBand...DeviceClass.成员"),`。
3. 若需要新枚举成员，在 `const.py` 的 `MiBandBinarySensorDeviceClass` / `MiBandSensorDeviceClass` / `MiBandEventDeviceClass` 中补充。

注意隐含规则：设备存在 MODE 事件（eiid1105）时，DeviceEntry 会自动额外带出 NODISTURB binary sensor，无需显式映射。

## 代码规范

生成器（`render_entry` / `insert_entry_sorted`）已实现以下约定，人工改动 device.py 时保持一致：

- key 用大写十六进制 `0xXXXX`（文件既有 key 均大写），条目按 key 升序插入第一个更大 key 之前，而不是追加到 dict 末尾。
- 单元素/空列表用紧凑单行（`sensor=[MiBandSensorDeviceClass.BATTERY_CHARGING],`、`sensor=[],`），多元素才换行展开。
- `name` 取英文 `pd_name` 并去掉开头品牌前缀（Xiaomi/Mi/Redmi，见 `strip_brand`）；中文名不写入 device.py，仅用于提交信息与报告。
