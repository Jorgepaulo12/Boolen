import httpx
from fastapi import HTTPException
import schemas
from typing import Dict

class PaychanguClient:
    def __init__(self):
        self.base_url = "https://api.paychangu.com"
        self.secret_key = "SEC-TEST-TXufbColCgWYrhZPvABr1jIK6djgMFB7"  # Sua chave secreta
        self.headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "accept": "application/json",
            "content-type": "application/json"
        }

    async def initialize_payment(self, payment: schemas.PaymentInitialize) -> Dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/mobile-money/payments/initialize",
                headers=self.headers,
                json={
                    "mobile_money_operator_ref_id": "20be6c20-adeb-4b5b-a7ba-0769820df4fb",
                    "mobile": payment.mobile,
                    "amount": payment.amount,
                    "charge_id": payment.charge_id
                }
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=400,
                    detail=f"Payment initialization failed: {response.text}"
                )
            
            return response.json()

    async def verify_payment_status(self, payment_ref: str) -> Dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/mobile-money/payments/{payment_ref}/status",
                headers=self.headers
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=400,
                    detail=f"Payment verification failed: {response.text}"
                )
            
            return response.json()

paychangu = PaychanguClient() 