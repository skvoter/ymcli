import requests
import json
import os
import sys
import tty
import termios
import contextlib
import time
from ctypes import CFUNCTYPE, c_char_p, c_int, cdll


TRACK_DOWNLOAD_INFO = (
    "https://storage.mds.yandex.net/download-info/{}/" + "2?format=json"
)
HANDLERS = {
    "TRACK": "https://music.yandex.ru/handlers/track.jsx?track={}",
    "ALBUM": "https://music.yandex.ru/handlers/album.jsx?album={}",
    "ARTIST": "https://music.yandex.ru/handlers/artist.jsx?artist={}",
}


class _Getch:
    def __init__(self):
        pass

    def __call__(self):
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch


getch = _Getch()


def load_json(handler, id):
    r = requests.get(handler.format(id))
    return json.loads(r.content)


@contextlib.contextmanager
def ignore_stdout():
    devnull = os.open(os.devnull, os.O_WRONLY)
    old_stdout = os.dup(2)
    sys.stderr.flush()
    os.dup2(devnull, 2)
    os.close(devnull)
    try:
        yield
    finally:
        os.dup2(old_stdout, 2)
        os.close(old_stdout)


ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)


def py_error_handler(filename, line, function, err, fmt):
    pass


c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)


@contextlib.contextmanager
def noalsaerr():
    asound = cdll.LoadLibrary("libasound.so.2")
    asound.snd_lib_error_set_handler(c_error_handler)
    yield
    asound.snd_lib_error_set_handler(None)


def quit(player):
    player.state = "stopped"
    print("\nExiting...")
    time.sleep(1)
    player.current_song = None
