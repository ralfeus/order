from logging import Logger
from logging import basicConfig, debug, error, exception, fatal, \
    getLevelName as _getLevelName, getLogger as _getLogger, info, warning
from logging import DEBUG, INFO
from logging import _levelToName, _nameToLevel, root

__all__ = ['BASIC_FORMAT', 'BufferingFormatter', 'CRITICAL', 'DEBUG', 'ERROR',
           'FATAL', 'FileHandler', 'Filter', 'Formatter', 'Handler', 'INFO',
           'LogRecord', 'LoggerAdapter', 'NOTSET', 'NullHandler',
           'StreamHandler', 'WARN', 'WARNING', 'addLevelName', 'basicConfig',
           'captureWarnings', 'critical', 'debug', 'disable', 'error',
           'exception', 'fatal', 'getLevelName', 'getLogger', 'getLoggerClass',
           'info', 'makeLogRecord', 'root', 'setLoggerClass', 'shutdown',
           'warning', 'getLogRecordFactory', 'setLogRecordFactory',
           'lastResort', 'raiseExceptions', 'getLevelNamesMapping']

FINE = 15

_levelToName = {**_levelToName, 
    FINE: 'FINE'
}
_nameToLevel = {**_nameToLevel, 
    'FINE': FINE
}

class OrderLogger(Logger):
    def fine(self, msg, *args, **kwargs):
        if self.isEnabledFor(FINE):
            self._log(FINE, msg, args, **kwargs)

def getLevelName(level):
    return _levelToName.get(level) or _getLevelName(level)

def getLogger(name=None) -> OrderLogger:
    """
    Get a logger with the specified name. If no name is provided, the root logger is returned.
    """
    return _getLogger(name) #type: ignore

Logger.manager.setLoggerClass(OrderLogger)
