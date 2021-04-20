import socketio
import logging
import json

log = logging.getLogger(__name__)


class SocketIONamespace(socketio.ClientNamespace):
    """A custom namespace because this sucks.

    I literally could have just used self.sio.on() to register events in bot.py but now I'm too tired to use it like that so we have this jank shit instead.
    """

    def __init__(self, parent, namespace):
        """Initializes the custom namepace.

        Args:
            parent (bot instance): The calling instance's reference (needed later).
            namespace (str): SocketIO namespace. Whatever that means.
        """
        self.parent = parent
        super().__init__(namespace=namespace)

    def on_connect(self) -> None:
        """Connection event handler.
        """
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
        # Tell socketIO to send us data.
        self.emit("start", config)
        # Register message handler because decorators are borked, and further using function names is borked
        self.client.on("new message", self.handleMessage)

    def on_disconnect(self) -> None:
        """Disconnect handler
        """
        log.info("Disconnected")

    def handleMessage(self, data):
        """Message handler

        Args:
            data (str): The call data in a str
        """
        # See, here's why we needed to pass in our own reference and everything about this hurts me.
        jsonData = json.loads(data)
        self.parent.postTweet(jsonData)

        if self.parent.reportLatency:
            sum = sum(self.parent.latency).total_seconds()
            avg = round(sum / len(self.parent.latency), 3)
            log.info(f"Average latency for the last 100 calls: {avg} seconds")
