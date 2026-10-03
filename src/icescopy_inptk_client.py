"""Asynchronous, separate-process INP toolkit CLI client. No scientific code."""
from collections import deque
import json
import traceback
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QTimer, Signal


class InptkClient(QObject):
    ready = Signal(dict)
    failed = Signal(str)
    diagnostic = Signal(str)
    busyChanged = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.SeparateChannels)
        self.process.readyReadStandardOutput.connect(self._read)
        self.process.readyReadStandardError.connect(self._stderr)
        self.process.errorOccurred.connect(self._process_error)
        self.process.finished.connect(self._finished)
        self.process.started.connect(self._started)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(lambda: self._fail("INP toolkit did not respond to the connection test."))
        self.path = ""
        self.capabilities = None
        self.pending = deque()
        self.active = None
        self.buffer = bytearray()
        self.next_id = 0
        self.stopping = False

    @property
    def busy(self):
        return self.active is not None or bool(self.pending)

    def connect_executable(self, path):
        path = str(Path(path).expanduser()) if path else ""
        if path == self.path and self.capabilities and self.process.state() == QProcess.Running:
            self.ready.emit(self.capabilities)
            return
        self.stop()
        if not path or not Path(path).is_file():
            self.failed.emit("Choose an INP toolkit executable in Settings → INP toolkit.")
            return
        self.path = path
        self.stopping = False
        self.process.setProgram(path)
        self.process.setArguments(["serve"])
        self.process.start()
        self.timer.start(15000)

    def _started(self):
        self.request(["capabilities"], self._connected)

    def _connected(self, reply):
        self.timer.stop()
        required = {"preview", "analyze", "table", "suggest-ranges", "export-csv"}
        if not required.issubset(reply.get("commands", {})):
            self._fail("This INP toolkit executable is missing required client commands.")
            return
        self.capabilities = reply
        self.ready.emit(reply)

    def request(self, args, callback, error=None):
        if self.process.state() != QProcess.Running:
            message = "INP toolkit is not connected. Use Connect or test its executable in Settings."
            (error or self.failed.emit)(message)
            return
        self.next_id += 1
        self.pending.append((self.next_id, list(args), callback, error))
        self._send_next()

    def _send_next(self):
        if self.active is not None or not self.pending:
            return
        self.active = self.pending.popleft()
        self.busyChanged.emit(True)
        ident, args, _callback, _error = self.active
        self.process.write((json.dumps({"id": ident, "args": args}, allow_nan=False) + "\n").encode())

    def _read(self):
        self.buffer.extend(bytes(self.process.readAllStandardOutput()))
        while b"\n" in self.buffer:
            line, _, rest = self.buffer.partition(b"\n")
            self.buffer = bytearray(rest)
            if not line.strip():
                continue
            try:
                reply = json.loads(line)
                if not self.active or not isinstance(reply, dict) or reply.get("id") != self.active[0]:
                    raise ValueError("Unexpected response identifier")
                if reply.get("protocol_version") != 2 or reply.get("saved_format_version") != 4:
                    raise ValueError("Requires CLI protocol 2 and saved format 4")
            except (ValueError, UnicodeError) as exc:
                self._fail(f"Invalid INP toolkit response: {exc}")
                return
            _ident, _args, callback, error = self.active
            self.active = None
            if reply.get("status") != "ok":
                message = reply.get("error", {}).get("message", "INP toolkit could not complete the request.")
                (error or self.failed.emit)(message)
            else:
                for warning in reply.get("warnings", []):
                    self.diagnostic.emit(str(warning))
                try:
                    callback(reply)
                except Exception as exc:
                    self.diagnostic.emit(traceback.format_exc())
                    self._fail(f"Could not display the INP toolkit response: {exc}")
                    return
            self._send_next()
            if not self.busy:
                self.busyChanged.emit(False)

    def _stderr(self):
        text = bytes(self.process.readAllStandardError()).decode("utf-8", errors="replace").strip()
        if text:
            self.diagnostic.emit(text[-8000:])

    def _process_error(self, _error):
        if not self.stopping:
            self._fail(f"INP toolkit process error: {self.process.errorString()}")

    def _finished(self, code, _status):
        if not self.stopping:
            self._fail(f"INP toolkit exited (code {code}). The last successful result is retained.")

    def _fail(self, message):
        self.stop()
        self.failed.emit(message)

    def stop(self):
        self.stopping = True
        self.timer.stop()
        self.pending.clear()
        self.active = None
        self.buffer.clear()
        self.capabilities = None
        if self.process.state() != QProcess.NotRunning:
            # Cross-platform cancellation. File-backed successful results survive
            # termination; the next connection starts a clean worker.
            self.process.kill()
            self.process.waitForFinished(1000)
        self.busyChanged.emit(False)
