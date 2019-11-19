import responder
from pprint import pprint
from starlette.websockets import WebSocket, WebSocketDisconnect
from typing import Dict
from logging import config, getLogger
from datetime import datetime as dt
from dataclasses import dataclass


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
        self.api = responder.API(debug=True)
        self.wsmember: Dict[str, WebSocket] = {}

        self.api.add_route('/post', self.append)
        self.api.add_route('/ws', self.websocketServer, websocket=True)

        self.api.run(port=80, address='0.0.0.0')

    async def websocketServer(self, ws: WebSocket):
        await ws.accept()
        key: str = ws.headers.get('sec-websocket-key')
        self.wsmember[key] = ws

        clientIP: str = ws.scope.get('client')[0]
        self.logger.debug(msg='connected from %s' % (clientIP,))

        while True:
            try:
                msg: str = await ws.receive_text()
            except (WebSocketDisconnect, IndexError, KeyError, OSError) as e:
                self.logger.info(msg=e)
                break
            else:
                self.logger.debug(msg='Got message from %s' % (clientIP,))
                for k, dst in self.wsmember.items():
                    if k != key:  # 自らのそれは送信しない
                        to: str = dst.scope.get('client')[0]
                        self.logger.debug(msg='Send to %s' % (to,))
                        await dst.send_text(msg)

        await ws.close()
        del self.wsmember[key]

    async def append(self, message: responder.Request, reply: responder.Response):
        postBody = await message.media()
        reply.content = b'OK'
        pprint(postBody)


class LogConfigure(object):

    def __init__(self, *, file: str = '', encoding: str = 'utf-8'):
        self._config = {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'simpleFormatter': {
                    'format': '[%(levelname)s] %(asctime)s %(module)s:%(lineno)s %(funcName)s : %(message)s',
                    'datefmt': '%H:%M:%S'
                },
                'plusFormatter': {
                    'format': '[%(levelname)s] %(asctime)s %(module)s:%(lineno)s %(funcName)s : %(message)s',
                    'datefmt': '%Y-%m-%d %H:%M:%S'
                }
            },
            'handlers': {
                'consoleHandler': {
                    'level': 'DEBUG',
                    'formatter': 'simpleFormatter',
                    'class': 'logging.StreamHandler',
                },
                'fileHandler': {
                    'level': 'INFO',
                    'formatter': 'plusFormatter',
                    'class': 'logging.handlers.RotatingFileHandler',
                    'filename': file,
                    'maxBytes': 1000000,
                    'backupCount': 7,
                    'encoding': encoding,
                }
            },
            'loggers': {
                'Log': {
                    'handlers': ['consoleHandler', 'fileHandler'],
                    'level': "DEBUG",
                }
            }
        }

        config.dictConfig(self._config)


if __name__ == '__main__':
    logconfig = LogConfigure(file='logs/server.log', encoding='cp932')

    server = Server()