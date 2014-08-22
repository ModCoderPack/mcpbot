import asyncore, socket
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

        self.logger.debug("%s:%s"%(host, port))

    def doConnect(self):
        self.connect((self.host, self.port))

    def handle_connect(self):
        self.logger.debug("Connecting...")

    def handle_close(self):
        self.logger.debug("Closing...")
        self.close()
        if not self.bot.isTerminating:
            sys.exit(404)

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