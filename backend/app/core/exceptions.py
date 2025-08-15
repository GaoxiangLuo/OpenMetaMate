class MetaMateException(Exception):
    """Base exception for MetaMate API"""

    pass


class PDFProcessingError(MetaMateException):
    """Raised when PDF processing fails"""

    pass


class ExtractionError(MetaMateException):
    """Raised when data extraction fails"""

    pass
