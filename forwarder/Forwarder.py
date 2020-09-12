import socket
import threading
from logging import Logger

from forwarder.ProtocolDetector import ProtocolDetector


class Forwarder(threading.Thread):
    def __init__(self, listenPort: int, targetHost: str, webSocketPort: int, httpServerPort: int, sslContext,
                 logger: Logger):
        super().__init__()
        self.setDaemon(True)
        self.setName("Port Forwarder")
        self.hostAddress = targetHost
        self.listenPort = listenPort
        self.sock = None

        self.webSocketPort = webSocketPort
        self.httpServerPort = httpServerPort
        self.logger = logger
        self.sslContext = sslContext

        self.count = 0

    def openSock(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM) if self.sslContext is not None else socket.socket(
            socket.AF_INET, socket.SOCK_STREAM, proto=0)
        self.sock.bind((self.hostAddress, self.listenPort))
        self.sock.listen(100)
        url = ('https' if self.sslContext is not None else 'http') + '://' + self.hostAddress + ':' + str(self.listenPort)
        self.logger.info(f"Forwarder is listening on {self.listenPort}, {url}")

    def run(self):
        if self.sslContext is not None:
            while True:
                self.openSock()
                try:
                    with self.sslContext.wrap_socket(self.sock, server_side=True) as ssock:
                        while True:
                            clientConn, clientAddress = ssock.accept()

                            ProtocolDetector(self, clientConn, clientAddress).start()
                except BaseException as e:
                    self.logger.error(e, exc_info=False)
                finally:
                    self.sock.close()
                    self.sock = None
        else:
            while True:
                self.openSock()
                while True:
                    try:
                        clientConn, clientAddress = self.sock.accept()
                        ProtocolDetector(self, clientConn, clientAddress).start()
                    except BaseException as e:
                        self.logger.error(e, exc_info=False)
                    finally:
                        self.sock.close()
                        self.sock = None
