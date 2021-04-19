import socketio
import logging
import json

log = logging.getLogger(__name__)


class SocketIONamespace(socketio.ClientNamespace):
    def __init__(self, parent, namespace):
        self.parent = parent
        super().__init__(namespace=namespace)

    def connect(self):
        self._startCapture

    def _startCapture(self):
        CONFIG = {
            "filterCode": "44912,45040,45112,45072,45136",
            "filterType": "talkgroup",
            "filterName": "OpenMHZ",
            "filterStarred": False,
            "shortName": "kcers1b",
        }
        # DEBUG CONFIG TO GET A LOT OF API RESPONSES
        # CONFIG = {
        #     "filterCode": "",
        #     "filterType": "all",
        #     "filterName": "OpenMHZ",
        #     "filterStarred": False,
        #     "shortName": "kcers1b"
        # }
        self.emit("start", CONFIG)

    def disconnect(self):
        log.info("Disconnected")

    def on_new_message(self, data):
        json = json.loads(data)
        self.parent._postTweet(json)

        if self.parent.reportLatency:
            sum = sum(self.parent.latency).total_seconds()
            avg = round(sum / len(self.parent.latency), 3)
            log.info(f"Average latency for the last 100 calls: {avg} seconds")
