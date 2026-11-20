"""Versioned permanent progress. Nothing from the current run is serialized."""
import json
import os
import tempfile
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from .guidance import DEFAULT_KEYS, KEY_NAMES, LESSONS


@dataclass(frozen=True)
class Profile:
    version: int = 2
    shell_known: bool = False
    levels: tuple = (2, 2, 2, 2)
    learned: tuple = ()
    bindings: tuple = DEFAULT_KEYS


class NewerVersion(ValueError):
    pass


def decode(data):
    obj = json.loads(data)
    if not isinstance(obj, dict) or type(obj.get("version")) is not int:
        raise ValueError("缺少版本号")
    if obj["version"] > 2:
        raise NewerVersion("存档来自较新版本，已保留原文件")
    levels = obj.get("levels")
    if (
        obj["version"] not in (1, 2)
        or type(obj.get("shell_known")) is not bool
        or not isinstance(levels, list)
        or len(levels) != 4
        or any(type(n) is not int or not 0 <= n <= 3 for n in levels)
    ):
        raise ValueError("无效的炉谱或设置")
    learned = obj.get("learned", []) if obj["version"] == 1 else obj.get("learned")
    keys = obj.get("bindings", list(DEFAULT_KEYS)) if obj["version"] == 1 else obj.get("bindings")
    if (not isinstance(learned, list) or not all(isinstance(s, str) and s in LESSONS for s in learned)
            or not isinstance(keys, list) or len(keys) != len(DEFAULT_KEYS)
            or not all(isinstance(k, str) and k in KEY_NAMES for k in keys)
            or len(set(keys)) != len(keys)):
        raise ValueError("无效的教学或按键记录")
    return Profile(shell_known=obj["shell_known"], levels=tuple(levels),
                   learned=tuple(sorted(set(learned))), bindings=tuple(keys))


def atomic_write(path, data):
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".profile-", delete=False) as f:
        tmp = Path(f.name)
        try:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        except BaseException:
            f.close()
            tmp.unlink(missing_ok=True)
            raise
    try:
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


@contextmanager
def locked(directory):
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "profile.lock").open("a+b") as lock:
        lock.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield  # Closing the handle also releases the lock on exceptions.


class ProfileStore:
    def __init__(self, directory=None):
        self.directory = (
            Path(directory)
            if directory is not None
            else Path(os.environ.get("LOCALAPPDATA", Path.home())) / "EmberCorridor"
        )
        self.main = self.directory / "profile.json"
        self.backup = self.directory / "profile.bak"
        self.data = Profile()
        self.notice = ""
        self.pending_unlock = False
        self.pending_settings = {}
        self.pending_learned = set()
        self.pending_bindings = None
        try:
            with locked(self.directory):
                self.data = self.read()
        except (ValueError, OSError) as exc:
            self.report(exc)

    def report(self, exc):
        self.notice = str(exc) if isinstance(exc, ValueError) else "存档读写失败，请检查目录或关闭另一窗口"

    def read(self):
        damaged = False
        for path in (self.main, self.backup):
            try:
                raw = path.read_bytes()
                data = decode(raw)
            except FileNotFoundError:
                continue
            except NewerVersion:
                raise
            except (ValueError, RecursionError):
                damaged = True
                continue
            if path == self.backup:
                atomic_write(self.main, raw)
                self.notice = "已从备份恢复炉谱和设置"
            return data
        if damaged:
            raise ValueError("存档损坏，原文件已保留，本次仅在内存游玩")
        return Profile()

    def update(self, *, unlock=False, setting=None, learned=(), bindings=None):
        self.pending_unlock |= unlock
        self.pending_learned.update(learned)
        if bindings is not None:
            self.pending_bindings = tuple(bindings)
        if setting is not None:
            index, value = setting
            self.pending_settings[index] = value

        def changed(profile):
            levels = list(profile.levels)
            for index, value in self.pending_settings.items():
                levels[index] = value
            return replace(
                profile,
                shell_known=profile.shell_known or self.pending_unlock,
                levels=tuple(levels),
                learned=tuple(sorted(set(profile.learned) | self.pending_learned)),
                bindings=self.pending_bindings or profile.bindings,
            )

        desired = changed(self.data)
        try:
            with locked(self.directory):
                previous = self.read()
                current = changed(previous)
                raw = json.dumps(asdict(current), indent=2).encode("utf8")
                prev = json.dumps(asdict(previous), indent=2).encode("utf8")
                # A new installation gets a usable backup on the very first save.
                atomic_write(self.backup, prev if self.main.exists() else raw)
                atomic_write(self.main, raw)
                self.data = current
                self.pending_unlock = False
                self.pending_settings.clear()
                self.pending_learned.clear()
                self.pending_bindings = None
                if not self.notice.startswith("已从备份"):
                    self.notice = ""
        except (ValueError, OSError) as exc:
            self.data = desired
            self.report(exc)
