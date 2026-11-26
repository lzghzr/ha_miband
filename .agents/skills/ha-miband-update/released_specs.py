"""Released MIoT specifications used by the weekly wearable inventory (stdlib only)."""

import json
from pathlib import Path
from urllib.parse import urlencode, quote
from urllib.request import urlopen

API = "https://miot-spec.org/miot-spec-v2/"
BASELINE = Path(__file__).with_name("released_specs.json")


def read_url(url):
    with urlopen(url, timeout=30) as response:
        return json.load(response)


def released_index():
    rows = read_url(API + "instances?status=all")["instances"]
    result = {}
    for row in rows:
        # An empty list means the model is listed, but has no released spec yet.
        releases = result.setdefault(row["model"], [])
        if row["status"] == "released":
            releases.append(row)
    if not any(result.values()):
        raise ValueError("发布目录为空")
    return result


def latest(index, model):
    rows = index.get(model, [])
    if not rows:
        return None
    version = max(int(r["version"]) for r in rows)
    urns = {r["type"] for r in rows if int(r["version"]) == version}
    if len(urns) != 1:
        raise ValueError(f"{model} 的 released v{version} 对应多个 URN：{sorted(urns)}")
    return urns.pop()


def instance(urn):
    doc = read_url(API + "instance?" + urlencode({"type": urn}))
    if doc.get("type") != urn or not doc.get("services"):
        raise ValueError(f"{urn}: 返回的规格与请求不符或没有 services")
    return doc


def type_id(obj):
    # MIoT type name + numeric ID; vendor and spec revision aren't payload fields.
    _, _, _, name, identifier, *_ = obj["type"].split(":")
    return name + ":" + identifier


def field(prop):
    result = {"type": type_id(prop), "format": prop["format"]}
    for key in ("unit", "value-range", "max-length", "access", "gatt-access"):
        if key in prop:
            result[key] = sorted(prop[key]) if key.endswith("access") else prop[key]
    if "value-list" in prop:
        result["values"] = {str(v["value"]): [v["description"], v.get("comment", "")]
                            for v in prop["value-list"]}
    return result


def snapshot(doc):
    objects = {}
    for svc in doc["services"]:
        props = {p["iid"]: p for p in svc.get("properties", [])}
        for group, base in (("properties", 0x3C18), ("events", 0x3E18)):
            for item in svc.get(group, []):
                iid = item["iid"]
                if iid <= 1000:
                    continue
                oid = f"0x{base + 1024 * svc['iid'] + iid:04X}"
                obj = {"service": type_id(svc), "siid": svc["iid"], "iid": iid}
                if group == "events":
                    obj.update(kind="event", type=type_id(item), arguments=[
                        {"piid": arg, **field(props[arg])} for arg in item["arguments"]
                    ])
                else:
                    obj.update(kind="property", **field(item))
                if oid in objects:
                    raise ValueError(f"{doc['type']}: 重复的 objectid {oid}")
                objects[oid] = obj
    return {"urn": doc["type"], "objects": dict(sorted(objects.items()))}


def save_snapshot(path, models):
    # Generated file: keep one complete broadcast object on each diffable line.
    def dump(value):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    lines = []
    for model, spec in sorted(models.items()):
        objects = ",\n".join(f"      {dump(k)}: {dump(v)}" for k, v in sorted(spec["objects"].items()))
        source = '    "source": "direct",\n' if spec.get("source") == "direct" else ""
        lines.append(f'  {dump(model)}: {{\n    "urn": {dump(spec["urn"])},\n{source}'
                     f'    "objects": {{\n{objects}\n    }}\n  }}')
    Path(path).write_text("{\n" + ",\n".join(lines) + "\n}\n", encoding="utf-8")


def differences(before, after, path=""):
    if before == after:
        return []
    if isinstance(before, list) and isinstance(after, list) and path.endswith("/arguments"):
        before, after = dict(enumerate(before)), dict(enumerate(after))
    if isinstance(before, dict) and isinstance(after, dict):
        return [row for key in sorted(before.keys() | after.keys())
                for row in differences(before.get(key), after.get(key), f"{path}/{key}")]
    return [{"field": path.lstrip("/"), "from": before, "to": after}]


def compare(previous, current, parsers):
    before = previous["objects"] if previous else {}
    after = current["objects"]
    added = sorted(after.keys() - before.keys())
    removed = sorted(before.keys() - after.keys())
    changed = sorted(k for k in before.keys() & after.keys() if before[k] != after[k])
    return {"from": previous["urn"] if previous else None, "to": current["urn"],
            "from_source": previous.get("source", "released") if previous else None,
            "to_source": current.get("source", "released"),
            "added": added, "removed": removed, "changed": changed,
            "details": {**{k: after[k]["type"] for k in added},
                        **{k: before[k]["type"] for k in removed},
                        **{k: differences(before[k], after[k]) for k in changed}},
            "unknown_objectids": [k for k in added + changed if int(k, 16) not in parsers]}


def audit(entries, index, baseline, parsers, get_instance, out=None):
    models = sorted({v["model"] for pid, v in entries.items() if pid != 0})
    if not models:
        raise ValueError("device.py 中没有已支持型号")
    current, changes = {}, {}
    if out:
        out.mkdir(parents=True, exist_ok=True)
    for model in models:
        previous = baseline.get(model)
        try:
            released = latest(index, model)
            if released and previous and previous.get("source", "released") == "released":
                current_version = int(released.rsplit(":", 1)[1])
                reviewed_version = int(previous["urn"].rsplit(":", 1)[1])
                if current_version < reviewed_version:
                    raise ValueError(f"目录最高版本 v{current_version} 低于已审核的 v{reviewed_version}")
            # Newly enrolled legacy devices may have only a direct instance.
            urn = released or (previous["urn"] if previous and previous.get("source") == "direct" else None)
            if urn is None:
                raise ValueError("公开目录找不到已发布规格")
            doc = get_instance(urn)
            spec = current[model] = snapshot(doc)
            if not released:
                spec["source"] = "direct"
        except (OSError, KeyError, TypeError, ValueError) as e:
            raise ValueError(f"{model}: {e}") from e
        if previous != spec:
            changes[model] = compare(previous, spec, parsers)
            if out:
                (out / (quote(model, safe="") + ".json")).write_text(
                    json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    if out:
        save_snapshot(out / "candidate.json", current)
    return {"checked": len(models), "changes": changes}
