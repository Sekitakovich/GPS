from logging import config


class LogConfigure(object):

    def __init__(self, *, file: str = '', encoding: str = 'utf-8'):
        self._config = {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'simpleFormatter': {
                    'format': '[%(levelname)s] %(asctime)s %(module)s:%(lineno)s %(funcName)s : %(message)s',
                    'datefmt': '%H:%M:%S'
                },
                'plusFormatter': {
                    'format': '[%(levelname)s] %(asctime)s %(module)s:%(lineno)s %(funcName)s : %(message)s',
                    'datefmt': '%Y-%m-%d %H:%M:%S'
                }
            },
            'handlers': {
                'consoleHandler': {
                    'level': 'DEBUG',
                    'formatter': 'simpleFormatter',
                    'class': 'logging.StreamHandler',
                },
                'fileHandler': {
                    'level': 'INFO',
                    'formatter': 'plusFormatter',
                    'class': 'logging.handlers.RotatingFileHandler',
                    'filename': file,
                    'maxBytes': 1000000,
                    'backupCount': 7,
                    'encoding': encoding,
                }
            },
            'loggers': {
                'Log': {
                    'handlers': ['consoleHandler', 'fileHandler'],
                    'level': "DEBUG",
                }
            }
        }

        config.dictConfig(self._config)
