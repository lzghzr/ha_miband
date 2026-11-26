---
name: ha-miband-update
description: 小米手环 HA 集成的设备更新流水线：抓取小米运动健康设备列表、经 miot-spec 计算 objectid、生成 DeviceEntry 并按 key 升序写入 device.py。当用户提到检查/更新手环手表设备、有新设备、跑设备更新流水线、新增小米手环/手表/Redmi Watch 支持、处理 miot-spec objectid、或询问设备为什么不被支持时使用；即使用户只说"看看有没有新设备"也应触发。
---

# 小米手环设备更新流水线

更新 ha_miband Home Assistant 集成的设备支持列表。三步流程与人工更新历史完全一致：

1. **step1 发现**：每次从 `cn`、`de`、`us`、`ru`、`sg`、`i2` 抓取中英文可穿戴设备目录，按 `pd_id` 合并，再排除已入库和已确认无需入库的设备。报告优先用中文设备名，缺中文时用英文。
2. **step2 分析**：对每个新设备按 objectid.js 公式（`objectid = eiid + 0x400*siid + base`，property/action/event 的 base 分别为 0x3C18/0x3D18/0x3E18）从 miot-spec 计算有意义的（eiid>1000）objectid。
3. **step3 生成**：把 objectid 映射为 DeviceEntry 代码块，按 dict key 升序插入 device.py 的正确位置。

## 文件布局

工具与检查状态在本目录；集成代码在仓库的 `custom_components/miband/`：

- `pipeline.py` — 流水线主脚本
- `get_config_info_by_category.py` — 设备列表抓取（被 pipeline 导入）
- `known_devices.json` — 设备状态，单文件两分区（结构见下）
- `get_config_info_by_category*.json` — 每次运行刷新的合并目录，已 gitignore，不提交
- `custom_components/miband/` 下的 `device.py`（apply 写入）、`parser.py`（人工补全）、`const.py`（设备类枚举）

## 标准流程

以下命令在**本 skill 目录**下执行（脚本按自身位置定位集成目录）：

```bash
python3 pipeline.py             # dry-run：刷新配置、发现新设备、生成代码块（不写 device.py）
python3 pipeline.py --apply     # 写入设备表，并登记新型号的规格基线
python3 pipeline.py --model miwear.watch.q66nfc   # 只处理指定 model
python3 pipeline.py --only devices|objectids|generate   # 只跑某一步
```

1. 先跑 dry-run，向用户报告：新设备清单、每个设备的 objectid 识别情况、将生成的代码块。
2. 经用户确认后 `--apply`。
3. 验证：再跑一次 dry-run 应报"发现 0 个新设备"；`git diff -- :/custom_components/miband/device.py` 检查插入位置与格式。
4. 提交：`git add :/custom_components/miband/device.py released_specs.json known_devices.json`，提交信息沿用项目惯例 `新增 <中文名>`（如"新增 小米手环11"）；只更新状态文件（没有新设备入库）时用 `记录 <中文名> 为不支持设备` 一类描述。

### dry-run 会写哪些文件

dry-run（不带 `--apply`）不修改设备表或已审核的规格基线，但会更新以下文件：

- `get_config_info_by_category*.json`：每次运行都重写（抓取结果，已 gitignore）。
- `known_devices.json`：step2 一旦**确认**某设备无需入库（HTTP 404 或 无有意义 objectid），即使 dry-run 也会写入两个分区，供下次运行跳过——否则每次运行都要重复报告同一台设备。

`--apply` 只在整轮抓取成功且没有待补全的 objectid 时写入设备表和新型号的规格基线。单独使用也会登记新型号基线；`--check-existing` 另外核对已入库型号。

`--only` 分档：`--only devices` 在 step1 后返回（除配置刷新外不改状态）；`--only objectids` / `--only generate` 在 step2 **之后**返回，照样会写 `known_devices.json`。

### 抓取失败不会被登记

网络/DNS/超时/非 404 状态码/响应缺 `services` 都判为**结论未知**：该设备本次不写入任何分区，下次运行仍作为新设备出现，脚本以退出码 `2` 提示需要重跑。只有目录缺项且直查 v1 返回 HTTP 404 才登记为 `not_registered`。目录中只有未发布规格的型号在报告中列为 `unreleased`，不写入跳过清单，下周再查。因此退出码 `2` 时应重跑，而不是把结果当作"该设备不支持"。

任一区域的**设备列表抓取失败**（超时 / 接口 `code!=0` / 返回里没有 `list`）时，退出码为 `2`，`--report` 的 `error` 会标明失败的区域和语言，本轮不登记设备。

### --report：给 CI 用的机器可读结果

```bash
python3 pipeline.py --apply --check-existing --spec-output "$RUNNER_TEMP/specs" --report "$RUNNER_TEMP/report.json"
```

字段：`new_devices` / `supported`（含 `unknown_objectids`）/ `unsupported`（含 `reason`）/ `unreleased` / `fetch_failed` / `needs_manual_work` / `error` / `exit_code`。每个出口都会落盘。

`unsupported.reason` 除 `not_registered` / `no_objectids` 外，还有 `already_recorded`：同一个 model 出现了新的 `pd_id`（状态里已有该 model 的不支持结论）——**不自动继承旧结论**，交给人工核验。

判定一律读这个 JSON，不要解析中文控制台输出（设备名来自外部接口，可能含换行等会污染判定的字符）。

### GitHub Actions

`.github/workflows/device-check.yml`（每周一 03:17 UTC + 手动触发，手动默认 `dry_run=true`）：
新设备可支持 → bot 入库 + 打轻量 tag + 发 Release；不支持 → 开 issue + 提交状态；
有未识别 objectid → **整轮零写入**，只开 issue；抓取失败 → 整轮中止。

### 已入库型号的规格复查

每周在发现新设备之前，按 `device.py` 的实际型号（排除 Unknown），从公开目录选该型号数值版本最高的 `released` URN。新旧型号共用这一次索引，每个 URN 的正文在同一轮只取一次。新设备在目录缺项时沿用原 v1 接口，只有实际 404 才判定未注册。若由直查入库，基线标为 `direct`，直到目录有正式版本；已有发布记录的型号不会回退到 v1。

只复查已有型号（不需要运动健康目录或账号）：

```bash
python3 pipeline.py --only existing --spec-output /tmp/miband-specs --report /tmp/miband-spec-report.json
```

`existing_specs.changes` 对比广播属性和事件（IID > 1000），包括对象 ID、事件参数顺序、类型、取值范围和枚举含义；规格号未变也会核对内容。仅规格版本变化也会标明。与审核基线一致时不发通知；有变化时更新同一张 issue，不自动修改已有实体。新出现或定义变化而解析器不认识的对象会阻止当轮提交和发布。原有发布记录从目录消失或查询失败，整轮中止。

`released_specs.json` 记录**已核对的规格**，不等于解析器已实现的功能。新增设备随入库提交登记；既有型号的基线不自动推进。维护者在 Actions 的 `device-check-output` 下载报告、变化型号的原始规格和 `specs/candidate.json`，对照 `released_specs.json` 审核。处理完**全部差异**后再用候选文件替换基线；若只处理部分型号，只更新已审核的型号记录。下轮核对无差异后可关闭 issue。

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

- `not_supported.reason` 取值：`not_registered`（miot-spec 真实 HTTP 404，属正常现象）/ `no_objectids`（无 eiid>1000 对象，集成不支持）。
- step1 只跳过 `known_devices` 里的设备；step2 把确认 404/无 objectid 的设备同时写入两个分区（dry-run 也写，见上）。
- **抓取失败（结论未知）不写入任何分区**，下次仍作为新设备出现，脚本以退出码 2 提示重跑。
- **有有意义 objectid 但未 apply 的设备不登记**（如曾因 dry-run 未写入的设备）——下次仍作为新设备出现，直到 apply 成功后由 device.py 自然过滤。

## 未知 objectid 的人工补全

pipeline 打印 `存在 N 个未识别的 objectid` 时，该设备不会生成完整代码，需三处手工修改后重跑：

1. `parser.py` 的 `xiaomi_dataobject_dict` 加 `0xXXXX: eiidYYYY,`，并实现 converter 函数（签名 `def eiidYYYY(xobj: bytes, device: XiaomiBluetoothDeviceData, device_type: str) -> dict[str, Any]`，参考同文件的 `eiid1016`（binary sensor）、`eiid1105`（event）、`eiid1034`（sensor））。
2. `SKILL/pipeline.py` 的 `FUNC_TO_CLASS` 加 `"eiidYYYY": ("binary|event|sensor", "MiBand...DeviceClass.成员"),`。
3. 若需要新枚举成员，在 `const.py` 的 `MiBandBinarySensorDeviceClass` / `MiBandSensorDeviceClass` / `MiBandEventDeviceClass` 中补充。

模式事件（eiid1105）按该型号规格的参数枚举生成实体：0/1 是静音，2/3 是勿扰。参数类型或枚举含义不匹配时转人工核验。

## 代码规范

生成器（`render_entry` / `insert_entry_sorted`）已实现以下约定，人工改动 device.py 时保持一致：

- key 用大写十六进制 `0xXXXX`（文件既有 key 均大写），条目按 key 升序插入第一个更大 key 之前，而不是追加到 dict 末尾。
- 单元素/空列表用紧凑单行（`sensor=[MiBandSensorDeviceClass.BATTERY_CHARGING],`、`sensor=[],`），多元素才换行展开。
- `name` 取英文 `pd_name` 并去掉开头品牌前缀（Xiaomi/Mi/Redmi，见 `strip_brand`）；中文名不写入 device.py，仅用于提交信息与报告。
