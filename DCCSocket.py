import asyncore, socket
import Logger
import time
import Queue
import urllib
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
        self.logger  = Logger.getLogger(__name__+".DCCHandler_"+sender.nick, bot.lognormal, bot.logerrors)

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
            self.logger.info("Send >" + msg.strip())
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

        self.logger  = Logger.getLogger("%s-%s-%s"%(__name__, self.bot.nick, self.bot.host)+".DCCSocket", bot.lognormal, bot.logerrors)        
        self.logger.info("Listening on %s:%s"%self.getAddr())

        self.pending = {}
        self.open    = {}

        self.indexAnon = 0

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
                self.logger.error("Address %s not found in the pending connection list!"%targip)
                return

            if not targip in self.pending and self.bot.dccAllowAnon:
                sender = Sender("AnonUser_%04d!~AnonUser_%04d@dev.null"%(self.indexAnon, self.indexAnon))
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
        #return urllib.urlopen('http://icanhazip.com/').readlines()[0].strip(), self.socket.getsockname()[1]
        #return socket.gethostbyname(self.bot.hostname), self.socket.getsockname()[1]
    #     return self.socket.getsockname()[0], self.socket.getsockname()[1]
    #
    # python -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(('8.8.8.8', 80)); print(s.getsockname()[0]); s.close()"

    def addPending(self, sender):
        try:
            self.logger.info("Adding %s - %s to the pending list"%(socket.gethostbyname(sender.host), sender))
            self.pending[socket.gethostbyname(sender.host)] = sender
            return True
        except Exception as e:
            print str(e)
            if "Address family for hostname not supported" in str(e):
                self.bot.sendNotice(sender.nick, "Support for IPv6 pending.")                
            else:
                self.bot.sendNotice(sender.nick, "Error while initialiasing DCC connection.")
            return False
