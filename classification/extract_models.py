"""Loose LLM output for classification profiles."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExtractedProductTypeRule(BaseModel):
    product_type: str = ""
    definition: str = ""
    keywords: list[str] = Field(default_factory=list)
    issuer_patterns: list[str] = Field(default_factory=list)
    example_descriptions: list[str] = Field(default_factory=list)


class ExtractedFieldDefinition(BaseModel):
    name: str
    description: str = ""
    data_classification: str | None = None


class ExtractedClientTaxonomy(BaseModel):
    product_types: list[ExtractedProductTypeRule] = Field(default_factory=list)
    field_definitions: list[ExtractedFieldDefinition] = Field(default_factory=list)
    rules: list[str] = Field(default_factory=list)
    extraction_notes: list[str] = Field(default_factory=list)


class ExtractedManualCitation(BaseModel):
    section: str = ""
    rule_text: str = ""


class ExtractedProductClassification(BaseModel):
    product_type: str = "unknown"
    confidence: str = "low"
    evidence_quotes: list[str] = Field(default_factory=list)
    manual_citations: list[ExtractedManualCitation] = Field(default_factory=list)
    needs_review: bool = True
    alternative_types: list[str] = Field(default_factory=list)
    extraction_notes: list[str] = Field(default_factory=list)
