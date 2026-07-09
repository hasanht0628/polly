from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ProductType(str, Enum):
    """Firm account archetypes used for portfolio classification."""

    credit_card = "credit_card"
    retail_installments = "retail_installments"
    fintech = "fintech"
    student_loan = "student_loan"
    lending_point = "lending_point"
    auto_deficiency = "auto_deficiency"
    other = "other"
    unknown = "unknown"


# Alias for callers that prefer the firm vocabulary.
AccountArchetype = ProductType


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
