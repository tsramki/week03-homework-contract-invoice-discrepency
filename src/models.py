"""Pydantic schemas shared across the CrewAI extraction and analysis tasks."""

from typing import List, Optional

from pydantic import BaseModel, Field


class ContractItem(BaseModel):
    name: str = Field(description="Name of the good/service as written in the contract")
    unit_price: float = Field(description="Contracted price per unit, in USD")


class ContractData(BaseModel):
    vendor: str
    referenced_invoice_number: Optional[str] = Field(
        default=None, description="Invoice number the contract references, if any"
    )
    payment_terms: Optional[str] = Field(default=None, description="e.g. 'Net 14 days'")
    payment_method: Optional[str] = None
    items: List[ContractItem] = Field(default_factory=list)


class InvoiceLineItem(BaseModel):
    description: str
    quantity: float
    unit_price: float
    amount: float


class InvoiceData(BaseModel):
    invoice_number: str
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    vendor: str
    bill_to: Optional[str] = None
    payment_terms: Optional[str] = None
    payment_method: Optional[str] = None
    line_items: List[InvoiceLineItem] = Field(default_factory=list)
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    total_due: Optional[float] = None
