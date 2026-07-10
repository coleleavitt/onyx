from pydantic import BaseModel


class WorkflowPinsResponse(BaseModel):
    workflow_ids: list[str]
