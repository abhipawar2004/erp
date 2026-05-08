from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import datetime
from typing import Optional, List


class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, description="Product name")
    description: Optional[str] = Field(None, description="Product description")
    price: Decimal = Field(..., ge=0, description="Product price (non-negative)")
    stock: int = Field(default=0, ge=0, description="Product stock (non-negative)")

 
class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, description="Product name")
    description: Optional[str] = Field(None, description="Product description")
    price: Optional[Decimal] = Field(None, ge=0, description="Product price (non-negative)")
    stock: Optional[int] = Field(None, ge=0, description="Product stock (non-negative)")


class ProductResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    price: Decimal
    stock: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Order Item Schemas
class OrderItemCreate(BaseModel):
    product_id: int = Field(..., gt=0, description="Product ID")
    quantity: int = Field(..., gt=0, description="Quantity (must be greater than 0)")


class OrderItemResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    price: Decimal

    class Config:
        from_attributes = True


# Order Schemas
class OrderCreate(BaseModel):
    order_items: List[OrderItemCreate] = Field(..., min_items=1, description="List of order items")


class OrderStatusUpdate(BaseModel):
    status: str = Field(..., description="Order status (PENDING, COMPLETED, CANCELLED)")


class OrderResponse(BaseModel):
    id: int
    status: str
    total_amount: Decimal
    order_items: List[OrderItemResponse]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
