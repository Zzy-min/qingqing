# backend/gateway/errors.py (minimal, will be expanded in Task 11)
class AuthError(Exception):
    def __init__(self, provider: str, message: str, code: str = "auth_missing"):
        self.provider = provider
        self.message = message
        self.code = code
        super().__init__(message)
