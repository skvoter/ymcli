import sys
import os
import threading
from ymcli.utils import ignore_stdout, quit
from ymcli.interfaces import Player, parse_url


def main():
    try:
        with ignore_stdout():
            player = Player()
        print("\nPlaylist:")
        assert len(sys.argv[1:]) > 0
        for link in sys.argv[1:]:
            songs = parse_url(link)
            player.playlist += songs
    except KeyboardInterrupt:
        pass
    else:
        player.play()
        if player.current_song is not None:
            quit(player)
    alive = True
    while alive is True:
        if len(threading.enumerate()) == 1:
            alive = False
    for path in os.listdir("/tmp/"):
        if path.startswith("ymnc"):
            os.remove("/tmp/" + path)
    os.system("stty sane")
    print("Goodbye!")
    sys.exit(0)


if __name__ == "__main__":
    main()
