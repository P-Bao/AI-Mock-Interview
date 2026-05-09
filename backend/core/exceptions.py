from fastapi import HTTPException, status


class SessionNotFoundException(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")


class EvaluationFailedException(HTTPException):
    def __init__(self, detail: str = "Evaluation failed") -> None:
        super().__init__(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)


class InvalidTranscriptException(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Transcript must contain at least one entry with role "user"',
        )

