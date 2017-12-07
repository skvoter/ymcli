import sys
import os
import threading
from utils import ignore_stdout, quit
from interfaces import Player, Song

def main():
    try:
        with ignore_stdout():
            player = Player()
        print('\nPlaylist:')
        for link in sys.argv[1:]:
            song = Song(link)
            player.playlist.append(song)
            print('{artist} - {title} ({album})'.format_map(song.trackinfo))
    except KeyboardInterrupt:
        pass
    else:
        player.play()
        if player.current_song!=None:
            quit(player)
    alive = True
    while alive is True:
        if len(threading.enumerate())==1:
            alive = False
    for path in os.listdir('/tmp/'):
        if path.startswith('ymnc'):
            os.remove('/tmp/'+path)
    os.system('stty sane')
    print('Goodbye!')
    sys.exit(0)

if __name__ == '__main__':
    main()
