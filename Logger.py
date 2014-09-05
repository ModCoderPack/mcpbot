import logging

def getLogger(name, lognormal='botlog.log', logerror='errors.log'):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if len(logger.handlers) == 0:
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(levelname)8s - %(funcName)20s - %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)

        fh = logging.FileHandler(logerror)
        fh.setLevel(logging.WARNING)
        fh.setFormatter(formatter)
        logger.addHandler(fh)

        nh = logging.FileHandler(lognormal)
        nh.setLevel(logging.INFO)
        nh.setFormatter(formatter)
        logger.addHandler(nh)

    return logger

#def setLoggerLevel(lvl):
#    logger.setLevel(lvl)