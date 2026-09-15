import logging


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        fields = [
            f"event={getattr(record, 'event', record.getMessage())}",
            f"level={record.levelname}",
        ]
        for name in ("session_id", "provider", "model", "operation", "error_type"):
            value = getattr(record, name, None)
            if value is not None:
                fields.append(f"{name}={value}")
        return " ".join(fields)


def configure_logging() -> None:
    app_logger = logging.getLogger("app")
    if any(
        isinstance(handler, logging.StreamHandler)
        and isinstance(handler.formatter, StructuredFormatter)
        for handler in app_logger.handlers
    ):
        return

    handler = logging.StreamHandler()
    handler.setFormatter(StructuredFormatter())
    app_logger.addHandler(handler)
    app_logger.setLevel(logging.INFO)
    app_logger.propagate = False
