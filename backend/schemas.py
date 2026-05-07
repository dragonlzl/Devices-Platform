from pydantic import BaseModel, Field
from typing import Dict, Optional


class VendorCreate(BaseModel):
    name: str = Field(..., min_length=1)


class VendorUpdate(BaseModel):
    name: str = Field(..., min_length=1)


class SystemCreate(BaseModel):
    name: str = Field(..., min_length=1)


class SystemUpdate(BaseModel):
    name: str = Field(..., min_length=1)


class VersionCreate(BaseModel):
    version: str = Field(..., min_length=1)


class VersionUpdate(BaseModel):
    version: str = Field(..., min_length=1)


class DeviceCreate(BaseModel):
    model: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)
    type: Optional[str] = None
    vendor_id: int
    system_id: int
    system_version_id: int
    resolution: Optional[str] = None
    arch: Optional[str] = None
    cpu: Optional[str] = None
    boot_password: Optional[str] = None
    notes: Optional[str] = None


class DeviceUpdate(BaseModel):
    model: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)
    type: Optional[str] = None
    vendor_id: int
    system_id: int
    system_version_id: int
    resolution: Optional[str] = None
    arch: Optional[str] = None
    cpu: Optional[str] = None
    boot_password: Optional[str] = None
    notes: Optional[str] = None
    loan_status: Optional[str] = None


class BorrowRequest(BaseModel):
    borrower_name: str = Field(..., min_length=1)
    expected_return_at: str = Field(..., min_length=1)


class ExtendRequest(BaseModel):
    expected_return_at: str = Field(..., min_length=1)


class BorrowerChangeRequest(BaseModel):
    borrower_name: str = Field(..., min_length=1)
    expected_return_at: str = Field(..., min_length=1)


class VendorDeleteRequest(BaseModel):
    rebind_vendor_id: Optional[int] = None


class SystemDeleteRequest(BaseModel):
    rebind_system_id: Optional[int] = None
    rebind_version_id: Optional[int] = None


class VersionDeleteRequest(BaseModel):
    rebind_version_id: Optional[int] = None


class SettingUpdate(BaseModel):
    webhook_url: str = Field(..., min_length=1)
    admin_url: Optional[str] = None


class NotificationParamUpdate(BaseModel):
    card_title: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)
    card_color: str = Field(..., min_length=1)
    status_color: str = Field(..., min_length=1)


class NotificationSettingsUpdate(BaseModel):
    settings: Dict[str, NotificationParamUpdate]


class WebhookNotificationParamUpdate(BaseModel):
    card_title: str = Field(..., min_length=1)
    body_template: str = Field(..., min_length=1)
    card_color: str = Field(..., min_length=1)


class WebhookNotificationSettingsUpdate(BaseModel):
    settings: Dict[str, WebhookNotificationParamUpdate]


class LLMModelCreate(BaseModel):
    name: str = Field(..., min_length=1)
    api_type: str = Field(..., min_length=1)
    base_url: str = Field(..., min_length=1)
    api_key: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    max_tokens: int = Field(..., ge=1)
    is_default: bool = False


class LLMModelUpdate(BaseModel):
    name: str = Field(..., min_length=1)
    api_type: str = Field(..., min_length=1)
    base_url: str = Field(..., min_length=1)
    api_key: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    max_tokens: int = Field(..., ge=1)
    is_default: bool = False


class LLMTestRequest(BaseModel):
    model_id: int


class LLMModelAssignRequest(BaseModel):
    role: str = Field(..., min_length=1)
