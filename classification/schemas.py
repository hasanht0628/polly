from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ProductType(str, Enum):
    credit_card = "credit_card"
    personal_loan = "personal_loan"
    auto_loan = "auto_loan"
    student_loan = "student_loan"
    mortgage = "mortgage"
    heloc = "heloc"
    medical_bill = "medical_bill"
    bnpl = "bnpl"
    telecom = "telecom"
    unknown = "unknown"


class ProductTypeRule(BaseModel):
    product_type: ProductType
    definition: str = ""
    keywords: list[str] = Field(default_factory=list)
    issuer_patterns: list[str] = Field(default_factory=list)
    example_descriptions: list[str] = Field(default_factory=list)


class FieldDefinition(BaseModel):
    name: str
    description: str = ""
    data_classification: str | None = None


class ClientTaxonomy(BaseModel):
    client_id: str
    product_types: list[ProductTypeRule] = Field(default_factory=list)
    field_definitions: list[FieldDefinition] = Field(default_factory=list)
    rules: list[str] = Field(default_factory=list)
    version: str = "1"
    source_manual_path: str | None = None


class ManualCitation(BaseModel):
    section: str = ""
    rule_text: str = ""


class ProductClassification(BaseModel):
    client_id: str
    product_type: ProductType = ProductType.unknown
    confidence: str = Field(
        default="low",
        description="high, medium, or low",
    )
    evidence_quotes: list[str] = Field(default_factory=list)
    manual_citations: list[ManualCitation] = Field(default_factory=list)
    needs_review: bool = True
    alternative_types: list[ProductType] = Field(default_factory=list)
