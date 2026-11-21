"""Circuit de validation et identité de l'utilisateur courant."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

State = Literal["draft", "in_review", "approved", "rejected"]
Role = Literal["consultant", "reviewer", "admin"]


class Transition(BaseModel):
    model_config = ConfigDict(frozen=True)

    to: State
    reason: str | None = None


class CurrentUser(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    role: Role
