import logging, logging.handlers

def getLogger(name, lognormal='botlog.log', logerror='errors.log', lognormalmaxsize=1024*1024, logerrormaxsize=1024*1024):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if len(logger.handlers) == 0:
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(levelname)8s - %(funcName)16s - %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)

        fh = logging.handlers.RotatingFileHandler(logerror, backupCount=5, maxBytes=logerrormaxsize)
        fh.setLevel(logging.WARNING)
        fh.setFormatter(formatter)
        logger.addHandler(fh)

        nh = logging.handlers.RotatingFileHandler(lognormal, backupCount=30, maxBytes=lognormalmaxsize)
        nh.setLevel(logging.INFO)
        nh.setFormatter(formatter)
        logger.addHandler(nh)

    return logger

#def setLoggerLevel(lvl):
#    logger.setLevel(lvl)