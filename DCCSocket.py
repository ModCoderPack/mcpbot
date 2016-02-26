import asyncore, socket, ssl, errno, select
import Logger
import time
import Queue
from IRCHandler import Sender
from contextlib import closing

EOL = "\r\n"
CTCPTAG = chr(1)

class DCCHandler(asyncore.dispatcher):

    def __init__(self, bot, sock, sender):
        asyncore.dispatcher.__init__(self, sock)
        self.bot = bot
        self.sender = sender
        self.recvBuffer = ""
        self.sendBuffer = Queue.Queue()
        self.logger  = Logger.getLogger(__name__ + ".DCCHandler_" + sender.nick, bot.lognormal, bot.logerrors)

    def __del__(self):
        self.logger.info("Connection with %s timedout" % self.sender)
        if self.sender.nick in self.bot.users:
            self.bot.users[self.sender.nick].dccSocket = None
        self.close()
        #super(DCCHandler, self).__del__()

    def sendMsg(self, msg):
        self.sendBuffer.put_nowait(msg + EOL)

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
            self.bot.cmdHandler.parseCmd(":%s PRIVMSG %s :%s%s" % (self.sender.toString(), self.bot.nick, self.bot.cmdChar, line.lstrip(self.bot.cmdChar)))

    def handle_write(self):
        if not self.sendBuffer.empty():
            msg = self.sendBuffer.get_nowait()
            self.logger.info("Send >" + msg.strip())
            self.send(msg)
            self.sendBuffer.task_done()
        else:
            time.sleep(0.001)

    def handle_close(self):
        self.logger.info("Connection with %s closed" % self.sender)
        if self.sender.nick in self.bot.users:
            self.bot.users[self.sender.nick].dccSocket = None
        self.close()

    # def handle_error(self):
    #     self.logger.info("Connection with %s errored"%self.sender)
    #     super.handle_error()
    #     if self.sender.nick in self.bot.users:
    #         self.bot.users[self.sender.nick].dccSocket = None
    #     self.close()

class DCCSocket(asyncore.dispatcher):

    def __init__(self, bot):
        self.bot = bot
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind(('', 0))
        self.listen(5)

        self.logger  = Logger.getLogger("%s-%s-%s" % (__name__, self.bot.nick, self.bot.host) + ".DCCSocket", bot.lognormal, bot.logerrors)
        self.logger.info("Listening on %s:%s" % self.getAddr())

        self.pending = {}
        self.open    = {}

        self.indexAnon = 0

        self.use_ssl = bot.use_ssl
        if self.use_ssl:
            self.send = self._ssl_send
            self.recv = self._ssl_recv

        self.ssl = None

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

    def handle_connect(self):
        """ Initializes SSL support after the connection has been made. """
        self.logger.info("Connecting DCC Socket...")
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

    def handle_accept(self):
        pair = self.accept()
        if pair is not None:
            sock, addr = pair
            self.logger.info('Incoming connection from %s' % repr(addr))

            targip = addr[0]
            sender = None
            welcomeMsg = []

            if targip in self.pending:
                sender = self.pending[targip]
                welcomeMsg.append("DCC Session activated")
                welcomeMsg.append("You can use 'help' to see the available commands.")
                welcomeMsg.append("Have a nice day!")

            if not targip in self.pending and not self.bot.dccAllowAnon:
                self.logger.error("Address %s not found in the pending connection list!" % targip)
                return

            if not targip in self.pending and self.bot.dccAllowAnon:
                sender = Sender("AnonUser_%04d!~AnonUser_%04d@dev.null" % (self.indexAnon, self.indexAnon))
                self.bot.users[sender.nick] = sender
                self.pending[targip] = sender
                self.indexAnon += 1
                welcomeMsg.append("DCC Session activated")
                welcomeMsg.append("You have been dropped to read-only because your IP couldn't be tied to a nick")
                welcomeMsg.append("This might be due to a problem with your bouncer if you are using one")
                welcomeMsg.append("You can use 'help' to see the available commands.")
                welcomeMsg.append("Have a nice day !")

            self.open[targip] = sender
            del self.pending[targip]

            handler = DCCHandler(self.bot, sock, sender)
            sender.dccSocket = handler

            for msg in welcomeMsg:
                self.bot.sendMessage(sender.nick, msg)

    def getAddr(self):
        with closing(socket.socket(socket.AF_INET, socket.SOCK_DGRAM)) as s:
            s.connect(('8.8.8.8', 80))
            return s.getsockname()[0], self.socket.getsockname()[1]

    def addPending(self, sender):
        try:
            addr_info = socket.getaddrinfo(sender.host, None)
            ip = None
            for entry in addr_info:
                if len(entry[4]) == 2:
                    ip = entry[4][0]
                    break

            if not ip:
                self.logger.info('Unable to find IPv4 address in address info: ' + str(addr_info))
                return False

            self.logger.info("Adding %s - %s to the pending list" % (ip, sender))
            self.pending[ip] = sender
            return True
        except Exception as e:
            self.bot.sendNotice(sender.nick, "Error while initializing DCC connection.")
            print str(e)
            return False

    def readable(self):
        if isinstance(self.socket, ssl.SSLSocket):
            # dispatch any bytes left in the SSL buffer
            while self.socket.pending() > 0:
                self.handle_read_event()
        return True
