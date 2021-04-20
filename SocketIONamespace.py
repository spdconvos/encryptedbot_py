import socketio
import logging
import json

log = logging.getLogger(__name__)


class SocketIONamespace(socketio.ClientNamespace):
    def __init__(self, parent, namespace):
        self.parent = parent
        super().__init__(namespace=namespace)

    def on_connect(self):
        config = {
            "filterCode": [44912, 45040, 45112, 45072, 45136],
            "filterType": "talkgroup",
            "filterName": "OpenMHZ",
            "filterStarred": False,
            "shortName": "kcers1b",
        }
        """ # DEBUG CONFIG TO GET A LOT OF API RESPONSES
        config = {
            "filterCode": "5ed813629818fe0025c8e245",
            "filterType": "group",
            "filterName": "OpenMHZ",
            "filterStarred": False,
            "shortName": "kcers1b",
        } """
        self.emit("start", config)
        self.client.on("new message", self.handleMessage)

    def on_disconnect(self):
        log.info("Disconnected")

    def handleMessage(self, data):
        jsonData = json.loads(data)
        self.parent.postTweet(jsonData)

        if self.parent.reportLatency:
            sum = sum(self.parent.latency).total_seconds()
            avg = round(sum / len(self.parent.latency), 3)
            log.info(f"Average latency for the last 100 calls: {avg} seconds")
