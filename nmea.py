from serial import Serial
from dataclasses import dataclass
from typing import List, Dict
from datetime import datetime as dt
from threading import Thread
from multiprocessing import Process, Queue
from functools import reduce
from operator import xor


class Receiver(Process):

    def __init__(self, *, port: str, baudrate: int, qp: Queue):

        super().__init__()
        self.daemon = True

        self.port: str = port
        self.baudrate: int = baudrate
        self.qp: Queue = qp

    def run(self) -> None:

        with Serial(self.port, baudrate=self.baudrate) as sp:
            while True:
                raw: bytes = sp.readline()
                self.qp.put(raw)


class Main(object):

    def calccsum(self, *, body: str) -> int:

        return reduce(xor, body.encode(), 0)

    def __init__(self):

        self.rq = Queue()
        self.receiver = Receiver(port='com4', baudrate=9600, qp=self.rq)
        self.receiver.start()

        counter: int = 0
        while True:

            raw: bytes = self.rq.get()

            if len(raw) > 2:
                text: str = raw[:-2].decode()  # cut off CR/+LF
                part: List[str] = text.split('*')
                if len(part) == 2:
                    body: str = part[0][1:]
                    csum: int = int(part[1], 16)
                    if self.calccsum(body=body) == csum:
                        item: List[str] = body.split(',')
                        suffix: str = item[0][-3:]
                        if suffix in ('RMC', 'GGA'):
                            print(body)


if __name__ == '__main__':

    main = Main()
