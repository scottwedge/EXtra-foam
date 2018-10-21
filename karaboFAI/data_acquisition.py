"""
Offline and online data analysis and visualization tool for azimuthal
integration of different data acquired with various detectors at
European XFEL.

Data acquisition.

Author: Jun Zhu <jun.zhu@xfel.eu>
Copyright (C) European X-Ray Free-Electron Laser Facility GmbH.
All rights reserved.
"""
import time
import queue

from karabo_bridge import Client
import zmq

from .widgets.pyqtgraph import QtCore
from .logger import logger
from .config import config


class TimeoutClient(Client):
    """To test next with timeout option.

    TODO: move into karabo_bridge
    """
    def __init__(self, *args, timeout=None, **kwargs):
        super().__init__(*args, **kwargs)
        # timeout setting
        if timeout is not None:
            self._socket.RCVTIMEO = 1000 * timeout

    def next(self):
        """Override."""
        if self._pattern == zmq.REQ:
            self._socket.send(b'next')
        return self.recv()

    def recv(self):
        """Override."""
        msg = self._socket.recv_multipart(copy=False)
        return self._deserialize(msg)


class DaqWorker(QtCore.QThread):

    # post message in the main GUI
    messager = QtCore.pyqtSignal(str)

    def __init__(self, parent, out_queue):
        """Initialization."""
        super().__init__(parent=parent)

        self.messager.connect(parent.onMessageReceived)

        self.server_tcp_sp = None

        self.parent().server_tcp_sp.connect(self.onServerTcpChanged)

        self._out_queue = out_queue
        self._running = True

    @QtCore.pyqtSlot(str, str)
    def onServerTcpChanged(self, address, port):
        self.server_tcp_sp = "tcp://" + address + ":" + port

    def run(self):
        """Override."""
        self._running = True
        with TimeoutClient(self.server_tcp_sp, timeout=1) as client:
            self.messager.emit("Bind to server {}".format(self.server_tcp_sp))
            while self._running:
                t0 = time.perf_counter()

                try:
                    data = client.next()
                except zmq.error.Again:
                    while self._running:
                        try:
                            data = client.recv()
                            break
                        except zmq.error.Again:
                            continue
                    else:
                        break

                logger.debug(
                    "Time for retrieving data from the server: {:.1f} ms"
                    .format(1000 * (time.perf_counter() - t0)))

                while self._running:
                    try:
                        self._out_queue.put(data, timeout=config['TIMEOUT'])
                        break
                    except queue.Full:
                        continue

    def terminate(self):
        self._running = False
