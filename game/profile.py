"""Versioned permanent progress. Nothing from the current run is serialized."""
import json
import os
import tempfile
from collections import deque
from concurrent.futures import ThreadPoolExecutor
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
    def __init__(self, directory=None, *, background_lessons=False):
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
        self.writer = None
        self.writes = deque()
        self.route_job = None
        self.route_payload = None
        self.route_notice = ""
        try:
            if background_lessons:
                # Start the worker during the initial load. Starting its Windows
                # thread at first impact can stall the next graphics submission.
                self.writer = ThreadPoolExecutor(max_workers=1, thread_name_prefix="lessons")
                self.data, self.notice = self.writer.submit(self._load).result()
            else:
                self.data, self.notice = self._load()
        except (ValueError, OSError) as exc:
            self.report(exc)

    def _load(self):
        with locked(self.directory):
            return self._read_profile()

    def report(self, exc):
        self.notice = str(exc) if isinstance(exc, ValueError) else "存档读写失败，请检查目录或关闭另一窗口"

    def read(self):
        data, notice = self._read_profile()
        if notice:
            self.notice = notice
        return data

    def _read_profile(self):
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
                return data, "已从备份恢复炉谱和设置"
            return data, ""
        if damaged:
            raise ValueError("存档损坏，原文件已保留，本次仅在内存游玩")
        return Profile(), ""

    def remember(self, learned):
        self.poll()
        self.pending_learned.update(learned)
        self._write(background=True)

    def record_route(self, record):
        self.route_payload = json.dumps(record, indent=2).encode("utf8")
        self.route_notice = ""
        if self.writer is None:
            self.route_notice = self._write_route(self.route_payload)
        else:
            # Jobs execute in order. Only the newest route's outcome belongs in the HUD.
            self.route_job = self.writer.submit(self._write_route, self.route_payload)

    def _write_route(self, payload):
        try:
            atomic_write(self.directory / "last-route.json", payload)
            return ""
        except OSError:
            return "潮图记录写入失败，可在暂停页抄下种子"

    def update(self, *, unlock=False, setting=None, learned=(), bindings=None):
        self.poll(wait=True)
        self.pending_unlock |= unlock
        self.pending_learned.update(learned)
        if bindings is not None:
            self.pending_bindings = tuple(bindings)
        if setting is not None:
            index, value = setting
            self.pending_settings[index] = value
        self._write(background=False)

    def _write(self, background):
        # The writer sees only this immutable snapshot. New lessons can arrive
        # while it is flushing the previous snapshot to disk.
        settings = tuple(self.pending_settings.items())
        lessons = frozenset(self.pending_learned)
        shell = self.pending_unlock
        keys = self.pending_bindings

        def changed(profile):
            levels = list(profile.levels)
            for index, value in settings:
                levels[index] = value
            return replace(
                profile,
                shell_known=profile.shell_known or shell,
                levels=tuple(levels),
                learned=tuple(sorted(set(profile.learned) | lessons)),
                bindings=keys or profile.bindings,
            )

        self.data = changed(self.data)
        if background:
            if self.writer is None:
                self.writer = ThreadPoolExecutor(max_workers=1, thread_name_prefix="lessons")
            self.writes.append(self.writer.submit(self._commit, changed))
        else:
            self._accept(self._commit(changed))

    def _commit(self, changed):
        try:
            with locked(self.directory):
                previous, notice = self._read_profile()
                current = changed(previous)
                raw = json.dumps(asdict(current), indent=2).encode("utf8")
                prev = json.dumps(asdict(previous), indent=2).encode("utf8")
                # A new installation gets a usable backup on the very first save.
                atomic_write(self.backup, prev if self.main.exists() else raw)
                atomic_write(self.main, raw)
                return current, notice
        except (ValueError, OSError) as exc:
            return None, exc

    def _accept(self, result):
        current, notice = result
        if current is None:
            self.report(notice)
            return
        self.pending_learned.difference_update(current.learned)
        self.pending_unlock = False
        self.pending_settings.clear()
        self.pending_bindings = None
        self.data = replace(current, learned=tuple(sorted(set(current.learned) | self.pending_learned)))
        if notice or not self.notice.startswith("已从备份"):
            self.notice = notice

    def poll(self, wait=False):
        while self.writes and (wait or self.writes[0].done()):
            self._accept(self.writes.popleft().result())
        if self.route_job is not None and (wait or self.route_job.done()):
            self.route_notice = self.route_job.result()
            self.route_job = None

    def close(self):
        if self.writer is not None:
            self.poll(wait=True)
            self.writer.shutdown()
            self.writer = None
            if self.pending_learned:
                self.update()
            if self.route_notice:
                self.route_notice = self._write_route(self.route_payload)
