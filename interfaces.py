import io, os, time
import pyaudio as pa
from hashlib import md5
from pydub import AudioSegment
from pydub.utils import make_chunks
from threading import Thread
from urllib.parse import urlparse
from utils import TRACK_DOWNLOAD_INFO, HANDLERS, load_json
from loop_routins import download_tracks, start_stream, print_line, handle_controls


def parse_url(link):
    path = urlparse(link).path
    locs = path.lstrip('/').split('/')
    if locs[-2] == 'track':
        trackid = link.split('/')[-1]
        info = load_json(HANDLERS['TRACK'], trackid)['track']
        song = Song(info)
        return [song]
    elif locs[-2] == 'album':
        albumid = link.split('/')[-1]
        info = load_json(HANDLERS['ALBUM'], albumid)
        songs = []
        for volume in info['volumes']:
            for song in volume:
                songinfo = info.copy()
                songinfo['trackinfo'] = song.copy()
                del songinfo['volumes']
                song = Song(songinfo, source='albuminfo')
                songs.append(song)
        return songs


class Song(object):

    def __init__(self, info, source='trackinfo'):
        self.source = source
        self.meta = self.get_meta(info)
        self.is_downloaded = False
        self.current_size = 0
        self.current_duration = 0
        self.segment = None
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


    def get_meta(self, info):
        if self.source == 'trackinfo':
            results = {
                'fullsize': info['fileSize'],
                'duration': info['durationMs'],
                'trackinfo': {
                    'artist': info['artists'][0]['name'] \
                    if len(info['artists'])==1 \
                    else ', '.join([x['name'] for x in info['artists']]),
                    'album': info['albums'][0]['title'] \
                    if len(info['albums'])==1 \
                    else ', '.join([x['title'] for x in info['albums']]),
                    'title': info['title'],
                    'year': info['albums'][0]['year']
                },
                'storage_dir': info['storageDir']
            }
            print('{artist} - {title} | {album}'.format_map(results['trackinfo']))
            return results
        elif self.source == 'albuminfo':
            results = {
                'fullsize': info['trackinfo']['fileSize'],
                'duration': info['trackinfo']['durationMs'],
                'trackinfo': {
                    'artist': info['artists'][0]['name'] \
                    if len(info['artists'])==1 \
                    else ', '.join([x['name'] for x in info['artists']]),
                    'album': info['title'],
                    'title': info['trackinfo']['title'],
                    'year': info['year']
                },
                'storage_dir': info['trackinfo']['storageDir']
            }
            print('{artist} - {title} | {album}'.format_map(results['trackinfo']))
            return results


    def get_download_link(self):
        info = load_json(TRACK_DOWNLOAD_INFO, self.meta['storage_dir'])
        info['path'] = info['path'].lstrip('/')
        info['md5'] = md5('XGRlBW9FXlekgbPrRHuSiA{path}{s}'.format_map(info).encode()).hexdigest()
        return 'https://{host}/get-mp3/{md5}/{ts}/{path}'.format_map(info)


class Player(object):

    def __init__(self):
        self.state = 'stopped'
        self.playlist = []
        self.stream = pa.PyAudio()
        self.current_song = 0
        self.current_song_position = 0
        self.play_signals = []
        self.stream_chunks = []
        self.stopped = False

    def play(self, trackno=0):
        self.state='play'
        download_loop = Thread(target=download_tracks, args=(self,))
        print_loop = Thread(target=print_line, args=(self,))
        handle_loop = Thread(target=handle_controls, args=(self,))
        stream_loop = Thread(target=start_stream, args=(self,))
        download_loop.daemon = True
        print_loop.daemon = True
        handle_loop.daemon = True
        print_loop.start()
        download_loop.start()
        stream_loop.start()
        handle_loop.start()
        while self.state != 'stopped' and self.current_song!=None:
            song = self.playlist[self.current_song]
            self.stream_chunks.append('reset_time')
            with open(song.filename, 'rb') as r:
                if song.is_downloaded == True:
                    song.segment = AudioSegment.from_mp3(r)
                    self.stream_chunks += make_chunks(song.segment, 1000)
                    while self.current_song == self.playlist.index(song):
                        time.sleep(0.1)
                else:
                    while song.segment == None:
                        time.sleep(0.1)
                    seglen = len(song.segment)
                    oldlen =0
                    self.stream_chunks += make_chunks(song.segment[oldlen:seglen], 1000)
                    while self.current_song == self.playlist.index(song):
                        oldlen = seglen
                        seglen = len(song.segment)
                        while seglen>oldlen and self.current_song == self.playlist.index(song):
                            self.stream_chunks += make_chunks(song.segment[oldlen:seglen], 1000)
                            time.sleep(1)


