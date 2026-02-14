#!/usr/bin/env python3
"""
Read JUnit XML from allure-results, extract test cases, and for each test
generate an Allure *-result.json that includes steps parsed from the
corresponding Maestro flow YAML. Then remove the JUnit XML so Allure generate
only uses our enriched results (with steps).

On failure: Maestro's JUnit <failure>/<error> message and body are captured
and attached as statusDetails on the test and on the last step (failed step).
Usage: run from repo root after regression.sh (which produces *_report.xml).
"""

import json
import os
import re
import shutil
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "allure-results"
FLOWS_DIR = ROOT / ".maestro" / "flows"

# Execution order: regression.sh runs scripts alphabetically (assets, dashboard, profile)
REPORT_TO_FLOW_ORDER = [
    ("assets_report", "assets_test.yaml"),
    ("dashboard_report", "dashboard_test.yaml"),
    ("profile_report", "profile_test.yaml"),
]

# Maestro --test-output-dir per report (screenshots on failure)
REPORT_TO_MAESTRO_DIR = {
    "dashboard_report": "maestro-dashboard",
    "assets_report": "maestro-assets",
    "profile_report": "maestro-profile",
}

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp")
IMAGE_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".bmp": "image/bmp", ".tiff": "image/tiff", ".webp": "image/webp"}


def find_latest_screenshot(maestro_dir: Path) -> Path | None:
    """Return path to the most recently modified image in maestro_dir (or subdirs), or None."""
    if not maestro_dir.exists():
        return None
    latest = None
    latest_mtime = 0
    for f in maestro_dir.rglob("*"):
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS:
            m = f.stat().st_mtime
            if m > latest_mtime:
                latest_mtime = m
                latest = f
    return latest


def copy_screenshot_to_allure(maestro_dir: Path, attachment_uuid: str) -> tuple[str, str] | None:
    """
    Copy latest screenshot from maestro_dir to allure-results as <uuid>-attachment.<ext>.
    Returns (source_filename, mime_type) for Allure attachment, or None.
    """
    src = find_latest_screenshot(maestro_dir)
    if not src:
        return None
    ext = src.suffix.lower()
    mime = IMAGE_MIME.get(ext, "image/png")
    dest = RESULTS_DIR / f"{attachment_uuid}-attachment{ext}"
    shutil.copy2(src, dest)
    return (dest.name, mime)


def steps_from_flow_yaml(flow_path: Path) -> list[str]:
    """Parse Maestro flow YAML and return a list of step names (one per command)."""
    if not flow_path.exists():
        return []
    lines = flow_path.read_text(encoding="utf-8").splitlines()
    steps = []
    in_steps = False
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        line_stripped = line.rstrip()
        if line_stripped.strip() == "---":
            in_steps = True
            continue
        if not in_steps:
            continue
        # Comment line: use as step description
        if line_stripped.strip().startswith("#") and line_stripped.strip() != "#":
            steps.append(line_stripped.strip().lstrip("#").strip() or "Comment")
            continue
        # Maestro command: "- commandName:" or "- commandName: value"
        m = re.match(r"^\s*-\s+(\w+)\s*:\s*(.*)$", line_stripped)
        if m:
            cmd, rest = m.group(1), m.group(2).strip()
            if cmd == "runFlow":
                # Look at following indented lines for file: ../subflows/xxx.yaml
                subname = "subflow"
                j = i
                while j < len(lines) and lines[j].startswith((" ", "\t")):
                    sub = re.search(r"file:\s*\.\./subflows/(\S+)", lines[j])
                    if sub:
                        subname = sub.group(1).replace(".yaml", "")
                        break
                    j += 1
                steps.append(f"Run flow: {subname}")
            elif cmd == "launchApp":
                steps.append("Launch app (clear state)")
            elif cmd == "tapOn":
                detail = rest or ""
                if "id:" in detail:
                    id_match = re.search(r"id:\s*[\"']?([^\"'\s]+)", detail)
                    detail = id_match.group(1) if id_match else detail
                steps.append(f"Tap: {detail}" if detail else "Tap")
            elif cmd == "assertVisible":
                detail = rest or ""
                if not detail and i < len(lines):
                    # Multi-line: next lines have id: or text:
                    for j in range(i, min(i + 5, len(lines))):
                        if re.search(r"id:\s*[\"']?([^\"'\s]+)", lines[j]):
                            id_match = re.search(r"id:\s*[\"']?([^\"'\s]+)", lines[j])
                            detail = id_match.group(1) if id_match else ""
                            break
                        if "text:" in lines[j]:
                            text_match = re.search(r"text:\s*[\"']?([^\"'\n]+)", lines[j])
                            detail = (text_match.group(1).strip() if text_match else "").strip('"')
                            break
                if "id:" in detail:
                    id_match = re.search(r"id:\s*[\"']?([^\"'\s]+)", detail)
                    detail = id_match.group(1) if id_match else detail
                elif "text:" in detail:
                    text_match = re.search(r"text:\s*[\"']?([^\"'\n]+)", detail)
                    detail = text_match.group(1).strip() if text_match else detail
                steps.append(f"Assert visible: {detail}" if detail else "Assert visible")
            else:
                steps.append(cmd + (f" ({rest})" if rest else ""))
    return steps


def junit_to_allure_results():
    os.chdir(ROOT)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # 1) Collect all test cases in execution order (so total duration = sum of all)
    cases = []
    for report_name, flow_name in REPORT_TO_FLOW_ORDER:
        xml_path = RESULTS_DIR / f"{report_name}.xml"
        if not xml_path.exists():
            continue
        tree = ET.parse(xml_path)
        root = tree.getroot()
        suites = root.findall(".//testsuite") if root.tag == "testsuites" else [root]
        for suite in suites:
            for tc in suite.findall("testcase"):
                name = tc.get("name") or tc.get("id") or "Unnamed"
                # JUnit: failure is often indicated by <failure>/<error> child, not always by status attribute
                status_details = None
                for tag in ("failure", "error"):
                    node = tc.find(tag)
                    if node is not None:
                        msg = (node.get("message") or "").strip()
                        body = (node.text or "").strip()
                        status_details = {"message": msg or body or "Test failed", "trace": body if body != msg else ""}
                        break
                has_failure_node = status_details is not None
                status = (tc.get("status") or "SUCCESS").lower()
                if status == "success":
                    status = "passed"
                elif status == "failure":
                    status = "failed"
                elif has_failure_node:
                    status = "failed"  # Maestro may only write <failure> without status attribute
                else:
                    status = "passed"
                time_sec = float(tc.get("time", 0))
                cases.append((report_name, flow_name, name, status, time_sec, status_details))
        xml_path.unlink()

    if not cases:
        return

    # 2) Sequential timestamps so report top shows total run time (sum of all tests)
    total_sec = sum(c[4] for c in cases)
    now_ms = int(time.time() * 1000)
    base_start_ms = now_ms - int(total_sec * 1000)

    for report_name, flow_name, name, status, time_sec, status_details in cases:
        flow_path = FLOWS_DIR / flow_name
        step_names = steps_from_flow_yaml(flow_path)

        start_ms = base_start_ms
        stop_ms = base_start_ms + int(time_sec * 1000)
        base_start_ms = stop_ms

        uid = str(uuid.uuid4()).replace("-", "")[:24]
        history_id = f"Test Suite:{name}#{name}"
        full_name = f"Test Suite:{name}"

        num_steps = len(step_names)
        # When failed: find which step matches the error message (e.g. "X" is visible -> step containing X)
        failed_step_index = num_steps - 1  # default: last step
        if status == "failed" and status_details:
            msg = (status_details.get("message") or "") + " " + (status_details.get("trace") or "")
            # Maestro: "Assertion is false: \"coverage-percentage--xyz\" is visible" -> match step with that id/text
            for part in re.findall(r'"([^"]+)"', msg):
                if len(part) > 2:
                    for idx, step_name in enumerate(step_names):
                        if part in step_name:
                            failed_step_index = idx
                            break
                    else:
                        continue
                    break

        step_objects = []
        step_duration_ms = int(time_sec * 1000 / max(len(step_names), 1))
        for i, step_name in enumerate(step_names):
            s_start = start_ms + i * step_duration_ms
            s_stop = s_start + step_duration_ms
            if status != "failed":
                step_status = "passed"
            elif i == failed_step_index:
                step_status = "failed"  # red + X in Allure
            elif i > failed_step_index:
                step_status = "skipped"  # did not run
            else:
                step_status = "passed"
            step_payload = {"name": step_name, "status": step_status, "start": s_start, "stop": s_stop}
            if status == "failed" and i == failed_step_index and status_details:
                step_payload["statusDetails"] = status_details
            step_objects.append(step_payload)

        result = {
            "uuid": uid,
            "historyId": history_id,
            "fullName": full_name,
            "name": name,
            "status": status,
            "start": start_ms,
            "stop": stop_ms,
            "labels": [
                {"name": "suite", "value": "Test Suite"},
                {"name": "testClass", "value": name},
                {"name": "package", "value": name},
            ],
            "steps": step_objects,
        }
        if status == "failed" and status_details:
            result["statusDetails"] = status_details
        # On failure: attach Maestro screenshot from flow's test-output dir
        if status == "failed" and report_name in REPORT_TO_MAESTRO_DIR:
            maestro_dir = RESULTS_DIR / REPORT_TO_MAESTRO_DIR[report_name]
            att_uuid = str(uuid.uuid4()).replace("-", "")[:24]
            attachment_info = copy_screenshot_to_allure(maestro_dir, att_uuid)
            if attachment_info:
                source_name, mime_type = attachment_info
                att = {"name": "Screenshot (failure)", "source": source_name, "type": mime_type}
                result["attachments"] = [att]
                if failed_step_index < len(step_objects):
                    step_objects[failed_step_index]["attachments"] = [att]
        out_path = RESULTS_DIR / f"{uid}-result.json"
        out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    junit_to_allure_results()
