"""Run the ZIP in a separate directory with an isolated profile and no Python on PATH."""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import time
from zipfile import ZipFile


def title_window(process):
    user = ctypes.windll.user32
    windows = []
    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(hwnd, _):
        pid = wintypes.DWORD()
        user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == process.pid and user.IsWindowVisible(hwnd):
            text = ctypes.create_unicode_buffer(512)
            user.GetWindowTextW(hwnd, text, 512)
            if "盐炉渡口" in text.value:
                windows.append(hwnd)
        return True
    user.EnumWindows(visit, 0)
    return windows[0] if windows else None


def wait_for(test, process, seconds=30):
    end = time.monotonic()+seconds
    while time.monotonic() < end:
        result = test()
        if result:
            return result
        if process.poll() is not None:
            raise RuntimeError(f"Early process exit: {process.returncode}")
        time.sleep(0.08)
    raise TimeoutError("The game did not reach the expected state")


def key(hwnd, vk, down):
    user = ctypes.windll.user32
    flags = 1 | (user.MapVirtualKeyW(vk, 0) << 16) | (0 if down else 0xc0000000)
    if not user.PostMessageW(hwnd, 0x100 if down else 0x101, vk, flags):
        raise ctypes.WinError()


def tap(hwnd, vk):
    key(hwnd, vk, True)
    key(hwnd, vk, False)


def regular_start(exe, cwd, env, level):
    profile = Path(env["LOCALAPPDATA"])/"EmberCorridor"
    def saved():
        path = profile/"profile.json"
        if path.is_file():
            data = json.loads(path.read_bytes())
            return data if data["levels"][2] == level and "move" in data["learned"] else None

    process = subprocess.Popen([exe,"--seed","17"], cwd=cwd, env=env)
    try:
        hwnd = wait_for(lambda: title_window(process), process)
        # Allow texture initialization to finish before posting the first menu key.
        time.sleep(1.25)
        tap(hwnd, 13)
        wait_for(lambda: (profile/"last-route.json").exists(), process)
        key(hwnd, ord("D"), True)
        time.sleep(0.30)
        key(hwnd, ord("D"), False)
        tap(hwnd, 27)
        time.sleep(0.12)
        tap(hwnd, 0x72)  # F3 increments saved volume modulo four.
        data = wait_for(saved, process)
        ctypes.windll.user32.PostMessageW(hwnd, 0x10, 0, 0)
        assert process.wait(timeout=15) == 0
        return dict(volume=data["levels"][2], learned=data["learned"], exit_code=process.returncode)
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)


def check_modes(exe, cwd, env):
    report = {}
    for name in ("practice", "skirmish", "classic"):
        local = Path(env["LOCALAPPDATA"]).parent / ("profile-" + name)
        profile = local / "EmberCorridor"
        process = subprocess.Popen([exe, "--"+name], cwd=cwd, env={**env, "LOCALAPPDATA":str(local)})
        try:
            hwnd = wait_for(lambda: title_window(process), process)
            time.sleep(1.25)
            if name == "classic":
                tap(hwnd, 13)
                wait_for(lambda: (profile/"last-route.json").exists(), process)
            key(hwnd, ord("D"), True)
            time.sleep(0.40)
            key(hwnd, ord("D"), False)
            if name != "practice":
                tap(hwnd, ord("J"))
            expected = {"move"} if name == "practice" else {"move", "attack"}
            def learned():
                p = profile/"profile.json"
                return p.exists() and expected <= set(json.loads(p.read_bytes())["learned"])
            wait_for(learned, process)
            route = profile/"last-route.json"
            if name == "classic":
                saved = json.loads(route.read_bytes())
                assert saved["seed"] is None and saved["templates"] == ["gate","pump","sluice","gallery","bell"]
            else:
                assert not route.exists()
            ctypes.windll.user32.PostMessageW(hwnd, 0x10, 0, 0)
            assert process.wait(timeout=15) == 0
            report[name] = dict(learned=sorted(expected), exit_code=process.returncode)
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
    return report


def check_first_play(exe, cwd, env):
    local = Path(env["LOCALAPPDATA"])
    formal = local / "EmberCorridor"
    before = {p.name: p.read_bytes() for p in formal.iterdir() if p.is_file()}
    assert "profile.json" in before
    sessions = local / "EmberCorridor-Playtests"
    records = []
    for start in (True, False):
        existing = set(sessions.glob("*/session.json"))
        process = subprocess.Popen([exe, "--first-play"], cwd=cwd, env=env)
        try:
            hwnd = wait_for(lambda: title_window(process), process)
            time.sleep(1.25)
            if start:
                tap(hwnd, 13)
                wait_for(lambda: set(sessions.glob("*/session.json")) - existing, process)
                key(hwnd, ord("D"), True)
                time.sleep(0.3)
                key(hwnd, ord("D"), False)
                tap(hwnd, 27)
                time.sleep(0.2)
            ctypes.windll.user32.PostMessageW(hwnd, 0x10, 0, 0)
            assert process.wait(timeout=15) == 0
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
        path, = set(sessions.glob("*/session.json")) - existing
        result = json.loads(path.read_bytes())
        assert result["outcome"] == ("closed" if start else "closed_before_start")
        if start:
            assert result["pause_ms"] > 0 and result["play_ms"] > 0
            assert json.loads((path.parent/"profile/last-route.json").read_bytes())["seed"] is None
        records.append(result)
    assert before == {p.name: p.read_bytes() for p in formal.iterdir() if p.is_file()}
    return dict(source="automated", formal_profile_byte_identical=True, sessions=records)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip", type=Path)
    parser.add_argument("evidence", type=Path)
    checks = parser.add_mutually_exclusive_group()
    checks.add_argument("--modes-only", action="store_true")
    checks.add_argument("--blade-detour", action="store_true",
                        help="Run the handmade five-room detour for the end-to-end playthrough.")
    args = parser.parse_args()
    out = args.evidence.resolve()
    out.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="潮钟线 发行业测 ") as tmp:
        root = Path(tmp)
        cwd = root/"独立工作目录"
        cwd.mkdir()
        with ZipFile(args.zip) as z:
            assert z.testzip() is None
            z.extractall(root)
        exe = root/"EmberCorridor/EmberCorridor.exe"
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        env.pop("PYTHONHOME", None)
        env.pop("VIRTUAL_ENV", None)
        windows = Path(os.environ["SystemRoot"])
        env.update(LOCALAPPDATA=str(root/"local"), PATH=os.pathsep.join(
            [str(windows/"System32"), str(windows)]))
        assert not shutil.which("python", path=env["PATH"])
        modes = check_modes(exe, cwd, env)
        (out/"modes.json").write_text(json.dumps(modes,indent=2), encoding="utf8")
        if args.modes_only:
            return
        launches = [regular_start(exe, cwd, env, volume) for volume in (3, 0)]
        if (exe.parent / "首次试玩.cmd").is_file():
            data = check_first_play(exe, cwd, env)
            (out/"first-play.json").write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                                encoding="utf8")
        timing = root/"timing.json"
        subprocess.run([exe, "--profile-render", timing], cwd=cwd, env=env, timeout=90, check=True)
        shutil.copyfile(timing, out/"packaged-timing.json")
        report = root/"验收"
        route_args = ["--blade-detour"] if args.blade_detour else []
        result = subprocess.run([exe, "--verify-install", report, *route_args], cwd=cwd, env=env,
                                timeout=240, check=False)
        if result.returncode:
            error = report/"error.txt"
            raise RuntimeError(error.read_text(encoding="utf8") if error.exists() else result.returncode)
        data = json.loads((report/"installed.json").read_bytes())
        assert data["frozen"] and not any(cwd.iterdir())
        assert data["route"]["seed"] == (None if args.blade_detour else 17)
        for p in report.iterdir():
            shutil.copyfile(p, out/p.name)
        with args.zip.open("rb") as f:
            digest = hashlib.file_digest(f, "sha256").hexdigest()
        record = dict(archive=args.zip.name, bytes=args.zip.stat().st_size, sha256=digest,
                      normal_launches=launches, independent_cwd=True, python_on_path=False)
        (out/"distribution.json").write_text(json.dumps(record,indent=2), encoding="utf8")
        print(record, data)


if __name__ == "__main__":
    main()
