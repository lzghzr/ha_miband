"""Render the weekly spec-drift issue from the machine-readable pipeline report."""
import json
import sys
from pathlib import Path
from urllib.parse import urlencode


def link(urn):
    if not urn:
        return "尚无基线"
    url = "https://miot-spec.org/miot-spec-v2/instance?" + urlencode({"type": urn})
    return f"[v{urn.rsplit(':', 1)[-1]}]({url})"


def body(changes):
    lines = ["<!-- device-check:released-specs -->",
             "以下在库型号的已发布规格与审核基线不同。完整差异、变化型号的原始规格和候选基线见本次运行的 `device-check-output`。"]
    for model, change in sorted(changes.items()):
        lines.append(f"\n### `{model}`：{link(change['from'])} → {link(change['to'])}")
        if change["from_source"] and change["from_source"] != change["to_source"]:
            lines.append("- 规格来源：原直查接口 → 已发布目录。")
        for key, label in (("added", "新增"), ("removed", "移除")):
            for oid in change[key]:
                lines.append(f"- {label} `{oid}` {change['details'][oid].split(':')[0]}")
        for oid in change["changed"]:
            for row in change["details"][oid]:
                values = [json.dumps(row[key], ensure_ascii=False) for key in ("from", "to")]
                lines.append(f"- `{oid}` {row['field']}：`{values[0]}` → `{values[1]}`")
        if not (change["added"] or change["removed"] or change["changed"]):
            lines.append("- 广播属性、事件及参数未变。")
        if change["unknown_objectids"]:
            lines.append("- 解析器未识别：" + "、".join(change["unknown_objectids"]) + "；本轮不提交、不发布。")
    return "\n".join(lines)


if __name__ == "__main__":
    report = json.loads(Path(sys.argv[1]).read_bytes())
    full = body(report["existing_specs"]["changes"])
    # GitHub issue bodies have a size limit; the complete report is always an artifact.
    print(full if len(full.encode()) <= 60000 else
          full.encode()[:59000].decode(errors="ignore").rsplit("\n", 1)[0] +
          "\n\n其余差异见本次运行的 report.json。")
