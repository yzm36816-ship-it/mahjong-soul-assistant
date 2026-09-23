"""Windows Graphics Capture, bound to a single authorized HWND (never a monitor)."""
import threading
import time
from PIL import Image


class WindowStream:
    def __init__(self, handle):
        from windows_capture import WindowsCapture
        self.handle = handle
        self.ready = threading.Event()
        self.lock = threading.Lock()
        self.image = None
        self.updated = 0.0
        self.closed = False
        self.session = WindowsCapture(window_hwnd=handle, monitor_index=None,
                                      cursor_capture=False, draw_border=True,
                                      minimum_update_interval=150)

        @self.session.event
        def on_frame_arrived(frame, capture_control):
            # Native buffers cease to be valid after callback; detach before returning.
            pixels = frame.frame_buffer[:, :, :3][:, :, ::-1].copy()
            image = Image.fromarray(pixels, "RGB")
            with self.lock:
                self.image = image
                self.updated = time.monotonic()
            self.ready.set()

        @self.session.event
        def on_closed():
            self.closed = True
            self.ready.set()

        self.control = self.session.start_free_threaded()

    def read(self):
        if not self.ready.wait(4):
            raise RuntimeError("游戏图形捕获暂未返回画面，请恢复游戏窗口。")
        with self.lock:
            if self.closed or self.image is None:
                raise RuntimeError("游戏窗口已关闭。")
            if time.monotonic() - self.updated > 4:
                raise RuntimeError("游戏图形画面暂未更新，正在重试。")
            return self.image.copy()

    def stop(self):
        self.control.stop()
        self.closed = True


_stream = None


def grab(handle):
    global _stream
    if _stream is None or _stream.handle != handle or _stream.closed:
        stop()
        _stream = WindowStream(handle)
    return _stream.read()


def stop():
    global _stream
    if _stream is not None:
        stream, _stream = _stream, None
        stream.stop()
