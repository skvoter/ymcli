from ctypes import CFUNCTYPE, c_char_p, c_int, cdll
import shutil
import contextlib
import io
import sys
import logging
import json
import requests
import time
import pyaudio as pa
import os
from hashlib import md5
from pydub import AudioSegment
from pydub.utils import make_chunks
from threading import Thread

logging.basicConfig(level=logging.INFO)

TRACK_DOWNLOAD_INFO = 'https://storage.mds.yandex.net/download-info/{}/2?format=json'
HANDLERS = {
    'TRACK': 'https://music.yandex.ru/handlers/track.jsx?track={}',
    'ALBUM': 'https://music.yandex.ru/handlers/album.jsx?album={}',
    'ARTIST': 'https://music.yandex.ru/handlers/artist.jsx?artist={}',
}


def load_json(handler, id):
    r = requests.get(handler.format(id))
    return json.loads(r.content)


class Song(object):

    def __init__(self, link, source='trackinfo'):
        self.source = source
        self.link = link
        self.meta = self.get_meta()
        self.is_downloaded = False
        self.current_size = 0
        self.current_duration = 0
        self.fullsize = self.meta['fullsize']
        self.duration = self.meta['duration']
        self.download_link = self.get_download_link()
        self.trackinfo = self.meta['trackinfo']
        self.filename = self.get_filename_hash()
        self.chunk_size = self.get_chunk_size()

    def get_chunk_size(self):
        if self.duration >= 120000:
            for i in range(4,10):
                if self.fullsize - int(self.fullsize/i)*(i-1) >= 5000 and self.fullsize<= int(self.fullsize/i)*i:
                    return int(self.fullsize/i)
        else:
            return self.fullsize


    def get_filename_hash(self):
        hsh = '/tmp/ymnc'+md5('{}_{}'.format(self.trackinfo['title'], self.trackinfo['artist']).encode()).hexdigest()
        open(hsh, 'a').close()
        if os.path.getsize(hsh) == self.fullsize:
            self.is_downloaded = True
        return hsh


    def get_meta(self):
        if self.source == 'trackinfo':
            trackid = self.link.split('/')[-1]
            info = load_json(HANDLERS['TRACK'], trackid)['track']
            results = {
                'fullsize': info['fileSize'],
                'duration': info['durationMs'],
                'trackinfo': {
                    'artist': info['artists'][0]['name'] if len(info['artists'])==1 else ', '.join([x['name'] for x in info['artists']]),
                    'album': info['albums'][0]['title'] if len(info['albums'])==1 else ', '.join([x['title'] for x in info['albums']]),
                    'title': info['title'],
                    'year': info['albums'][0]['year']
                },
                'storage_dir': info['storageDir']
            }
            return results

    def get_download_link(self):
        info = load_json(TRACK_DOWNLOAD_INFO, self.meta['storage_dir'])
        info['path'] = info['path'].lstrip('/')
        info['md5'] = md5('XGRlBW9FXlekgbPrRHuSiA{path}{s}'.format_map(info).encode()).hexdigest()
        return 'https://{host}/get-mp3/{md5}/{ts}/{path}'.format_map(info)


def start_stream(player):
    with noalsaerr():
        stream = player.stream.open(format=player.stream.get_format_from_width(2),
                                    channels=2,
                                    rate=44100,
                                    output=True)
        while player.state != 'stopped':
            if len(player.stream_chunks) == 0:
                time.sleep(1)
            elif player.stream_chunks[0] == 'next':
                if player.current_song == len(player.playlist)-1:
                    player.stream_chunks = []
                    player.stream_chunks.append('stop_player')
                else:
                    player.current_song += 1
                    del player.stream_chunks[0]
            elif player.stream_chunks[0] == 'stop_player':
                player.state = 'stopped'
                player.current_song = None
                del player.stream_chunks[0]
            elif player.stream_chunks[0] not in ('rewind', 'forward', 'reset_time'):
                stream.write(player.stream_chunks[0]._data)
                player.current_song_position += 1
                del player.stream_chunks[0]
                if player.current_song_position > (
                    player.playlist[player.current_song].duration/1000
                ):
                    player.stream_chunks = []
                    player.stream_chunks.append('reset_time')
                    player.stream_chunks.append('next')
            elif player.stream_chunks[0] == 'reset_time':
                del player.stream_chunks[0]
                player.current_song_position = 0
        stream.stop_stream()
        stream.close()

def print_line(player):
    print()
    while player.state != 'stopped':
        current_song = player.playlist[player.current_song]
        songinfo = current_song.trackinfo['artist']+' - '+ current_song.trackinfo['title']
        current_time = '{:0>2}:{:0>2}'.format(
            divmod(player.current_song_position, 60)[0],
            divmod(player.current_song_position, 60)[1])+'/'+ '{:0>2}:{:0>2}'.format(
                divmod(int(current_song.duration/1000), 60)[0],
                divmod(int(current_song.duration/1000), 60)[1])
        gaplen = shutil.get_terminal_size()[0]-len(current_time)-len(songinfo)-2
        if gaplen<=0:
            gap = ' '
            songinfo = songinfo[:(shutil.get_terminal_size()[0]-len(current_time)-1)]
        else:
            percentage_duration = int(
                player.current_song_position/int(current_song.duration/1000)*gaplen
            )
            percentage_size = int((current_song.current_size/current_song.fullsize)*gaplen)
            bar = (
                '\033[37m'+ \
                '━'*percentage_duration + \
                '\033[90m'+ \
                '━'*(percentage_size-percentage_duration) + \
                '\033[39m'
            )
            gap = ' '+ bar + ' '*(gaplen-len(bar)+15)+ ' '
        print('\r'+current_time+gap+songinfo, end='')
        time.sleep(0.3)


def download_tracks(player):
    while player.state != 'stopped' and player.current_song!=None:
        track = player.playlist[player.current_song]
        while player.current_song == player.playlist.index(track):
            binds = player.playlist[player.current_song:player.current_song+2]
            for track in binds:
                if track.is_downloaded == False:
                    with open(track.filename, 'wb') as f:
                        internet = False
                        while internet is False:
                            try:
                                r = requests.get(
                                    track.download_link,
                                    headers={'Range':'bytes={}-{}'.format(
                                        track.current_size, track.fullsize
                                    )}, stream=True)
                                internet = True
                            except:
                                time.sleep(2)
                        for chunk in r.iter_content(track.chunk_size):
                            f.write(chunk)
                            track.current_size += len(chunk)
                            if track.current_size == track.fullsize:
                                track.is_downloaded = True
                                track.current_size = track.fullsize
                else:
                    track.current_size = track.fullsize

class Player(object):

    def __init__(self):
        self.state = 'stopped'
        self.playlist = []
        self.stream = pa.PyAudio()
        self.current_song = 0
        self.current_song_position = 0
        self.stream_chunks = []

    def play(self, trackno=0):
        self.state='play'
        download_loop = Thread(target=download_tracks, args=(self,))
        print_loop = Thread(target=print_line, args=(self,))
        stream_loop = Thread(target=start_stream, args=(self,))
        download_loop.daemon = True
        print_loop.daemon = True
        print_loop.start()
        download_loop.start()
        stream_loop.start()
        while self.state != 'stopped':
            song = self.playlist[self.current_song]
            with open(song.filename, 'rb') as r:
                if song.is_downloaded == True:
                    self.stream_chunks.append('reset_time')
                    segment = AudioSegment.from_mp3(r)
                    self.stream_chunks += make_chunks(segment, 1000)
                    while self.current_song == self.playlist.index(song):
                        time.sleep(1)
                else:
                    flag = True
                    self.stream_chunks.append('reset_time')
                    while self.current_song == self.playlist.index(song):
                        chunk = r.read(song.chunk_size)
                        if len(chunk)==song.chunk_size:
                            chunk = io.BytesIO(chunk)
                            segment = AudioSegment.from_mp3(chunk)
                            self.stream_chunks += make_chunks(segment, 1000)
                        elif os.path.getsize(song.filename)==song.fullsize and flag is True:
                            if len(chunk)!=0:
                                chunk = io.BytesIO(chunk)
                                segment = AudioSegment.from_mp3(chunk)
                                self.stream_chunks += make_chunks(segment, 1000)
                            self.stream_chunks.append('reset_time')
                            flag = False
                        elif flag is True:
                            r.seek(-(len(chunk)), 1)
                            time.sleep(1)


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
    asound = cdll.LoadLibrary('libasound.so')
    asound.snd_lib_error_set_handler(c_error_handler)
    yield
    asound.snd_lib_error_set_handler(None)

def main():
    with ignore_stdout():
        player = Player()
    try:
        for link in sys.argv[1:]:
            song = Song(link)
            player.playlist.append(song)
        player.play()
    except KeyboardInterrupt:
        player.state = 'stopped'
        for path in os.listdir('/tmp/'):
            if path.startswith('ymnc'):
                os.remove('/tmp/'+path)
        print('\nGoodbye!')
        sys.exit(0)

if __name__ == '__main__':
    main()
