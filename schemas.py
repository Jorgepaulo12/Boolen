from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class UserBase(BaseModel):
    email: str
    username: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    is_admin: bool
    created_at: datetime
    profile_picture: Optional[str] = None

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class CourseBase(BaseModel):
    title: str
    description: str

class CourseCreate(CourseBase):
    price: float
    duration_minutes: int

class Course(CourseBase):
    id: int
    price: float
    duration_minutes: int
    cover_image: str
    uploaded_by: int
    created_at: datetime
    likes_count: int = 0
    dislikes_count: int = 0
    user_reaction: Optional[bool] = None  # True para like, False para dislike, None para nenhum
    liked: bool = False  # Indica se o usuário atual deu like no curso

    class Config:
        from_attributes = True

class CourseDownloadCreate(BaseModel):
    course_id: int

class CourseDownload(CourseDownloadCreate):
    id: int
    user_id: int
    downloaded_at: datetime

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

class WalletBase(BaseModel):
    balance: float

class Wallet(WalletBase):
    id: int
    user_id: int

    class Config:
        from_attributes = True

class WalletTransactionBase(BaseModel):
    amount: float
    transaction_type: str

class WalletTransaction(WalletTransactionBase):
    id: int
    wallet_id: int
    payment_ref: Optional[str]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class DepositInitialize(BaseModel):
    mobile: str
    amount: str

class UserProfile(BaseModel):
    email: str
    username: str
    profile_picture: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class UserProfileUpdate(BaseModel):
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None