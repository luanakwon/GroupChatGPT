import logging
import logging.config

LOGGING_CONFIG = {
    "version": 1,
    "formatters": {
        "default": {
            "format": "[%(asctime)s] %(levelname)s - %(name)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "level": "DEBUG",
        },
        "file": {
            "class": "logging.FileHandler",
            "formatter": "default",
            "level": "INFO",
            "filename": "app.log",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "DEBUG",
    },
    "loggers": {
        "discord": {  # 👈 Make sure you explicitly configure discord logger
            "level": "INFO",  # or DEBUG if you want everything
            "handlers": ["console", "file"],
            "propagate": False,
        },
        "openai":{
            "level":"INFO",
            "handlers":["console"],
            "propagate": False,
        },
        "httpcore":{
            "level":"INFO",
            "handlers":["console"],
            "propagate": False,
        }
    }
}

def set_logging():
    logging.config.dictConfig(LOGGING_CONFIG)
    logger = logging.getLogger(__name__)
    logger.info("App started")
