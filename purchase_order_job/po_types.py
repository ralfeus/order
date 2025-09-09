from datetime import date
import logging
from typing import List, Tuple, Optional
from pydantic import BaseModel

class Config(BaseModel):
    ATOMY_RECEIVER_NAME_FORMAT: str = "{company} {id1}"
    BROWSER_URL: Optional[str] = None
    DEBUG_SCREENSHOTS: bool = False
    FREE_LOCAL_SHIPPING_AMOUNT_THRESHOLD: int = 50000
    LOG_LEVEL: int = logging.INFO

class Customer(BaseModel):
    username: str
    password: str

class OrderProduct(BaseModel):
    product_id: str
    quantity: int
    price: int
    separate_shipping: bool
    purchase: bool

class Address(BaseModel):
    name: str
    address_1: str
    address_2: str

    def to_dict(self):
        return {
            "name": self.name,
            "address_1": self.address_1,
            "address_2": self.address_2,
        }

class Company(BaseModel):
    name: Optional[str] = None
    tax_id: Tuple[str, str, str] = ("", "", "")
    contact_person: Optional[str] = None
    address: Optional[Address] = None
    business_type: Optional[str] = None
    business_category: Optional[str] = None
    tax_phone: Optional[str] = None
    email: Optional[str] = None
    bank_id: str
    tax_simplified: Optional[bool] = None

class PurchaseOrder(BaseModel):
    id: str
    purchase_date: Optional[date] = None
    customer: Customer
    contact_phone: str
    company: Company
    order_products: List[OrderProduct]
    address: Address
    phone: str
    vendor_po_id: Optional[str] = None
    payment_account: Optional[str] = None
    total_krw: Optional[int] = None
    payment_phone: str
