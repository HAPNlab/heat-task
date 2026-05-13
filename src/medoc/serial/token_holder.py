class TokenHolder:
    def __init__(self) -> None:
        self.token: int = 0

    def __add__(self, other):
        if not isinstance(other, int):
            raise ValueError("Attempted to increment token with non-int value")
        new_tok = TokenHolder()
        new_tok.token += other
        return new_tok
