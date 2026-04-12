from datetime import datetime

from pydantic import BaseModel


class AttachmentMeta(BaseModel):
    """Attachment metadata — no binary data included."""
    id: int
    filename: str
    content_type: str
    size_bytes: int
    uploaded_at: datetime

    model_config = {'from_attributes': True}
