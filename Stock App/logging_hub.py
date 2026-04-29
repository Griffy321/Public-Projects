import logging 

logger = logging.getLogger("Stock App")

logging_config = {
    "version"                  : 1,
    "disable_existing_loggers" : False,
    "filters"                  : {},
    "formatters"               : {},
    "handlers"                 : {},
    "loggers"                  : {},
}

def main():
    logging.config.dictConfig(config=logging_config)
    