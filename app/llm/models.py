from pydantic import BaseModel


class GeneratedQueries(BaseModel):
    """Search queries Gemini generates for one research question."""

    queries: list[str]


class AnswerSource(BaseModel):
    """One numbered source in the answer prompt.

    The number is the position in the list, which is what the model's [n]
    markers refer to.
    """

    title: str
    url: str
    text: str
