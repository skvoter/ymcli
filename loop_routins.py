import io
import requests
import time
import shutil
from utils import noalsaerr, getch, quit
from pydub import AudioSegment
from pydub.utils import make_chunks


def handle_controls(player):
    while player.state != 'stopped':
        a = getch()
        if ord(a) == 3 or a == 'q':
            quit(player)
        elif a == 'f':
            if len(player.stream_chunks) != 0:
                player.stream_chunks.insert(0, 'forward')
        elif a == 'b':
            if len(player.stream_chunks) != 0:
                player.stream_chunks = [player.stream_chunks[0]] + ['backward']
        elif a == '>':
            if player.current_song == len(player.playlist)-1:
                pass
            else:
                player.stream_chunks = []
                player.stream_chunks.append('reset_time')
                player.stream_chunks.append('next')
        elif a == '<':
            if player.current_song == 0:
                pass
            else:
                player.stream_chunks = []
                player.stream_chunks.append('reset_time')
                player.stream_chunks.append('previous')


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
            elif player.stream_chunks[0] == 'previous':
                if player.current_song != 0:
                    player.stream_chunks = []
                    player.current_song -= 1
            elif player.stream_chunks[0] == 'next':
                if player.current_song == len(player.playlist)-1:
                    player.stream_chunks = []
                    player.stream_chunks.append('stop_player')
                else:
                    player.stream_chunks = []
                    player.current_song += 1
            elif player.stream_chunks[0] == 'stop_player':
                player.state = 'stopped'
                player.current_song_position = 0
                del player.stream_chunks[0]
            elif player.stream_chunks[0] == 'backward':
                if player.current_song_position - 5 >= 0:
                    seg = player.playlist[player.current_song].segment[
                        (player.current_song_position-5)*1000:]
                    player.current_song_position -= 5
                else:
                    seg = player.playlist[player.current_song].segment
                    player.current_song_position = 0
                player.stream_chunks += make_chunks(seg, 1000)
                del player.stream_chunks[0]
            elif player.stream_chunks[0] == 'forward':
                if player.current_song_position + 5 > player.playlist[
                    player.current_song
                ].duration:
                    player.stream_chunks = []
                    player.stream_chunks.append('reset_time')
                    player.stream_chunks.append('next')
                elif player.current_song_position + 5 < len(
                    player.playlist[player.current_song].segment
                )/1000:
                    player.stream_chunks = []
                    seg = player.playlist[player.current_song].segment[
                        (player.current_song_position+5)*1000:]
                    player.current_song_position += 5
                    player.stream_chunks += make_chunks(seg, 1000)
                else:
                    del player.stream_chunks[0]
            elif player.stream_chunks[0] not in (
                'backward', 'forward', 'reset_time'
            ):
                stream.write(player.stream_chunks[0]._data)
                player.current_song_position += 1
                if player.stream_chunks[0] not in (
                    'next', 'forward', 'backward'
                ):
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
        songinfo = (current_song.trackinfo['artist']
                    + ' - ' + current_song.trackinfo['title'])
        current_time = ('{:0>2}:{:0>2}'.format(
            divmod(player.current_song_position, 60)[0],
            divmod((player.current_song_position, 60)[1]))
                        + '/'
                        + '{:0>2}:{:0>2}'.format(
                            divmod(int(current_song.duration/1000), 60)[0],
                            divmod(int(current_song.duration/1000), 60)[1]))
        gaplen = (shutil.get_terminal_size()[0]
                  - len(current_time)
                  - len(songinfo) - 2)
        if gaplen <= 0:
            gap = ' '
            songinfo = songinfo[:(shutil.get_terminal_size()[0]
                                  - len(current_time)-1)]
        else:
            percentage_duration = int(
                player.current_song_position/int(
                    current_song.duration/1000
                ) * gaplen)
            percentage_size = int(
                (current_song.current_size/current_song.fullsize) * gaplen)
            bar = ('\033[37m'
                   + '━'*percentage_duration
                   + '\033[90m'
                   + '━'*(percentage_size-percentage_duration)
                   + '\033[39m')
            gap = ' ' + bar + ' '*(gaplen-len(bar)+15) + ' '
        print('\r'+current_time+gap+songinfo, end='')
        time.sleep(0.3)


def download_tracks(player):
    while player.state != 'stopped' and player.current_song is not None:
        track = player.playlist[player.current_song]
        while player.current_song == player.playlist.index(track):
            if player.current_song == len(player.playlist)-1:
                binds = [track]
            elif player.current_song is not None:
                binds = player.playlist[
                    player.current_song:player.current_song+2
                ]
            else:
                break
            for track in binds:
                if track.is_downloaded is False:
                    with open(track.filename, 'wb') as f:
                        internet = False
                        while internet is False:
                            try:
                                r = requests.get(
                                    track.download_link,
                                    headers={'Range': 'bytes={}-{}'.format(
                                        track.current_size, track.fullsize
                                    )}, stream=True)
                                internet = True
                            except Exception:
                                time.sleep(2)
                        for chunk in r.iter_content(track.chunk_size):
                            f.write(chunk)
                            track.current_size += len(chunk)
                            rchunk = io.BytesIO(chunk)
                            segment = AudioSegment.from_mp3(rchunk)
                            if track.segment is not None:
                                track.segment = track.segment.append(
                                    segment, crossfade=0)
                            else:
                                track.segment = segment
                            if track.current_size == track.fullsize:
                                track.is_downloaded = True
                                track.current_size = track.fullsize
                else:
                    track.current_size = track.fullsize
