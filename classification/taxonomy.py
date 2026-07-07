"""Baseline account taxonomy and merge helpers."""

from __future__ import annotations

from classification.schemas import ClientTaxonomy, ProductType, ProductTypeRule

ACCOUNT_TYPE_LIST = (
    "credit_card, personal_loan, auto_loan, student_loan, mortgage, heloc, "
    "medical_bill, bnpl, telecom, or unknown if none match"
)

DEFAULT_ACCOUNT_TYPES: list[ProductTypeRule] = [
    ProductTypeRule(
        product_type=ProductType.credit_card,
        definition="Revolving consumer credit card accounts",
        keywords=["credit card", "APR", "minimum payment", "cardmember", "credit limit"],
        issuer_patterns=[],
        example_descriptions=["Monthly credit card statement"],
    ),
    ProductTypeRule(
        product_type=ProductType.personal_loan,
        definition="Unsecured or general-purpose installment loans",
        keywords=["personal loan", "installment loan", "unsecured loan", "signature loan"],
        issuer_patterns=[],
        example_descriptions=["Personal loan billing statement"],
    ),
    ProductTypeRule(
        product_type=ProductType.auto_loan,
        definition="Vehicle-secured installment loans",
        keywords=["auto loan", "vehicle loan", "VIN", "motor vehicle", "car loan"],
        issuer_patterns=[],
        example_descriptions=["Auto finance statement"],
    ),
    ProductTypeRule(
        product_type=ProductType.student_loan,
        definition="Federal and private education debt",
        keywords=["student loan", "education loan", "deferment", "forbearance", "Navient"],
        issuer_patterns=[],
        example_descriptions=["Student loan servicer notice"],
    ),
    ProductTypeRule(
        product_type=ProductType.mortgage,
        definition="First-lien home mortgage loans",
        keywords=[
            "mortgage",
            "principal balance",
            "escrow",
            "deed of trust",
            "home loan",
            "property address",
        ],
        issuer_patterns=[],
        example_descriptions=["Mortgage loan statement"],
    ),
    ProductTypeRule(
        product_type=ProductType.heloc,
        definition="Home equity line of credit",
        keywords=[
            "HELOC",
            "home equity line",
            "line of credit",
            "draw period",
            "revolving line",
        ],
        issuer_patterns=[],
        example_descriptions=["HELOC statement"],
    ),
    ProductTypeRule(
        product_type=ProductType.medical_bill,
        definition="Healthcare provider or hospital billing",
        keywords=[
            "medical bill",
            "hospital",
            "patient",
            "provider",
            "CPT",
            "diagnosis",
            "physician",
        ],
        issuer_patterns=[],
        example_descriptions=["Hospital or clinic billing statement"],
    ),
    ProductTypeRule(
        product_type=ProductType.bnpl,
        definition="Buy now, pay later installment plans",
        keywords=[
            "buy now pay later",
            "BNPL",
            "Affirm",
            "Klarna",
            "Afterpay",
            "pay in 4",
            "installment plan",
        ],
        issuer_patterns=[],
        example_descriptions=["BNPL payment schedule"],
    ),
    ProductTypeRule(
        product_type=ProductType.telecom,
        definition="Wireless, cable, or telecom service accounts",
        keywords=[
            "wireless",
            "mobile",
            "data plan",
            "carrier",
            "telecom",
            "phone bill",
            "minutes",
        ],
        issuer_patterns=[],
        example_descriptions=["Wireless or cable bill"],
    ),
]


def baseline_taxonomy(client_id: str = "baseline") -> ClientTaxonomy:
    return ClientTaxonomy(
        client_id=client_id,
        product_types=list(DEFAULT_ACCOUNT_TYPES),
        rules=["Use document evidence to match one account type from the taxonomy."],
        version="baseline",
    )


def merge_taxonomies(client: ClientTaxonomy | None) -> ClientTaxonomy:
    """Client rules override/augment baseline rules by product_type."""
    base = baseline_taxonomy(client_id=client.client_id if client else "baseline")
    if client is None:
        return base

    by_type: dict[ProductType, ProductTypeRule] = {
        rule.product_type: rule.model_copy(deep=True) for rule in base.product_types
    }
    for rule in client.product_types:
        if rule.product_type == ProductType.unknown:
            continue
        existing = by_type.get(rule.product_type)
        if existing is None:
            by_type[rule.product_type] = rule.model_copy(deep=True)
            continue
        by_type[rule.product_type] = ProductTypeRule(
            product_type=rule.product_type,
            definition=rule.definition or existing.definition,
            keywords=_merge_unique(existing.keywords, rule.keywords),
            issuer_patterns=_merge_unique(existing.issuer_patterns, rule.issuer_patterns),
            example_descriptions=_merge_unique(
                existing.example_descriptions, rule.example_descriptions
            ),
        )

    merged_rules = list(base.rules)
    for rule in client.rules:
        if rule not in merged_rules:
            merged_rules.append(rule)

    return ClientTaxonomy(
        client_id=client.client_id,
        product_types=list(by_type.values()),
        field_definitions=list(client.field_definitions),
        rules=merged_rules,
        version=client.version,
        source_manual_path=client.source_manual_path,
    )


def _merge_unique(base: list[str], extra: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for item in base + extra:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged
