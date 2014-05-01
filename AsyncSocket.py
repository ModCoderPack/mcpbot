import asyncore, socket
import Logger
import Queue
from IRCHandler import CmdGenerator

class AsyncSocket(asyncore.dispatcher):

    def __init__(self, bot, host, port):
        self.bot  = bot
        self.host = host
        self.port = port
        self.recvBuffer = ""
        self.sendBuffer = Queue.Queue()
        #self.cmdHandler = CmdHandler(self)
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.logger  = Logger.getLogger(__name__, bot.lognormal, bot.logerrors)

        self.logger.debug("%s:%s"%(host, port))

    def doConnect(self):
        self.connect((self.host, self.port))

    def handle_connect(self):
        self.logger.debug("Connecting...")

    def handle_close(self):
        self.logger.debug("Closing...")
        self.close()

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

            if not self.bot.isIdentified:
                self.sendBuffer.put_nowait(CmdGenerator.getNICK(self.bot.nick, self.bot.nick))
                self.sendBuffer.put_nowait(CmdGenerator.getUSER(self.bot.nick))
                self.bot.isIdentified = True


    def handle_write(self):
        if not self.sendBuffer.empty():
            msg = self.sendBuffer.get_nowait()
            self.logger.debug("Send >" + msg.strip())
            self.send(msg)
            self.sendBuffer.task_done()
            
        #for ircmsg in self.sendBuffer:
        #    self.logger.debug("Send >" + ircmsg.strip())
        #    self.send(ircmsg)
        #self.sendBuffer = []