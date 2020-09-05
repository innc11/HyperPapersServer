import socket
import threading

from forwarder.PipeThread import PipeThread


class ProtocolDetector(threading.Thread):
    def __init__(self, fwd, clientConn, clientAddress):
        super().__init__()
        self.setDaemon(True)
        self.setName("Protocol Detector")
        self.fwd = fwd
        self.clientConn = clientConn
        self.clientAddress = clientAddress

    def run(self):
        clientConn = self.clientConn

        with clientConn:
            self.fwd.logger.info(f"[ProtocolDetector]: New connection from {self.clientAddress[0]}")

            if self.fwd.count >= 100:
                self.fwd.logger.warn(f'[ProtocolDetector]: The number of pipe thread is too many and up to {str(self.fwd.count)}!')

            buffer = ""
            forwardingPort = -1

            while True:
                try:
                    data = clientConn.recv(1024).decode()

                    if not data:
                        return

                    buffer += data

                    if "Upgrade: websocket" in buffer:
                        # print("is websocket")
                        forwardingPort = self.fwd.webSocketPort
                        break

                    if "\r\n\r\n" in buffer:
                        # print("is not websocket")
                        forwardingPort = self.fwd.httpServerPort
                        break

                except Exception as e:
                    self.fwd.logger.info(e, exc_info=True)
                    return
            # print('connect to '+self.fwd.serverHost+': '+str(forwardingPort))
            serverConn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            serverConn.connect((self.fwd.hostAddress, forwardingPort))
            serverConn.send(buffer.encode())

            self.fwd.count += 1

            c2s = PipeThread(clientConn, serverConn)  # client to server
            s2c = PipeThread(serverConn, clientConn)  # server to client

            c2s.start()
            s2c.start()

            c2s.join()
            s2c.join()

            self.fwd.count -= 1

            # self.fwd.logger.info("[ProtocolDetector]: Pipe thread ended")
