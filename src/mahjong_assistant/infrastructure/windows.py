"""Capture only an explicitly selected game HWND, never the whole desktop."""
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import sys
from PIL import ImageGrab, ImageStat


@dataclass
class Window:
    handle: int
    title: str


def process_name(handle: int) -> str:
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(handle, ctypes.byref(pid))
    process = kernel32.OpenProcess(0x1000, False, pid.value)
    if not process:
        return ""
    try:
        length = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(length.value)
        if kernel32.QueryFullProcessImageNameW(process, 0, buffer, ctypes.byref(length)):
            return buffer.value.replace("\\", "/").rsplit("/", 1)[-1].lower()
        return ""
    finally:
        kernel32.CloseHandle(process)


EXCLUDED_PROCESSES = {"chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe", "codex.exe"}


def game_windows() -> list[Window]:
    if sys.platform != "win32":
        return []
    user32 = ctypes.windll.user32
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    results = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @callback_type
    def visit(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            title = ctypes.create_unicode_buffer(user32.GetWindowTextLengthW(hwnd) + 1)
            user32.GetWindowTextW(hwnd, title, len(title))
            text = title.value
            if any(key in text.lower() for key in ("雀魂", "mahjong soul", "mahjongsoul", "じゃんたま")) and "助手" not in text:
                if process_name(int(hwnd)) not in EXCLUDED_PROCESSES:
                    results.append(Window(int(hwnd), text))
        return True

    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.EnumWindows(visit, 0)
    return results


def capture(handle: int):
    if sys.platform != "win32":
        raise RuntimeError("实时窗口读取仅支持 Windows。可以使用截图导入。")
    user32 = ctypes.windll.user32
    for name in ("IsWindow", "IsIconic", "GetWindowTextLengthW"):
        getattr(user32, name).argtypes = [wintypes.HWND]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    if not user32.IsWindow(handle) or user32.IsIconic(handle):
        raise RuntimeError("游戏窗口已关闭或最小化，请恢复窗口后重试。")
    if process_name(handle) in EXCLUDED_PROCESSES:
        raise RuntimeError("当前选择不是桌面游戏客户端，请重新选择雀魂窗口。")
    title = ctypes.create_unicode_buffer(user32.GetWindowTextLengthW(handle) + 1)
    user32.GetWindowTextW(handle, title, len(title))
    if not any(key in title.value.lower() for key in ("雀魂", "mahjong soul", "mahjongsoul", "じゃんたま")) or "助手" in title.value:
        raise RuntimeError("窗口身份已变化，请重新选择雀魂窗口。")
    # GPU-rendered Steam windows often return black through PrintWindow.
    # Prefer Windows Graphics Capture; keep the old HWND API as a compatibility fallback.
    try:
        from .gpu_capture import grab
        frame = grab(handle)
    except Exception:
        frame = ImageGrab.grab(window=handle).convert("RGB")
    if min(frame.size) < 300 or max(ImageStat.Stat(frame.resize((32, 32))).stddev) < 3:
        raise RuntimeError("窗口返回黑屏或画面过小。请使用窗口模式，或先导入截图。")
    return frame
