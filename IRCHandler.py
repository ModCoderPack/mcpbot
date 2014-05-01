import threading
import Logger
import re
import traceback
import sets

EOL = "\r\n"
CTCPTAG = chr(1)

###########################################################################################################

class Sender(object):
    def __init__(self, sender):
        self.nick    = ""
        self.regnick = ""
        self.ident = ""
        self.host  = ""
        self.auth  = -1
        self.authEvent  = threading.Event()
        self.whoisEvent = threading.Event()
        self.dccSocket = None

        if not '!' in sender:
            self.nick = sender[1:]
        else:
            self.nick  = sender.split('!')[0][1:]
            self.ident = sender.split('!')[1].split('@')[0]
            self.host  = sender.split('!')[1].split('@')[1]

    def __repr__(self):
        return "%s!%s@%s"%(self.nick, self.ident, self.host)

    def toString(self):
        return "%s!%s@%s"%(self.nick, self.ident, self.host)

    def unauthenticate(self):
        self.auth = -1
        self.regnick = ""
        self.authEvent.clear()
        self.whoisEvent.clear()        

    def authenticate(self, level):
        self.auth = level
        self.authEvent.set()

class CmdGenerator(object):

    @classmethod
    def getNICK(cls, oldnick, nick):
        return ":{nick} NICK {nick}".format(nick = nick) + EOL

    @classmethod
    def getUSER(cls, nick):
        return ":{nick} USER {username} {hostname} {servername} :{realname}".format(nick = nick, 
                                                                                    username=nick, 
                                                                                    hostname="none", 
                                                                                    servername="none", 
                                                                                    realname=nick) + EOL

    @classmethod
    def getPONG(cls, msg):
        return "PONG {msg}".format(msg=msg) + EOL

    @classmethod
    def getJOIN(cls, channel, key=None):
        if key:
            return "JOIN {channel}; {key}".format(channel=channel, key=key) + EOL
        else:
            return "JOIN {channel}".format(channel=channel) + EOL

    @classmethod
    def getNOTICE(cls, dest, msg):
        return "NOTICE {dest} :{msg}".format(dest = dest, msg = msg) + EOL

    @classmethod
    def getPRIVMSG(cls, dest, msg):
        return "PRIVMSG {dest} :{msg}".format(dest = dest, msg = msg) + EOL     

    @classmethod
    def getCTCP(cls, msg):
        return "%s%s%s"%(CTCPTAG,msg,CTCPTAG)

    @classmethod
    def getWHOIS(cls, nick):
        return "WHOIS {nick}".format(nick = nick) + EOL

    @classmethod
    def getDCCCHAT(cls, dest, addr, port):
        ctcpmsg = CmdGenerator.getCTCP("DCC CHAT chat {addr} {port}".format(addr=CmdGenerator.conv_ip_std_long(addr), port=port))
        privmsg = CmdGenerator.getPRIVMSG(dest, ctcpmsg)
        return privmsg

    @classmethod
    def conv_ip_long_std(cls, longip):
        try:
            ip = long(longip)
        except ValueError:
            return '0.0.0.0'
        if ip >= 2 ** 32:
            return '0.0.0.0'
        address = [str(ip >> shift & 0xFF) for shift in [24, 16, 8, 0]]
        return '.'.join(address)

    @classmethod
    def conv_ip_std_long(self, stdip):
        address = stdip.split('.')
        if len(address) != 4:
            return 0
        longip = 0
        for part, shift in zip(address, [24, 16, 8, 0]):
            try:
                ip_part = int(part)
            except ValueError:
                return 0
            if ip_part >= 2 ** 8:
                return 0
            longip += ip_part << shift
        return longip

###########################################################################################################

class CmdHandler(object):
    def __init__(self, bot, socket):
        self.bot     = bot
        self.socket  = socket
        self.sender  = ""
        self.cmd     = ""
        self.params  = []
        self.logger  = Logger.getLogger(__name__, bot.lognormal, bot.logerrors)
        self.commands  = {}
        self.callbacks = {}
        self.irccmds   = {
        'PING':   {'callback':self.onPING},
        'NOTICE': {'callback':self.onNOTICE},
        'PRIVMSG':{'callback':self.onPRIVMSG},
        'INVITE': {'callback':self.onINVITE},
        'JOIN':   {'callback':self.onJOIN},
        'PART':   {'callback':self.onPART},
        'MODE':   {'callback':self.onMODE},
        'KICK':   {'callback':self.onKICK},                                                
        'QUIT':   {'callback':self.onQUIT},              
        'KILL':   {'callback':self.onKILL},
        'NICK':   {'callback':self.onNICK},
        }

        self.rplcmds = {
        376 : {'name':'RPL_ENDOFMOTD', 'callback':self.onRPL_ENDOFMOTD},
        330 : {'name':'RPL_WHOISACCOUNT', 'callback':self.onRPL_WHOISACCOUNT}
        }

    def registerCommand(self, command, callback, groups, minarg, maxarg, desc = None):
        if not groups:
            groups = ['any']

        self.commands[command] = {'command':command, 'callback':callback, 'groups':groups, 'minarg':minarg, 'maxarg':maxarg, 'desc':desc}
        for group in groups:
            if not group in self.bot.groups:
                self.bot.groups[group]= sets.Set()
            self.bot.groups[group].add(command)

        self.bot.updateConfig()

    def registerEvent(self, event, callback):
        if not event in self.callbacks.keys():
            self.callbacks[event] = []
        self.callbacks[event].append(callback)

    def handleEvents(self, event, sender, params):
        if event in self.callbacks:
           for callback in self.callbacks[event]:
                cmdThread = threading.Thread(target=self.threadedEvent, name="%s:%s"%(sender.toString(),event), args=(event, callback, self.bot, sender, params))
                cmdThread.start()

    def threadedEvent(self, event, callback, bot, sender, params):
        try:    
            callback(bot, sender, params)
        except Exception as e:
            self.logger.error("Error while handling event [ %s ] with params %s from user [ %s ]"%(event, params, sender))
            self.logger.error("%s"%e)
            for line in traceback.format_exc().split('\n'):
                self.logger.error(line)            

    def parseCmd(self, msg):
        if msg.strip() == "":
            return

        elems = msg.strip().split()

        if elems[0][0] == ':':
            self.sender = Sender(elems[0])
            elems.pop(0)
        else:
            self.sender = Sender("")

        self.cmd = elems[0]

        if len(elems) > 1:
            self.params = elems[1:]

        try:
            cmd = int(self.cmd)
            self.onNUMERICAL(self.sender, cmd, self.params)
            return
        except Exception as e:
            pass

        if self.cmd in self.irccmds:
            try:
                self.irccmds[self.cmd]['callback'](self.sender, self.params)
            except Exception as e:
                self.logger.error("Error while handling command [ %s ] with params %s from user [ %s ]"%(self.cmd, self.params, self.sender))
                self.logger.error("%s"%e)
                for line in traceback.format_exc().split('\n'):
                    self.logger.error(line)                
        else:
            self.logger.debug("Cmd > %s %s %s"%(self.sender, self.cmd, self.params))            

    #######################################################
    #IRC Commands
    def onPING(self, sender, params):
        self.logger.debug("[S : %s] [M : %s]"%(sender.nick, " ".join(params)))        
        self.bot.sendRaw(CmdGenerator.getPONG(params[0]))
        self.handleEvents('Ping', sender, params)

    def onNOTICE(self, sender, params):
        self.logger.debug("[S : %s] [M : %s]"%(sender.nick, " ".join(params)))        

        #We received a notice from NickServ. We check if it is an ACC notice
        if (sender.nick.lower() == 'nickserv'):
            reMatch = re.match(self.bot.authRegex, " ".join(params[1:])[1:])
            if reMatch:
                #We check that the user exists in our tables, we setup the lvl value & unlock the command thread.
                if not reMatch.group('nick') in self.bot.users:
                    self.logger.error("Received unkown user auth level : %s %s"%(reMatch.group('nick'), reMatch.group('level')))
                else:
                    self.bot.users[reMatch.group('nick')].authenticate(int(reMatch.group('level')))
                    self.logger.debug("Auth notice for %s with level %s"%(reMatch.group('nick'), reMatch.group('level')))

        self.handleEvents('Notice', sender, params)

    def onINVITE(self, sender, params):
        self.logger.debug("[S : %s] [M : %s]"%(sender.nick, " ".join(params)))        
        if self.bot.autoInvite:
            self.bot.join(params[1])
        self.handleEvents('Invite', sender, params)

    def onJOIN(self, sender, params):
        self.logger.debug("[S : %s] [M : %s]"%(sender.nick, " ".join(params)))        
        if sender.nick == self.bot.nick:
            self.logger.debug("Adding chan %s to chan list"%(params[0]))
            self.bot.channels.add(params[0])
            self.bot.updateConfig()

        self.handleEvents('Join', sender, params)

    def onPART(self, sender, params):
        self.logger.debug("[S : %s] [M : %s]"%(sender.nick, " ".join(params)))        
        if sender.nick == self.bot.nick:        
            self.logger.debug("Removing chan %s to chan list"%(params[0]))
            self.bot.channels.remove(params[0])   
            self.bot.updateConfig()
        if sender.nick in self.bot.users:
            self.bot.users[sender.nick].unauthenticate()
            self.bot.users[sender.nick].whoisEvent.clear()            
        self.handleEvents('Part', sender, params)

    def onMODE(self, sender, params):
        self.logger.debug("[S : %s] [M : %s]"%(sender.nick, " ".join(params)))        
        self.handleEvents('Mode', sender, params)

    def onKICK(self, sender, params):
        self.logger.debug("[S : %s] [M : %s]"%(sender.nick, " ".join(params)))        
        if params[1] == self.bot.nick:        
            self.logger.debug("Removing chan %s to chan list"%(params[0]))
            self.bot.channels.remove(params[0])   
            self.bot.updateConfig()           
        if sender.nick in self.bot.users:
            self.bot.users[sender.nick].unauthenticate()                    
            self.bot.users[sender.nick].whoisEvent.clear()            
        self.handleEvents('Kick', sender, params)

    def onNICK(self, sender, params):
        self.logger.debug("[S : %s] [M : %s]"%(sender.nick, " ".join(params)))        
        if sender.nick in self.bot.users:
            self.bot.users[sender.nick].unauthenticate()                    
            self.bot.users[sender.nick].whoisEvent.clear()
        self.handleEvents('Nick', sender, params)        

    def onQUIT(self, sender, params):
        self.logger.debug("[S : %s] [M : %s]"%(sender.nick, " ".join(params)))        
        self.handleEvents('Quit', sender, params)

    def onKILL(self, sender, params):
        self.logger.debug("[S : %s] [M : %s]"%(sender.nick, " ".join(params)))        
        self.handleEvents('Kill', sender, params)

    def onPRIVMSG(self, sender, params):
        dest = params[0]             #Chan or private dest
        msg  = ' '.join(params[1:])  #We stich the chat msg back together
        msg  = msg[1:]               #We remove the leading :

        if (msg[0] == self.bot.cmdChar):
            self.onCOMMAND(sender, dest, msg[1:])   #We remove the cmd symbol before passing the cmd to the bot
        elif msg[0] == CTCPTAG and msg[-1] == CTCPTAG:
            self.onCTCP(sender, dest, msg[1:-1].split())
        else:
            self.logger.debug("%s %s"%(sender.nick, " ".join(params)))        
            self.handleEvents('Privmsg', sender, params)

    #######################################################
    # Numerical RPL handling
    def onNUMERICAL(self, sender, cmd, params):
        if int(cmd) in self.rplcmds.keys():
            self.rplcmds[cmd]['callback'](sender, params)
        else:
            self.logger.debug("%03d [S: %s] [M: %s]"%(cmd, sender.nick, " ".join(params)))
        self.handleEvents(int(cmd), sender, params)



    def onRPL_ENDOFMOTD(self, sender, params):
        self.logger.debug("[S : %s] [M : %s]"%(sender.nick, " ".join(params)))        
        if self.bot.autoJoin and not self.bot.isReady:
            self.bot.isReady = True
            for chan in self.bot.channels:
                if not chan.strip() or not chan[0] == '#':
                    continue
                self.bot.join(chan)          

    def onRPL_WHOISACCOUNT(self, sender, params):
        self.logger.debug("[S : %s] [M : %s]"%(sender.nick, " ".join(params)))  
        if params[1] in self.bot.users:
            self.bot.users[params[1]].regnick = params[2]
            self.bot.users[params[1]].whoisEvent.set()



    #######################################################
    # User defined commands
    def onCOMMAND(self, sender, dest, command):
        self.logger.info("COMMAND> %s"%command)
        if not command.split()[0] in self.commands.keys():
            return

        cmd  = self.commands[command.split()[0]]
        args = command.split()[1:] if len(command.split()) > 1 else []
        callback = cmd['callback']

        if len(args) < cmd['minarg'] or len(args) > cmd['maxarg']:
            if cmd['desc']:
                self.bot.sendNotice(sender.nick, "Wrong syntax : %s"%cmd['desc'])
                return
            else:
                self.bot.sendNotice(sender.nick, "Wrong number of arguments : min = %s, max = %s"%(cmd['minarg'], cmd['maxarg']))
                return                

        self.bot.sendRaw(self.bot.nickAuth.format(nick=sender.nick) + EOL)
        self.bot.sendRaw(CmdGenerator.getWHOIS(sender.nick))
        self.bot.users[sender.nick] = sender

        #We start the command thread
        cmdThread = threading.Thread(target=self.threadedCommand, name=sender.toString(), args=(callback, cmd, self.bot, sender, dest, args))
        cmdThread.start()

    def threadedCommand(self, callback, cmd, bot, sender, dest, args):
        try:
            #We block until we received the answer from nickserv and we start the command if the nick is registered.
            #TODO :  If the nick is not registered, send back a msg asking for registration.
            if not bot.users[sender.nick].authEvent.wait(10):
                bot.sendNotice(sender.nick, "Error contacting nickserv. Please retry later.")
                return

            if not bot.users[sender.nick].auth == 3:
                bot.sendNotice(sender.nick, "You need to register your nick before using the bot.")
                return                

            if not bot.users[sender.nick].whoisEvent.wait(10):
                bot.sendNotice(sender.nick, "Error doing a whois. Please retry later.")
                return

            userValid = False

            if cmd['command']  in bot.groups['any']:
                userValid = True

            else:
                for group, commands in bot.groups.items():
                    if cmd['command'].lower() in commands and sender.regnick.lower() in bot.authUsers:
                        if group in bot.authUsers[sender.regnick.lower()]:
                            userValid = True

            if sender.regnick.lower() in bot.authUsers and 'admin' in bot.authUsers[sender.regnick.lower()]:
                userValid = True

            if userValid:
                callback(bot, sender, dest, cmd, args)
            else:
                bot.sendNotice(sender.regnick, "You don't have the right to run this command")

        except Exception as e:
            self.logger.error("Error while handling command [ %s ] from user [ %s ] to [ %s ] with args [ %s ]"%(cmd, sender, dest, args))
            self.logger.error("%s"%e)
            for line in traceback.format_exc().split('\n'):
                self.logger.error(line)


    #######################################################
    # CTCP Commands
    def onCTCP(self, sender, dest, msg):
        self.logger.debug("[S : %s] [M : %s]"%(sender.nick, " ".join(params)))        

        if (msg[0] == 'VERSION'):
            self.bot.sendRaw(CmdGenerator.getNOTICE(sender.nick, "MCPBot v4.0 'You were not expecting me !' by ProfMobius"))
            self.handleEvents('Version', sender, msg)

        elif (msg[0] == 'USERINFO'):
            self.bot.sendRaw(CmdGenerator.getNOTICE(sender.nick, "MCPBot v4.0 'You were not expecting me !' by ProfMobius"))
            self.handleEvents('Userinfo', sender, msg)            

        elif (msg[0] == 'FINGER'):
            self.bot.sendRaw(CmdGenerator.getNOTICE(sender.nick, "Don't do that !"))
            self.handleEvents('Finger', sender, msg)            

        elif (msg[0] == 'DCC'):
            self.onDCC(sender, dest, msg)

        else:
            self.handleEvents('CTCP', sender, msg)

    #######################################################
    # DCC Commands
    def onDCC(self, sender, dest, msg):
        self.logger.info("%s %s %s"%(sender, msg, CmdGenerator.conv_ip_long_std(msg[3])))
        self.bot.Raw(CmdGenerator.getNOTICE(sender.nick, "Don't call me, I will call you."))
        host, port = self.bot.dccSocket.getAddr()
        self.bot.dccSocket.addPending(sender)
        self.bot.sendRaw(CmdGenerator.getDCCCHAT(sender.nick, host, port))
        self.handleEvents('DCC', sender, msg)


# UNIMPLEMENTED COMMANDS :
# PASSWORD
# SERVER
# OPER
# SQUIT
# TOPIC
# NAMES
# LIST
# VERSION
# STATS
# LINKS
# TIME
# CONNECT
# TRACE
# ADMIN
# INFO
# WHO
# WHOIS
# WHOWAS
# ERROR