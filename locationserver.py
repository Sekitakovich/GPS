import responder
from pprint import pprint
from starlette.websockets import WebSocket, WebSocketDisconnect
from typing import Dict
from logging import getLogger
from datetime import datetime as dt
from dataclasses import dataclass
import time
import json
from threading import Thread
import websocket

from log import LogConfigure


class BroadCaster(Thread):

    def __init__(self):

        super().__init__()
        self.daemon = True
        self.logger = getLogger('Log')
        self.ready: bool = False

        def onMessage(ws, message):
            self.logger.debug(msg=message)
            pass

        def onError(ws, error):
            self.logger.debug(msg=error)
            pass

        def onClose(ws):
            self.ready = False
            pass

        def onOpen(ws):
            self.ready = True
            self.logger.debug(msg='start')

        url = 'ws://127.0.0.1/ws'
        self.ws = websocket.WebSocketApp(url,
                                    on_open=onOpen, on_error=onError, on_close=onClose, on_message=onMessage)

    def run(self) -> None:
        self.ws.run_forever()

    def send(self, *, message: str):
        if self.ready:
            self.ws.send(message)


@dataclass()
class IPTables(object):
    line: str
    node: str
    join: bool = False
    alert: int = 0
    last: dt = dt.now()


class Server(object):

    def __init__(self):
        self.logger = getLogger('Log')
        self.api = responder.API(debug=False)

        self.wsmember: Dict[str, WebSocket] = {}
        self.broadcaster = BroadCaster()
        self.broadcaster.start()

        self.api.add_route('/post', self.insert)
        self.api.add_route('/ws', self.websocketServer, websocket=True)

        self.api.run(port=80, address='0.0.0.0')

    async def websocketServer(self, ws: WebSocket):

        await ws.accept()
        key: str = ws.headers.get('sec-websocket-key')
        self.wsmember[key] = ws

        clientIP: str = ws.scope.get('client')[0]
        # self.logger.debug(msg='connected from %s' % (clientIP,))

        while True:
            try:
                msg: str = await ws.receive_text()
            except (WebSocketDisconnect, IndexError, KeyError, OSError) as e:
                self.logger.info(msg=e)
                break
            else:
                # self.logger.debug(msg='Got message from %s' % (clientIP,))
                for k, dst in self.wsmember.items():
                    if k != key:  # 自らのそれは送信しない
                        # to: str = dst.scope.get('client')[0]
                        # self.logger.debug(msg='Send to %s' % (to,))
                        await dst.send_text(msg)

        await ws.close()
        del self.wsmember[key]

    async def insert(self, message: responder.Request, reply: responder.Response):
        try:  # これ通用してない
            postBody = await message.media()
        except (TypeError,) as e:
            self.logger.error(msg=e)
        else:
            reply.content = b'OK'
            self.broadcaster.send(message=json.dumps(postBody))
            pprint(postBody)


if __name__ == '__main__':
    logconfig = LogConfigure(file='logs/server.log', encoding='cp932')

    server = Server()
