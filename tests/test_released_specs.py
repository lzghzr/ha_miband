"""Offline regressions for the shared new-device / existing-spec weekly check."""
import ast
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components/miband"
sys.path.insert(0, str(ROOT / ".agents/skills/ha-miband-update"))
sys.path.insert(0, str(ROOT / ".github/scripts"))
import pipeline
import released_specs as specs
import spec_issue

MODEL = "miwear.watch.o66cn"
URN = "urn:miot-spec-v2:device:watch:0000A07C:miwear-o66cn:2"
DOC = {"type": URN, "services": [{
    "iid": 9, "type": "urn:miot-spec-v2:service:device-status:0000791C:miwear-o66cn:2",
    "properties": [{"iid": 1, "type": "urn:miot-spec-v2:property:mode:00000008:miwear-o66cn:2",
                    "format": "uint8", "value-list": [
                        {"value": 2, "description": "No Disturb On", "comment": "开启勿扰模式"},
                        {"value": 3, "description": "No Disturb Off", "comment": "关闭勿扰模式"}]}],
    "events": [{"iid": 1105, "type": "urn:miot-spec-v2:event:mode-changed:00005100:miwear-o66cn:2",
                "description": "Mode Changed", "arguments": [1]}],
}]}
INDEX = {MODEL: [{"version": 2, "type": URN}]}
PID = 0x59FA


class ReleasedSpecs(unittest.TestCase):
    def test_select_released_numeric_version_not_order_or_debug(self):
        rows = [{"type": f"urn:{v}", "model": MODEL, "version": str(v), "status": status}
                for v, status in [(10, "released"), (2, "released"), (11, "debug")]]
        with patch.object(specs, "read_url", return_value={"instances": rows}):
            idx = specs.released_index()
        self.assertEqual(specs.latest(idx, MODEL), "urn:10")
        self.assertIsNone(specs.latest(idx, "other"))
        idx[MODEL].append({"version": 10, "type": "different"})
        with self.assertRaises(ValueError):
            specs.latest(idx, MODEL)

    def test_changed_enum_at_same_version_and_oid(self):
        before = specs.snapshot(DOC)
        changed = copy.deepcopy(DOC)
        changed["services"][0]["properties"][0]["value-list"][0].update(description="Mute On")
        diff = specs.compare(before, specs.snapshot(changed), {0x6669: "eiid1105"})
        self.assertEqual(diff["changed"], ["0x6669"])
        self.assertEqual(diff["details"]["0x6669"][0]["field"], "arguments/0/values/2")
        self.assertEqual(diff["unknown_objectids"], [])
        md = spec_issue.body({MODEL: diff})
        self.assertIn("No Disturb On", md)
        self.assertIn("Mute On", md)
        self.assertIn("0x6669", md)

    def test_registered_entity_tables_match_all_reviewed_models(self):
        baseline = json.loads(specs.BASELINE.read_bytes())
        tree = ast.parse((COMPONENT / "device.py").read_text())
        table = next(node.value for node in tree.body if isinstance(node, ast.AnnAssign)
                     and isinstance(node.target, ast.Name) and node.target.id == "DEVICE_TYPES")
        registered = {key.value: entry for key, entry in zip(table.keys, table.values)}
        parsers = pipeline.load_xiaomi_objectid_dict()
        entries = {pid: d for pid, d in pipeline.load_device_entries().items() if pid}
        self.assertEqual({d["model"] for d in entries.values()}, set(baseline))
        for pid, entry in entries.items():
            with self.subTest(model=entry["model"]):
                objects = baseline[entry["model"]]["objects"]
                known = {int(oid, 16): parsers.get(int(oid, 16)) for oid in objects}
                binary, events, sensors, unknown = pipeline.objectid_to_entry(known, objects)
                self.assertFalse(unknown)
                rendered = pipeline.render_entry(pid, entry["model"], entry["name"], binary,
                                                 events, sensors)
                generated = ast.parse("{" + rendered.strip() + "}", mode="eval").body.values[0]
                self.assertEqual(ast.dump(generated), ast.dump(registered[pid]))

    def test_mode_enum_override_requires_review(self):
        doc = copy.deepcopy(DOC)
        doc["services"][0]["properties"][0]["value-list"][0]["description"] = "Mute On"
        objects = specs.snapshot(doc)["objects"]
        binary, _, _, unknown = pipeline.objectid_to_entry({0x6669: "eiid1105"}, objects)
        self.assertEqual(unknown, [0x6669])
        self.assertFalse(binary)

    def test_arguments_and_removed_object(self):
        old = copy.deepcopy(DOC)
        service = old["services"][0]
        service["properties"].append(dict(service["properties"][0], iid=2, format="uint32"))
        service["events"][0]["arguments"].append(2)
        new = copy.deepcopy(old)
        new["services"][0]["events"][0]["arguments"].reverse()
        self.assertEqual(specs.compare(specs.snapshot(old), specs.snapshot(new), {})["changed"],
                         ["0x6669"])
        del new["services"][0]["events"]
        new["services"][0]["actions"] = [dict(service["events"][0])]
        self.assertEqual(specs.compare(specs.snapshot(old), specs.snapshot(new), {})["removed"],
                         ["0x6669"])

    def test_known_released_404_not_misclassified(self):
        with HTTPError("u", 404, "", {}, None) as error, contextlib.redirect_stderr(io.StringIO()):
            get = Mock(side_effect=error)
            self.assertEqual(pipeline.fetch_instance(MODEL, INDEX, get)[1], "error")
            self.assertEqual(pipeline.fetch_instance(MODEL, {}, get)[1], "not_registered")
        get = Mock(return_value=DOC)
        self.assertEqual(pipeline.fetch_instance(MODEL, {}, get)[1], "ok")
        self.assertTrue(get.call_args.args[0].endswith(":1"))
        with patch.object(specs, "read_url", return_value=DOC), self.assertRaises(ValueError):
            specs.instance("wrong-urn")

    def test_no_silent_downgrade_on_missing_release(self):
        entries = {PID: {"model": MODEL}}
        previous = specs.snapshot(DOC)
        with self.assertRaisesRegex(ValueError, MODEL):
            specs.audit(entries, {}, {MODEL: previous}, {}, Mock())
        direct = dict(previous, source="direct")
        actual = specs.audit(entries, INDEX, {MODEL: direct}, {}, Mock(return_value=DOC))
        self.assertEqual(actual["changes"][MODEL]["from_source"], "direct")
        self.assertEqual(actual["changes"][MODEL]["to_source"], "released")

    def test_older_release_stops_before_discovery_or_writes(self):
        baseline = {MODEL: specs.snapshot(DOC)}
        older = URN.rsplit(":", 1)[0] + ":1"
        get = Mock()
        report, saved, candidate, catalog_calls = self.run_week(
            baseline, {PID: {"model": MODEL}}, [],
            {MODEL: [{"version": 1, "type": older}]}, get, {}, apply=True,
        )
        self.assertEqual(report["exit_code"], 2)
        self.assertIn("低于已审核", report["error"])
        self.assertEqual(saved, baseline)
        self.assertIsNone(candidate)
        self.assertEqual(catalog_calls, 0)
        get.assert_not_called()

    def run_week(self, base, entries, rows, index, getter, known, only=False, apply=False,
                 directory=None, weekly=True):
        with contextlib.ExitStack() as stack:
            td = directory or Path(stack.enter_context(tempfile.TemporaryDirectory()))
            baseline, report = td / "baseline.json", td / "report.json"
            device = td / "device.py"
            if not device.exists():
                specs.save_snapshot(baseline, base)
                device.write_bytes((COMPONENT / "device.py").read_bytes())
            for module, attr, value in [
                (pipeline, "load_device_entries", Mock(return_value={0: {"model": "Unknown"}, **entries})),
                (pipeline, "load_xiaomi_objectid_dict", Mock(return_value=known)),
                (pipeline, "DEVICES_JSON", str(td / "state.json")), (pipeline, "DEVICE_FILE", str(device)),
                (specs, "BASELINE", baseline), (specs, "instance", getter),
            ]:
                stack.enter_context(patch.object(module, attr, value))
            idx = stack.enter_context(patch.object(specs, "released_index", return_value=index))
            catalog = stack.enter_context(patch.object(pipeline.get_config_info_by_category, "fetch_catalog",
                                                       return_value={"result": {"list": rows}}))
            args = ["pipeline", "--report", str(report),
                    "--zh", str(td / "zh"), "--en", str(td / "en")]
            if weekly:
                args += ["--spec-output", str(td / "out")]
                args.extend(["--only", "existing"] if only else ["--check-existing"])
            if apply:
                args.append("--apply")
            stack.enter_context(patch.object(sys, "argv", args))
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = pipeline.main()
            idx.assert_called_once_with()
            result = json.loads(report.read_bytes())
            self.assertEqual(result["exit_code"], code)
            output = td / "out/candidate.json"
            return result, json.loads(baseline.read_bytes()), (json.loads(output.read_bytes())
                    if output.exists() else None), catalog.call_count

    def test_no_new_pid_still_reports_unknown_and_keeps_baseline(self):
        base = {MODEL: {"urn": URN[:-1] + "1", "objects": {}}}
        row = {"pd_id": PID, "model": MODEL, "pd_name": "Band 10"}
        result, saved, candidate, _ = self.run_week(base, {PID: row}, [row], INDEX,
                                                   Mock(return_value=DOC), {})
        self.assertEqual(result["new_devices"], [])
        self.assertEqual(result["existing_specs"]["changes"][MODEL]["unknown_objectids"], ["0x6669"])
        self.assertTrue(result["needs_manual_work"])
        self.assertEqual(base, saved)
        self.assertNotEqual(base, candidate)

    def test_one_fetch_for_existing_model_also_seen_as_new_pid(self):
        row = {"pd_id": PID + 20, "model": MODEL, "pd_name": "Band 10"}
        get = Mock(return_value=DOC)
        base = {MODEL: specs.snapshot(DOC)}
        report, saved, _, _ = self.run_week(base, {PID: {"model": MODEL}}, [row],
                                            INDEX, get, {0x6669: "eiid1105"})
        get.assert_called_once_with(URN)
        self.assertEqual(report["existing_specs"], {"checked": 1, "changes": {}})
        self.assertEqual(report["supported"][0]["pd_id"], PID + 20)
        self.assertEqual(saved, base)

    def test_new_model_enrolled_without_accepting_old_drift(self):
        row = {"pd_id": 0x9999, "model": "new.watch.model", "pd_name": "New"}
        new_urn = URN.replace("miwear-o66cn", "new-model")
        idx = {**INDEX, row["model"]: [{"version": 2, "type": new_urn}]}
        base = {MODEL: {"urn": URN[:-1]+"1", "objects": {}}}
        get = Mock(side_effect=lambda urn: dict(DOC, type=urn))
        result, saved, candidate, _ = self.run_week(base, {PID: {"model": MODEL}}, [row], idx,
                                                   get, {0x6669: "eiid1105"}, apply=True)
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(saved[MODEL], base[MODEL])
        self.assertEqual(saved[row["model"]], candidate[row["model"]])
        self.assertEqual(candidate[MODEL], specs.snapshot(DOC))
        self.assertEqual(get.call_count, 2)

    def test_released_fetch_failure_stops_before_discovery(self):
        base = {MODEL: specs.snapshot(DOC)}
        result, saved, candidate, calls = self.run_week(
            base, {PID: {"model": MODEL}}, [], INDEX, Mock(side_effect=OSError("timeout")), {})
        self.assertEqual(result["exit_code"], 2)
        self.assertIn(MODEL, result["error"])
        self.assertEqual(saved, base)
        self.assertIsNone(candidate)
        self.assertEqual(calls, 0)

    def test_draft_rechecked_after_release_and_plain_apply_enrolls_it(self):
        model = "new.watch.model"
        urn = URN.replace("miwear-o66cn", "new-model")
        catalog = [{"pd_id": 0x9999, "model": model, "pd_name": "New"}]
        rows = [dict(INDEX[MODEL][0], model=MODEL, status="released"),
                {"model": model, "version": 2, "type": urn, "status": "preview"}]
        base = {MODEL: specs.snapshot(DOC)}
        get = Mock(side_effect=lambda u: dict(DOC, type=u))
        with tempfile.TemporaryDirectory() as td:
            directory = Path(td)
            for status in ("debug", "preview", "released"):
                rows[1]["status"] = status
                with patch.object(specs, "read_url", return_value={"instances": rows}):
                    index = specs.released_index()
                result, saved, _, _ = self.run_week(
                    base, {}, catalog, index, get, {0x6669: "eiid1105"},
                    apply=True, weekly=False, directory=directory,
                )
                self.assertEqual(result["exit_code"], 0)
                self.assertFalse(result["unsupported"] or result["fetch_failed"])
                self.assertFalse((directory / "state.json").exists())
                table = (directory / "device.py").read_text()
                if status != "released":
                    get.assert_not_called()
                    self.assertEqual(result["unreleased"], [{"model": model, "pd_id": 0x9999}])
                    self.assertNotIn("0x9999:", table)
                    self.assertEqual(saved, base)
                else:
                    get.assert_called_once_with(urn)
                    self.assertEqual(result["unreleased"], [])
                    self.assertEqual(table.count("0x9999:"), 1)
                    self.assertEqual(saved, {**base, model: specs.snapshot(dict(DOC, type=urn))})

    def test_blocked_apply_preserves_device_table_and_baseline(self):
        good = {"model": "new.watch.good", "pd_id": 0x9999, "pd_name": "Good"}
        bad = {"model": "new.watch.bad", "pd_id": 0x9998, "pd_name": "Bad"}
        original = (COMPONENT / "device.py").read_bytes()
        for problem in ("new_unknown", "existing_unknown", "fetch_failed"):
            with self.subTest(problem=problem), tempfile.TemporaryDirectory() as td:
                directory = Path(td)
                base = {MODEL: specs.snapshot(DOC)}
                def get(urn):
                    doc = copy.deepcopy(DOC)
                    if problem == "fetch_failed" and "new-bad" in urn:
                        raise TimeoutError
                    if ((problem == "new_unknown" and "new-bad" in urn)
                            or (problem == "existing_unknown" and urn == URN)):
                        doc["services"][0]["events"][0]["iid"] += 1
                    return dict(doc, type=urn)
                result, saved, _, _ = self.run_week(
                    base, {PID: {"model": MODEL}}, [good, bad], INDEX, get,
                    {0x6669: "eiid1105"}, apply=True, directory=directory,
                )
                self.assertTrue(any(d["model"] == good["model"] for d in result["supported"]))
                self.assertEqual(result["needs_manual_work"], problem != "fetch_failed")
                self.assertEqual(result["exit_code"], 2 if problem == "fetch_failed" else 0)
                self.assertEqual((directory / "device.py").read_bytes(), original)
                self.assertEqual(saved, base)

    def test_apply_restores_table_if_second_replace_fails(self):
        with tempfile.TemporaryDirectory() as td:
            table, baseline = Path(td) / "device.py", Path(td) / "baseline.json"
            table.write_bytes(b"old table")
            baseline.write_bytes(b"old baseline")
            replace = Path.replace
            def fail_baseline(src, dst):
                if dst == baseline:
                    raise PermissionError
                return replace(src, dst)
            with (patch.object(pipeline, "DEVICE_FILE", table), patch.object(specs, "BASELINE", baseline),
                  patch.object(Path, "replace", fail_baseline), self.assertRaises(PermissionError)):
                pipeline.apply_entries("new table", {MODEL: specs.snapshot(DOC)})
            self.assertEqual(table.read_bytes(), b"old table")
            self.assertEqual(baseline.read_bytes(), b"old baseline")


if __name__ == "__main__":
    unittest.main()
