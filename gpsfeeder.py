from serial import Serial, SerialException, SerialTimeoutException
from typing import List, Dict
from threading import Thread, Lock
from queue import Queue
from functools import reduce
from operator import xor
import time
import json
from dataclasses import dataclass, asdict
import requests
from datetime import datetime as dt
from datetime import timedelta
from logging import getLogger

from log import LogConfigure


@dataclass()
class Plus(object):
    alt: float = 0.0
    sats: int = 0
    kmh: float = 0.0


@dataclass()
class Basic(object):
    lat: float = 0.0
    lng: float = 0.0
    sog: float = 0.0
    cog: float = 0.0
    ns: str = ''
    ew: str = ''
    utc: str = ''
    mode: str = ''  # N<A<D<E


@dataclass()
class DOP(object):
    p: float = 0.0
    h: float = 0.0
    v: float = 0.0


@dataclass()
class Location(object):
    base: Basic = Basic()
    plus: Plus = Plus()
    dop: DOP = DOP()


class Driver(Thread):

    def __init__(self, *, sp: Serial, qp: Queue):

        super().__init__()
        self.daemon = True
        self.logger = getLogger('Log')

        self.location = Location()

        self.sp = sp
        self.qp = qp

        self.GPSdatetimeFormat: str = '%d-%d-%d %d:%d:%d'
        self.SYSdatetimeformat: str = '%Y-%m-%d %H:%M:%S'

        self.at: str = dt.now().strftime(self.SYSdatetimeformat)  # notice!
        self.counter: int = 0

    def run(self) -> None:
        while True:
            nmea: str = self.qp.get()
            sentence = self.checkNMEA(nmea=nmea)
            if len(sentence):
                self.loadSentence(item=sentence)
            else:
                self.logger.critical(msg='invalid sentence')

    def loadSentence(self, *, item: List[str]):

        def atRMC():

            if item[2] == 'A':
                ymd = item[9]
                hms = item[1]
                utcSring: str = self.GPSdatetimeFormat % (
                    int(ymd[4:6]) + 2000, int(ymd[2:4]), int(ymd[0:2]), int(hms[0:2]), int(hms[2:4]), int(hms[4:6])
                )
                jst = (dt.strptime(utcSring, self.SYSdatetimeformat) + timedelta(hours=9)).strftime(
                    self.SYSdatetimeformat)
                self.location.base.utc = utcSring

                self.location.base.lat = float(item[3]) if item[3] else 0.0
                self.location.base.ns = item[4]
                self.location.base.lng = float(item[5]) if item[5] else 0.0
                self.location.base.ew = item[6]
                self.location.base.sog = float(item[7]) if item[7] else 0.0
                self.location.base.cog = float(item[8]) if item[8] else 0.0
                self.location.base.mode = item[12]

                self.at = jst
                self.counter += 1

        def atGGA():

            if item[6] != '0':
                self.location.plus.sats = int(item[7]) if item[7] else 0
                self.location.plus.alt = float(item[9]) if item[9] else 0.0

        def atVTG():

            if item[9] != 'N':
                self.location.plus.kmh = float(item[7]) if item[7] else 0.0

        def atGSA():

            if item[2] != '1':
                self.location.dop.p = float(item[4]) if item[4] else 0.0
                self.location.dop.h = float(item[5]) if item[5] else 0.0
                self.location.dop.v = float(item[6]) if item[6] else 0.0

        window: Dict[str, any] = {
            'RMC': atRMC,
            'GGA': atGGA,
            'VTG': atVTG,
            'GSA': atGSA,
        }

        try:
            suffix = item[0][2:]
            if suffix in window.keys():
                window[suffix]()
        except (IndexError, ValueError) as e:
            self.logger.error(msg=e)
        else:
            pass

    def checkNMEA(self, *, nmea: str) -> list:

        result = []

        part: list = nmea.split('*')
        if len(part) == 2:
            try:
                body: str = part[0][1:]
                your: int = int(part[1], 16)
                mine: int = reduce(xor, body.encode(), 0)
            except (IndexError, ValueError) as e:
                self.logger.error(msg=e)
            else:
                if your == mine:
                    return body.split(',')

        return result


class Receiver(Thread):

    def __init__(self, *, sp: Serial, qp: Queue):

        super().__init__()
        self.daemon = True
        self.logger = getLogger('Log')

        self.sp = sp
        self.qp = qp

    def run(self) -> None:

        while True:
            try:
                raw: bytes = self.sp.readline()
            except (SerialException, SerialTimeoutException) as e:
                self.logger.error(msg=e)
            else:
                if len(raw) >= 2:
                    text: str = raw[:-2].decode()
                    self.qp.put(text)


class Sender(Thread):

    def __init__(self, *, url: str, sq: Queue):

        super().__init__()
        self.daemon = True
        self.logger = getLogger('Log')

        self.sq = sq
        self.locker = Lock()
        self.url = url
        self.headers: Dict[str, str] = {
            'Content-Type': 'application/json',
        }
        self.online: bool = True

        self.stack: List[str] = []
        self.retryInterval: int = 5
        self.retryThread = Thread(target=self.retryCycle, daemon=True)
        self.retryThread.start()

    def send(self, *, content: str) -> bool:

        success: bool = True
        try:
            response = requests.post(self.url, content, headers=self.headers, timeout=2.5)
        except (
                requests.exceptions.Timeout, requests.exceptions.ConnectionError,
                requests.exceptions.HTTPError) as e:
            success = False
            self.online = False
            self.logger.error(msg=e)
        else:
            self.online = True
            if response.status_code == 200:
                # self.logger.debug(msg='send success')
                pass
            else:
                self.logger.error(msg=response.status_code)

        return success

    def retryCycle(self):

        while True:
            time.sleep(self.retryInterval)
            if self.online:
                with self.locker:
                    while True:
                        remain: int = len(self.stack)
                        if remain:
                            self.logger.debug('Remain %d' % remain)
                            content = self.stack[0]
                            if self.send(content=content):
                                del (self.stack[0])
                                self.logger.debug('send OK')
                            else:
                                break
                        else:
                            break

    def run(self) -> None:

        while True:

            src = self.sq.get()
            content: str = json.dumps(src, indent=2)

            if self.send(content=content):
                pass
            else:
                with self.locker:
                    self.stack.append(content)


class Main(object):

    def __init__(self, *, port: str, baudrate: int, account: str, url: str):

        self.logger = getLogger('Log')

        self.logger.info(msg='Start')

        self.account = account
        self.runnninng: bool = True
        self.loopCounter: int = 0
        self.sends: int = 0
        self.report: Dict[str, any] = {
            'counter': 0,
            'at': '',
            'status': True,
            'account': account,
            'location': '',
        }
        self.qp = Queue()
        self.sq = Queue()

        self.sleepTable: List[dict] = [
            {'max': 5, 'val': 60 * 1},
            {'max': 10, 'val': 30 * 1},
            {'max': 20, 'val': 4},
            {'max': 40, 'val': 3},
            {'max': 80, 'val': 2},
        ]

        try:
            sp = Serial(port=port, baudrate=baudrate)
        except (SerialException,) as e:
            self.runnninng = False
            self.logger.error(msg=e)
        else:

            self.receiver = Receiver(sp=sp, qp=self.qp)
            self.driver = Driver(sp=sp, qp=self.qp)
            self.sender = Sender(url=url, sq=self.sq)

            self.intervalSecs: int = 1

    def sendThis(self, *, status: bool = True):

        self.report['status'] = status
        self.report['counter'] = self.sends
        self.report['location'] = asdict(self.driver.location)
        self.report['at'] = self.driver.at
        self.sq.put(self.report)
        self.sends += 1

    def calcTiming(self, *, kmh: int) -> int:

        value: int = 1  # default

        for s in self.sleepTable:
            if kmh < s['max']:
                value = s['val']
                break

        return value

    def mainLoop(self):

        lastCounter: int = 0
        timing: int = 1
        lastTiming: int = 1
        isGPS: bool = False

        self.receiver.start()
        self.driver.start()
        self.sender.start()

        # time.sleep(self.intervalSecs)

        while True:

            measuredCunter = self.driver.counter
            if measuredCunter != lastCounter:  # changed
                isGPS = True
                if (self.loopCounter % timing) == 0:
                    self.sendThis()
                timing = self.calcTiming(kmh=int(self.driver.location.plus.kmh))
                if timing != lastTiming:
                    self.logger.debug('timing was changed %d -> %d' % (lastTiming, timing))
                    lastTiming = timing
                lastCounter = measuredCunter
            else:
                if isGPS:
                    isGPS = False
                    timing = 1
                    lastTiming = 1
                    # self.sendThis(status=False)
                    self.logger.critical(msg='GPS lost')
                else:
                    self.logger.debug(msg='Checking (%d)' % (self.loopCounter,))
                    pass

            time.sleep(self.intervalSecs)
            self.loopCounter += 1


if __name__ == '__main__':

    account: str = 'sekitakovich'
    url: str = 'http://127.0.0.1/post'

    logconfig = LogConfigure(file='logs/client.log', encoding='cp932')

    main = Main(port='com5', baudrate=9600, account=account, url=url)
    if main.runnninng:
        main.mainLoop()
