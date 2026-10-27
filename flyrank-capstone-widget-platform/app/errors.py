"""Errors the service layer raises; main.py turns each one into a clean JSON response."""
import math


class AppError(Exception):
    status_code = 500

    def __init__(self, message, *, headers=None, fields=None):
        super().__init__(message)
        self.message = message
        self.headers = headers or {}
        self.fields = fields


class BadRequest(AppError):
    status_code = 400


class Unauthorized(AppError):
    status_code = 401


class NotFound(AppError):
    status_code = 404


class PayloadTooLarge(AppError):
    status_code = 413


class RateLimited(AppError):
    status_code = 429

    def __init__(self, retry_after_seconds):
        wait = max(1, math.ceil(retry_after_seconds))
        super().__init__("Too many requests. Please slow down.", headers={"Retry-After": str(wait)})
