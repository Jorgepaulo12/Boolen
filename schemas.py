from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    username: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    profile_picture: Optional[str] = None
    is_admin: bool = False
    created_at: datetime

    class Config:
        from_attributes = True

class CourseBase(BaseModel):
    title: str
    description: str
    price: float
    duration_minutes: int

class CourseCreate(CourseBase):
    pass

class Course(CourseBase):
    id: int
    course_code: str
    cover_image: Optional[str] = None
    file_path: Optional[str] = None
    uploaded_by: int
    created_at: datetime
    status: str
    instructor: User

    class Config:
        from_attributes = True

class CourseDownloadBase(BaseModel):
    course_id: int

class CourseDownload(CourseDownloadBase):
    id: int
    enrollment_code: str
    user_id: int
    downloaded_at: datetime
    status: str = "active"
    progress: float = 0.0
    last_accessed: Optional[datetime] = None
    course: Course
    user: User

    class Config:
        from_attributes = True

class WalletBase(BaseModel):
    balance: float = 0.0

class WalletCreate(WalletBase):
    user_id: int

class Wallet(WalletBase):
    id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class WalletTransactionBase(BaseModel):
    amount: float
    transaction_type: str
    payment_ref: Optional[str] = None

class WalletTransactionCreate(WalletTransactionBase):
    wallet_id: int

class WalletTransaction(WalletTransactionBase):
    id: int
    wallet_id: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class UserProfile(BaseModel):
    email: str
    username: str
    profile_picture: Optional[str] = None
    created_at: datetime
    courses_downloaded: List[CourseDownload] = []
    courses_created: List[Course] = []

    class Config:
        from_attributes = True

class PaymentInitialize(BaseModel):
    mobile: str
    amount: str
    charge_id: str
    mobile_money_operator_ref_id: str = "20be6c20-adeb-4b5b-a7ba-0769820df4fb"

class PaymentResponse(BaseModel):
    status: str
    message: str
    data: dict

class PaymentVerification(BaseModel):
    ref_id: str
    status: str
    transaction_id: Optional[str] = None

class UserProfileUpdate(BaseModel):
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None