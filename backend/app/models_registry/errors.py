"""Erreur métier du registre, mappée en {"error": {code, message}} par l'API et en code de sortie par la CLI."""


class RegistryError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message
