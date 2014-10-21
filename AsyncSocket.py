import asyncore, socket, ssl, errno, select
import Logger
import Queue
import sys
import time
from IRCHandler import CmdGenerator

class AsyncSocket(asyncore.dispatcher):

    def __init__(self, bot, host, port, floodlimit):
        self.bot  = bot
        self.host = host
        self.port = port
        self.recvBuffer = ""
        self.sendBuffer = Queue.Queue()
        #self.cmdHandler = CmdHandler(self)
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.logger  = Logger.getLogger("%s-%s-%s"%(__name__, self.bot.nick, self.bot.host)+".AsynSocket", bot.lognormal, bot.logerrors)

        self.floodLimit    = floodlimit
        self.timeLastWrite = time.time()

        self.logger.info("%s:%s"%(host, port))

        self.use_ssl = bot.use_ssl
        if self.use_ssl:
            self.send = self._ssl_send
            self.recv = self._ssl_recv

        self.ssl = None

    def doConnect(self):
        self.connect((self.host, self.port))

    def handle_connect(self):
        """ Initializes SSL support after the connection has been made. """
        self.logger.info("Connecting Socket...")
        if self.use_ssl:
            self.ssl = ssl.wrap_socket(self.socket, do_handshake_on_connect=False)
            self.set_socket(self.ssl)
            # Non-blocking handshake
            while True:
                try:
                    self.ssl.do_handshake()
                    break
                except ssl.SSLError as err:
                    if err.args[0] == ssl.SSL_ERROR_WANT_READ:
                        select.select([self.ssl], [], [], 5.0)
                    elif err.args[0] == ssl.SSL_ERROR_WANT_WRITE:
                        select.select([], [self.ssl], [], 5.0)
                    else:
                        raise

    def handle_close(self):
        self.logger.info("Closing Socket")
        self.close()
        # if not self.bot.isTerminating:
        #     self.logger.info('Throwing sys.exit(408)')
        #     sys.exit(408)

    def handle_read(self):
        self.recvBuffer = self.recvBuffer + self.recv(8192)
        #We split on end of line, and if the last line is not ending up by "\r\n", we add it back.
        lines = self.recvBuffer.split("\n")
        lines = map(str.strip, lines)

        if lines[-1] != "":
            self.recvBuffer = lines[-1]
            lines.pop()
        else:
            self.recvBuffer = ""
            lines.pop()

        #We curate the line and pass it to the command interpreter.
        for line in lines:
            #self.logger.debug("Raw  >" + line)
            self.bot.cmdHandler.parseCmd(line)

    def handle_write(self):
        if not self.sendBuffer.empty() and (time.time() - self.timeLastWrite > self.floodLimit):
            msg = self.sendBuffer.get_nowait()
            if not ':identify' in msg:
                self.logger.debug("Send >" + msg.strip())
            self.send(msg)
            self.sendBuffer.task_done()
            self.timeLastWrite = time.time()
        else:
            time.sleep(0.001)

        if not self.bot.isIdentified:
            if self.bot.servpass != "":                
                self.sendBuffer.put_nowait(CmdGenerator.getPASS(self.bot.servpass))
            self.sendBuffer.put_nowait(CmdGenerator.getNICK(self.bot.nick, self.bot.nick))
            self.sendBuffer.put_nowait(CmdGenerator.getUSER(self.bot.nick))
            self.bot.isIdentified = True

        if self.bot.isTerminating:
            sys.exit(187)

    def _ssl_send(self, data):
        """ Replacement for self.send() during SSL connections. """
        try:
            result = self.write(data)
            return result
        except ssl.SSLError, why:
            if why[0] in (asyncore.EWOULDBLOCK, errno.ESRCH):
                return 0
            else:
                raise ssl.SSLError, why

    def _ssl_recv(self, buffer_size):
        """ Replacement for self.recv() during SSL connections. """
        try:
            data = self.read(buffer_size)
            if not data:
                self.handle_close()
                return ''
            return data
        except ssl.SSLError, why:
            if why[0] in (asyncore.ECONNRESET, asyncore.ENOTCONN,
                          asyncore.ESHUTDOWN):
                self.handle_close()
                return ''
            elif why[0] == errno.ENOENT:
                # Required in order to keep it non-blocking
                return ''
            else:
                raise