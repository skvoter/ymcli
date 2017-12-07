import sys
import os
from utils import ignore_stdout
from interfaces import Player, Song

def quit(player):
    player.state = 'stopped'
    for path in os.listdir('/tmp/'):
        if path.startswith('ymnc'):
            os.remove('/tmp/'+path)
    print('\nGoodbye!')
    sys.exit(0)


def main():
    with ignore_stdout():
        player = Player()
    try:
        print('\nPlaylist:')
        for link in sys.argv[1:]:
            song = Song(link)
            player.playlist.append(song)
            print('{artist} - {title} ({album})'.format_map(song.trackinfo))
        player.play()
    except KeyboardInterrupt:
        quit(player)
if __name__ == '__main__':
    main()
