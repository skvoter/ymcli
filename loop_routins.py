import requests
import time
import shutil
from utils import noalsaerr


def start_stream(player):
    with noalsaerr():
        stream = player.stream.open(
            format=player.stream.get_format_from_width(2),
            channels=2,
            rate=44100,
            output=True
        )
        while player.state != 'stopped':
            if len(player.stream_chunks) == 0:
                time.sleep(0.1)
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


