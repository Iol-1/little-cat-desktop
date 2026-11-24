"""Keep Windows audio device work off the Qt message thread."""
from pathlib import Path
import threading
import winsound


class PurrPlayer:
    """Serialize native sound calls while retaining only the latest intent.

    ``set_playing`` and ``close`` never wait for the device. A failed command
    stays failed until the desired state changes, so a 60 Hz caller cannot
    repeatedly retry a broken sound device. The daemon worker owns all native
    audio operations and never calls Qt.
    """

    def __init__(self, path, play_sound=None):
        self.path = str(Path(path))
        self._play_sound = play_sound or winsound.PlaySound
        self._condition = threading.Condition()
        self._thread = None
        self._desired = False
        self._revision = 0
        self._handled_revision = 0
        self._actual = False
        self._needs_stop = False
        self._closed = False
        self._status = 'idle'
        self._error = ''

    @property
    def status(self):
        with self._condition:
            return self._status

    @property
    def error(self):
        with self._condition:
            return self._error

    @property
    def playing(self):
        with self._condition:
            return self._actual

    def set_playing(self, playing):
        wanted = bool(playing)
        with self._condition:
            if self._closed or wanted == self._desired:
                return
            self._desired = wanted
            self._revision += 1
            self._error = ''
            if self._thread is None:
                # A stopped, unused player has nothing to initialize or stop.
                if not wanted:
                    self._handled_revision = self._revision
                    return
                self._thread = threading.Thread(target=self._run, name='CatSound', daemon=True)
                self._thread.start()
            self._condition.notify()

    def close(self):
        with self._condition:
            if self._closed:
                return
            self._closed = True
            self._desired = False
            self._revision += 1
            if self._thread is None:
                self._status = 'closed'
            self._condition.notify()

    def _run(self):
        while True:
            with self._condition:
                self._condition.wait_for(lambda: self._closed or self._revision != self._handled_revision)
                wanted, revision = self._desired, self._revision
                if self._closed:
                    wanted = False
                    if not self._needs_stop:
                        self._status = 'closed'
                        return
                if (wanted and self._actual) or (not wanted and not self._needs_stop):
                    self._handled_revision = revision
                    if not self._error:
                        self._status = 'playing' if self._actual else 'idle'
                    continue
                self._status = 'starting' if wanted else 'stopping'
                if wanted:
                    # Even a failed device initialization may need a cleanup.
                    self._needs_stop = True

            error = ''
            try:
                if wanted:
                    flags = winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP | winsound.SND_NODEFAULT
                    self._play_sound(self.path, flags)
                else:
                    self._play_sound(None, 0)
            except Exception as exception:
                error = f'{type(exception).__name__}: {exception}'

            with self._condition:
                self._handled_revision = revision
                self._error = error
                if not error:
                    self._actual = wanted
                    self._needs_stop = wanted
                self._status = 'error' if error else ('playing' if wanted else 'idle')
                # Closing never retries a failed stop forever, and never joins
                # a native driver call from the GUI thread.
                if self._closed and not wanted:
                    self._status = 'closed'
                    return
