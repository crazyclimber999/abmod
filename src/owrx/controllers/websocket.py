from . import Controller
from owrx.websocket import WebSocketConnection
from owrx.connection import HandshakeMessageHandler
from owrx.controllers.admin import Authentication


class WebSocketController(Controller):
    def indexAction(self):
        # the user must be read here: cookies are only available on the HTTP
        # request that opens the websocket, not on the messages that follow
        user = Authentication().getUser(self.request)
        conn = WebSocketConnection(self.handler, HandshakeMessageHandler(user))
        # enter read loop
        conn.handle()
