import asyncore, socket
import Logger
from IRCHandler import CmdGenerator

class DCCHandler(asyncore.dispatcher):

    def __init__(self, bot, sock):
        asyncore.dispatcher.__init__(self, sock)
        self.bot = bot
        self.recvBuffer = ""
        self.sendBuffer = []
        self.logger  = Logger.getLogger(__name__+".DCCHandler", bot.lognormal, bot.logerrors)

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
            self.logger.debug("Raw  >" + line)

            

class DCCSocket(asyncore.dispatcher):

    def __init__(self, bot):
        self.bot = bot
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind(('localhost', 0))
        self.listen(5)

        self.logger  = Logger.getLogger(__name__+".DCCSocket", bot.lognormal, bot.logerrors)        
        self.logger.info("Listening on %s:%s"%self.getAddr())

        self.pending = {}
        self.open    = {}

    def handle_accept(self):
        pair = self.accept()
        if pair is not None:
            sock, addr = pair
            print 'Incoming connection from %s' % repr(addr)

            if not addr in self.pending:
                self.logger.error("Address %s not found in the pending connection list !"%addr[0])
                return

            self.open[addr[0]] = self.pending[addr[0]]
            del self.pending[addr[0]]

            handler = DCCHandler(self.bot, sock)
            self.bot.users[self.pending[addr[0]]].dccSocket = handler

    def getAddr(self):
        return self.socket.getsockname()[0], self.socket.getsockname()[1]

    def addPending(self, sender):
        self.logger.debug("Adding %s - %s to the pending list"%(socket.gethostbyname(sender.host), '%s!%s'%(sender.nick,sender.ident)))
        self.pending[socket.gethostbyname(sender.host)] = '%s!%s'%(sender.nick,sender.ident)