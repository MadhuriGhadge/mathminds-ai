from enum import Enum

class ErrorCodes(str, Enum):
    INTERNAL_ERROR = "ERR_001"
    INPUT_VALIDATION_ERROR = "ERR_002"
    RESOURCE_NOT_FOUND = "ERR_003"
    DEPENDENCY_ERROR = "ERR_004"
    GEMINI_ERROR = "ERR_005"
    RATE_LIMIT_EXCEEDED = "ERR_006"

ERROR_MESSAGES = {
    ErrorCodes.INTERNAL_ERROR: "An unexpected internal error occurred.",
    ErrorCodes.INPUT_VALIDATION_ERROR: "The input provided is invalid.",
    ErrorCodes.RESOURCE_NOT_FOUND: "The requested resource was not found.",
    ErrorCodes.DEPENDENCY_ERROR: "A downstream service is currently unavailable.",
    ErrorCodes.GEMINI_ERROR: "Unable to generate a solution at this time.",
    ErrorCodes.RATE_LIMIT_EXCEEDED: "Too many requests. Please try again later."
}

class AppError(Exception):
    def __init__(self, code: ErrorCodes, message: str = None, original_exception: Exception = None):
        self.code = code
        self.message = message or ERROR_MESSAGES.get(code, "Unknown Error")
        self.original_exception = original_exception
        super().__init__(self.message)
