class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found."):
        super().__init__(code="NOT_FOUND", message=message, status_code=404)


class BadRequestError(AppError):
    def __init__(self, code: str, message: str):
        super().__init__(code=code, message=message, status_code=400)


class ExternalServiceError(AppError):
    def __init__(self, code: str, message: str, status_code: int = 502):
        super().__init__(code=code, message=message, status_code=status_code)
