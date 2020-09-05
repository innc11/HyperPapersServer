import threading


class PipeThread(threading.Thread):
    def __init__(self, sourcePipe, targetPipe, callback=None):
        super().__init__()
        self.setDaemon(True)
        self.setName("Pipe Thread")
        self.sourcePipe = sourcePipe
        self.targetPipe = targetPipe
        self.callback = callback

    def run(self):
        while True:
            try:
                data = self.sourcePipe.recv(1024)
                if not data:
                    break
                self.targetPipe.send(data)
            except Exception as e:
                break
