import threading
import time


class Interval:
    """A class that loops every interval.
    """

    def __init__(self, interval, action) -> None:
        """Initialize the interval loop.

        Args:
            interval (float): The interval in seconds.
            action (function): The action to do.
        """
        self.interval = interval
        self.action = action

        self.stop = threading.Event()

        thread = threading.Thread(target=self._setInterval)
        thread.start()

    def _setInterval(self) -> None:
        """Does things.
        """
        next = time.time()
        while not self.stop.wait(next - time.time()):
            next += self.interval
            try:
                self.action()
            except OSError as e:
                print(e)
                pass

    def cancel(self) -> None:
        """Cancels the interval.
        """
        self.stop.set()
