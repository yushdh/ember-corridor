"""Build a relocatable Windows x64 folder and archive its exact contents."""
import hashlib
import argparse
from importlib.metadata import distribution
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
NAME = "EmberCorridor"


def copy_notices(folder):
    folder.mkdir()
    shutil.copyfile(ROOT/"tools/foley/README.md", folder/"武器拟音.txt")
    shutil.copyfile(Path(sys.base_prefix)/"LICENSE.txt", folder/"Python.txt")
    for name in ("arcade", "pyglet", "pillow", "pymunk", "cffi", "pycparser",
                 "attrs", "pytiled_parser", "typing_extensions", "pyinstaller"):
        dist = distribution(name)
        notices = [f for f in dist.files if ".dist-info/" in str(f)
                   and f.name.upper().startswith(("LICENSE", "COPYING", "NOTICE"))]
        target = folder / f"{name}-{dist.version}"
        target.mkdir()
        for f in notices:
            shutil.copyfile(dist.locate_file(f), target/f.name)
        if not notices:
            license_text = dist.metadata["License"]
            if not license_text:
                raise RuntimeError(f"No bundled license for {name}")
            (target/"LICENSE.txt").write_text(license_text, encoding="utf8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT/"dist")
    args = parser.parse_args()
    if sys.platform != "win32" or sys.maxsize <= 2**32:
        raise SystemExit("Use a 64-bit Windows Python environment.")
    build, dist = ROOT/"build", args.output_dir
    build.mkdir(exist_ok=True)
    dist.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=build) as tmp:
        stage = Path(tmp)
        cmd = [sys.executable, "-m", "PyInstaller", "--onedir", "--windowed", "--noupx",
               "--name", NAME, "--distpath", str(stage/"out"), "--specpath", str(stage),
               "--workpath", str(stage/"work"), "--paths", str(ROOT),
               "--copy-metadata", "arcade",
               "--add-data", f"{ROOT/'assets'}{os.pathsep}assets",
               "--exclude-module", "tkinter", str(ROOT/"tools/launch_windows.py")]
        subprocess.run(cmd, check=True, cwd=ROOT)
        bundle = stage/"out"/NAME
        # Arcade 3.3.3's hook treats the destination filename as a directory.
        # Its runtime opens arcade/VERSION, while the hook collected VERSION/VERSION.
        version_path = bundle/"_internal/arcade/VERSION"
        if version_path.is_dir():
            hook_dir = version_path.rename(stage/"arcade-version-from-hook")
            shutil.copyfile(hook_dir/"VERSION", version_path)
        assert version_path.read_bytes() == distribution("arcade").locate_file("arcade/VERSION").read_bytes()
        media = bundle/"_internal/assets"
        manifest = json.loads((media/"manifest.json").read_bytes())
        files = {row["path"] for row in manifest["assets"]} | {"assets/manifest.json"}
        packaged = {"assets/"+p.relative_to(media).as_posix() for p in media.rglob("*") if p.is_file()}
        assert files == packaged
        for p in files:
            assert (ROOT/p).read_bytes() == (bundle/"_internal"/p).read_bytes(), p
        copy_notices(bundle/"licenses")
        shutil.copyfile(ROOT/"docs/WINDOWS_RELEASE.md", bundle/"开始游戏.txt")
        (bundle/"首次试玩.cmd").write_bytes(b'@echo off\r\nstart "" "%~dp0EmberCorridor.exe" --first-play\r\n')
        archive = stage/f"{NAME}-Windows-x64.zip"
        with ZipFile(archive, "w", ZIP_DEFLATED, compresslevel=6) as zipfile:
            for p in sorted(bundle.rglob("*")):
                if p.is_file():
                    zipfile.write(p,p.relative_to(bundle.parent))
        destination = dist/archive.name
        archive.replace(destination)
        with destination.open("rb") as stream:
            print(destination, hashlib.file_digest(stream, "sha256").hexdigest())


if __name__ == "__main__":
    main()
