import asyncore, socket
import Logger
import time
import Queue
import urllib
from IRCHandler import CmdGenerator

EOL = "\r\n"
CTCPTAG = chr(1)

class DCCHandler(asyncore.dispatcher):

    def __init__(self, bot, sock, sender):
        asyncore.dispatcher.__init__(self, sock)
        self.bot = bot
        self.sender = sender
        self.recvBuffer = ""
        self.sendBuffer = Queue.Queue()
        self.logger  = Logger.getLogger(__name__+".DCCHandler", bot.lognormal, bot.logerrors)

    def __del__(self):
        self.logger.info("Connection with %s timedout"%self.sender)
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
            self.bot.cmdHandler.parseCmd(":%s PRIVMSG %s :%s%s"%(self.sender.toString(), self.bot.nick, self.bot.cmdChar, line))

    def handle_write(self):
        if not self.sendBuffer.empty():
            msg = self.sendBuffer.get_nowait()
            self.logger.debug("Send >" + msg.strip())
            self.send(msg)
            self.sendBuffer.task_done()
        else:
            time.sleep(0.001)       

    def handle_close(self):
        self.logger.info("Connection with %s closed"%self.sender)
        if self.sender.nick in self.bot.users:
            self.bot.users[self.sender.nick].dccSocket = None
        self.close()

    def handle_error(self):
        self.logger.info("Connection with %s errored"%self.sender)
        if self.sender.nick in self.bot.users:
            self.bot.users[self.sender.nick].dccSocket = None
        self.close()

class DCCSocket(asyncore.dispatcher):

    def __init__(self, bot):
        self.bot = bot
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET & socket.AF_INET6, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind(('', 0))
        self.listen(5)

        self.logger  = Logger.getLogger(__name__+".DCCSocket", bot.lognormal, bot.logerrors)        
        self.logger.info("Listening on %s:%s"%self.getAddr())

        self.pending = {}
        self.open    = {}

    def handle_accept(self):
        pair = self.accept()
        if pair is not None:
            sock, addr = pair
            self.logger.debug('Incoming connection from %s' % repr(addr))

            targip = addr[0]
            sender = self.pending[targip]

            if not targip in self.pending:
                self.logger.error("Address %s not found in the pending connection list !"%targip)
                return

            self.open[targip] = sender
            del self.pending[targip]

            handler = DCCHandler(self.bot, sock, sender)
            sender.dccSocket = handler

            self.bot.sendMessage(sender.nick, "DCC Session activated")

    def getAddr(self):
        return urllib.urlopen('http://icanhazip.com/').readlines()[0].strip(), self.socket.getsockname()[1]
        #return socket.gethostbyname(self.bot.hostname), self.socket.getsockname()[1]
        #return self.socket.getsockname()[0], self.socket.getsockname()[1]

    def addPending(self, sender):
        try:
            self.logger.debug("Adding %s - %s to the pending list"%(socket.gethostbyname(sender.host), sender))
            self.pending[socket.gethostbyname(sender.host)] = sender
            return True
        except Exception as e:
            print str(e)
            if "Address family for hostname not supported" in str(e):
                self.bot.sendNotice(sender.nick, "Support for IPv6 pending.")                
            else:
                self.bot.sendNotice(sender.nick, "Error while initialiasing DCC connection.")
            return False
