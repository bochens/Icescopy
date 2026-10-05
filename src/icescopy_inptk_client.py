"""Separate-process INP client; transport and JSON work stay off the GUI thread."""
from collections import deque
import json
from pathlib import Path
import traceback
from shiboken6 import isValid

from PySide6.QtCore import QObject, QProcess, QThread, QTimer, Signal, Slot, Qt, QMetaObject, QEventLoop


class ToolkitTransport(QObject):
    started = Signal(int)
    response = Signal(int, object)
    failure = Signal(int, str)
    diagnostic = Signal(int, str)
    computed = Signal(int, int, object, str)

    def __init__(self):
        super().__init__()
        self.process = None
        self.epoch = 0
        self.buffer = bytearray()
        self.stopping = False

    @Slot(int, str)
    def start(self, epoch, path):
        self.close()
        self.epoch = epoch
        self.stopping = False
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.SeparateChannels)
        self.process.readyReadStandardOutput.connect(self.read)
        self.process.readyReadStandardError.connect(self.read_error)
        self.process.started.connect(lambda: self.started.emit(self.epoch))
        self.process.errorOccurred.connect(lambda _code: self.fail(self.process.errorString()))
        self.process.finished.connect(lambda code, _status: self.fail(f"Process exited (code {code})."))
        self.process.start(path, ['serve'])

    def fail(self, message):
        if not self.stopping:
            self.failure.emit(self.epoch, message)

    @Slot(int, object)
    def send(self, epoch, body):
        if epoch != self.epoch: return
        try:
            if not self.process or self.process.state() != QProcess.Running:
                raise ValueError('INP toolkit is not running.')
            self.process.write((json.dumps(body, allow_nan=False, separators=(',', ':'))+'\n').encode())
        except (ValueError, TypeError) as exc:
            self.fail(str(exc))

    def feed(self, data):
        self.buffer.extend(data)
        while b'\n' in self.buffer:
            line, _, self.buffer = self.buffer.partition(b'\n')
            if not line.strip(): continue
            try:
                reply = json.loads(line)
            except (ValueError, UnicodeError) as exc:
                self.fail(f'Invalid JSON response: {exc}'); return
            self.response.emit(self.epoch, reply)

    def read(self):
        self.feed(bytes(self.process.readAllStandardOutput()))

    def read_error(self):
        text = bytes(self.process.readAllStandardError()).decode('utf-8', errors='replace').strip()
        if text: self.diagnostic.emit(self.epoch, text[-8000:])

    @Slot(int, int, object)
    def compute(self, epoch, ident, function):
        # Immutable snapshots only: functions must never read or edit Qt widgets.
        try:
            self.computed.emit(epoch, ident, function(), '')
        except Exception as exc:
            self.computed.emit(epoch, ident, None, str(exc))

    @Slot()
    def close(self):
        self.stopping = True
        self.buffer.clear()
        if self.process:
            if self.process.state() != QProcess.NotRunning:
                self.process.kill(); self.process.waitForFinished(1000)
            self.process.deleteLater(); self.process = None


def close_transport(worker, thread):
    if isValid(thread) and thread.isRunning():
        if isValid(worker): QMetaObject.invokeMethod(worker, 'close', Qt.BlockingQueuedConnection)
        thread.quit(); thread.wait()


class InptkClient(QObject):
    ready = Signal(dict)
    failed = Signal(str)
    diagnostic = Signal(str)
    busyChanged = Signal(bool)
    start_requested = Signal(int, str)
    send_requested = Signal(int, object)
    stop_requested = Signal()
    compute_requested = Signal(int, int, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = ToolkitTransport()
        self.thread = QThread()
        self.worker.moveToThread(self.thread)
        self.thread.finished.connect(self.worker.deleteLater)
        self.start_requested.connect(self.worker.start)
        self.send_requested.connect(self.worker.send)
        self.stop_requested.connect(self.worker.close)
        self.compute_requested.connect(self.worker.compute)
        self.worker.started.connect(self._started)
        self.worker.response.connect(self._received)
        self.worker.failure.connect(self._worker_failed)
        self.worker.diagnostic.connect(self._diagnostic)
        self.worker.computed.connect(self._computed)
        worker, thread = self.worker, self.thread
        self.destroyed.connect(lambda: close_transport(worker, thread))
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(lambda: self._fail('INP toolkit did not respond to the connection test.'))
        self.path = ''
        self.capabilities = None
        self.pending = deque()
        self.active = None
        self.jobs = {}
        self.next_id = 0
        self.epoch = 0
        self.connecting = False
        self.closed = False

    @property
    def busy(self):
        return self.connecting or self.active is not None or bool(self.pending) or bool(self.jobs)

    def supports_option(self, command, flag):
        """Read the executable's advertised CLI options, without version guesses."""
        if not self.capabilities:
            return False
        options = self.capabilities["commands"][command]["options"]
        return any(flag in option["flags"] for option in options)

    def connect_executable(self, path):
        if self.closed: return
        path = str(Path(path).expanduser()) if path else ''
        if path == self.path and self.capabilities:
            self.ready.emit(self.capabilities); return
        self.stop()
        if not path or not Path(path).is_file():
            self.failed.emit('Choose an INP toolkit executable in Settings → INP toolkit client.'); return
        self.path = path
        self.connecting = True
        self.busyChanged.emit(True)
        if not self.thread.isRunning(): self.thread.start()
        self.start_requested.emit(self.epoch, path)
        self.timer.start(15000)

    def _started(self, epoch):
        if epoch == self.epoch: self.request(['capabilities'], self._connected)

    def _connected(self, reply):
        self.timer.stop()
        required = {'analyze', 'table', 'suggest-ranges', 'export-csv', 'save'}
        mode = reply.get('client_mode', {})
        if (not required.issubset(reply.get('commands', {})) or not mode.get('import')
                or not mode.get('release') or mode.get('memory_reference_prefix') != '@'):
            self._fail('Update INP toolkit: this client requires in-memory import and result references.'); return
        self.capabilities = reply
        self.connecting = False
        self.ready.emit(reply)

    def request(self, args, callback, error=None):
        self.request_body({'args': list(args)}, callback, error)

    def request_body(self, body, callback, error=None):
        if self.closed: return
        if not self.connecting and self.capabilities is None:
            (error or self.failed.emit)('INP toolkit is unavailable. Check its executable in Settings → INP toolkit client.'); return
        self.next_id += 1
        self.pending.append((self.next_id, body, callback, error))
        self._send_next()

    def _send_next(self):
        if self.active is not None or not self.pending: return
        self.active = self.pending.popleft()
        self.busyChanged.emit(True)
        ident, body, _callback, _error = self.active
        self.send_requested.emit(self.epoch, {'id': ident, **body})

    def compute(self, function, callback, error=None):
        if self.closed: return
        if not self.thread.isRunning(): self.thread.start()
        self.next_id += 1
        self.jobs[self.next_id] = (callback, error)
        self.busyChanged.emit(True)
        self.compute_requested.emit(self.epoch, self.next_id, function)

    def _computed(self, epoch, ident, value, message):
        if epoch != self.epoch or ident not in self.jobs: return
        callback, error = self.jobs.pop(ident)
        if message: (error or self.failed.emit)(message)
        else: self._callback(callback, value)
        if not self.busy: self.busyChanged.emit(False)

    def _received(self, epoch, reply):
        if epoch != self.epoch: return
        if (not self.active or not isinstance(reply, dict) or reply.get('id') != self.active[0]
                or reply.get('protocol_version') != 2 or reply.get('saved_format_version') != 4):
            self._fail('Invalid INP toolkit response: expected request ID, CLI protocol 2 and saved format 4.'); return
        _ident, _body, callback, error = self.active
        self.active = None
        if reply.get('status') != 'ok':
            (error or self.failed.emit)(reply.get('error', {}).get('message', 'INP toolkit could not complete the request.'))
        else:
            for warning in reply.get('warnings', []): self.diagnostic.emit(str(warning))
            self._callback(callback, reply)
        self._send_next()
        if not self.busy: self.busyChanged.emit(False)

    def _callback(self, callback, reply):
        try: callback(reply)
        except Exception as exc:
            self.diagnostic.emit(traceback.format_exc())
            self._fail(f'Could not handle the INP toolkit response: {exc}')

    def _worker_failed(self, epoch, message):
        if epoch == self.epoch: self._fail(message)

    def _diagnostic(self, epoch, message):
        if epoch == self.epoch: self.diagnostic.emit(message)

    def _fail(self, message):
        self.stop()
        self.failed.emit(message)

    def stop(self):
        self.epoch += 1
        self.connecting = False
        self.timer.stop()
        self.pending.clear(); self.jobs.clear(); self.active = None
        self.capabilities = None
        if self.thread.isRunning(): self.stop_requested.emit()
        self.busyChanged.emit(False)

    def shutdown(self):
        self.closed = True
        self.stop()
        close_transport(self.worker, self.thread)

    def request_wait(self, args):
        """Save-boundary helper; process events but prevent edits while saving."""
        if self.closed: raise ValueError('The INP client is closed.')
        if self.busy: raise ValueError('Wait for INP processing to finish before saving the session.')
        loop = QEventLoop()
        answer, errors = [], []
        def done(reply): answer.append(reply); loop.quit()
        def fail(message): errors.append(message); loop.quit()
        self.failed.connect(fail)
        timeout = QTimer()
        timeout.setSingleShot(True)
        timeout.timeout.connect(lambda: fail('Saving the INP result timed out. The existing session was not overwritten.'))
        timeout.start(60000)
        try:
            self.request(args, done, fail)
            if not answer and not errors: loop.exec(QEventLoop.ExcludeUserInputEvents)
        finally:
            timeout.stop()
            self.failed.disconnect(fail)
        if errors: raise ValueError(errors[0])
        return answer[0]

    def compute_wait(self, function):
        """Small save-boundary wrapper for file serialization on the worker."""
        if self.closed: raise ValueError('The INP client is closed.')
        loop = QEventLoop()
        answer, errors = [], []
        def done(value): answer.append(value); loop.quit()
        def fail(message): errors.append(message); loop.quit()
        self.failed.connect(fail)
        try:
            self.compute(function, done, fail)
            if not answer and not errors: loop.exec(QEventLoop.ExcludeUserInputEvents)
        finally:
            self.failed.disconnect(fail)
        if errors: raise ValueError(errors[0])
        return answer[0]
