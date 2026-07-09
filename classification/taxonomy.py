"""Baseline account taxonomy and merge helpers."""

from __future__ import annotations

from classification.schemas import ClientTaxonomy, ProductType, ProductTypeRule

ACCOUNT_TYPE_LIST = (
    "credit_card, retail_installments, fintech, student_loan, lending_point, "
    "auto_deficiency, other, or unknown if none match"
)

DEFAULT_ACCOUNT_TYPES: list[ProductTypeRule] = [
    ProductTypeRule(
        product_type=ProductType.credit_card,
        definition="Revolving consumer credit card accounts",
        keywords=["credit card", "APR", "minimum payment", "cardmember", "credit limit", "store card"],
        issuer_patterns=[],
        example_descriptions=["Monthly credit card statement"],
    ),
    ProductTypeRule(
        product_type=ProductType.retail_installments,
        definition="Retail or merchant installment plans, including store financing and BNPL-style checkout plans",
        keywords=[
            "retail installment",
            "installment plan",
            "buy now pay later",
            "BNPL",
            "Affirm",
            "Klarna",
            "Afterpay",
            "pay in 4",
            "store financing",
        ],
        issuer_patterns=[],
        example_descriptions=["Retail installment contract", "BNPL payment schedule"],
    ),
    ProductTypeRule(
        product_type=ProductType.fintech,
        definition="Online / marketplace personal loans and other fintech-originated unsecured credit (excluding LendingPoint)",
        keywords=[
            "personal loan",
            "fintech",
            "online loan",
            "marketplace lending",
            "unsecured loan",
            "signature loan",
        ],
        issuer_patterns=["LendingClub", "Prosper", "Upstart"],
        example_descriptions=["Fintech personal loan statement"],
    ),
    ProductTypeRule(
        product_type=ProductType.student_loan,
        definition="Federal and private education debt",
        keywords=["student loan", "education loan", "deferment", "forbearance", "Navient"],
        issuer_patterns=[],
        example_descriptions=["Student loan servicer notice"],
    ),
    ProductTypeRule(
        product_type=ProductType.lending_point,
        definition="Accounts originated or branded as LendingPoint",
        keywords=["LendingPoint", "Lending Point"],
        issuer_patterns=["LendingPoint"],
        example_descriptions=["LendingPoint account statement"],
    ),
    ProductTypeRule(
        product_type=ProductType.auto_deficiency,
        definition="Auto loan deficiency balances after repossession or sale of collateral",
        keywords=[
            "auto deficiency",
            "deficiency balance",
            "repossession",
            "repo",
            "vehicle deficiency",
            "auto loan",
            "VIN",
            "motor vehicle",
        ],
        issuer_patterns=[],
        example_descriptions=["Auto deficiency notice", "Post-repossession balance letter"],
    ),
    ProductTypeRule(
        product_type=ProductType.other,
        definition="Accounts that do not fit the named firm archetypes",
        keywords=[],
        issuer_patterns=[],
        example_descriptions=["Miscellaneous consumer debt"],
    ),
]


def baseline_taxonomy(client_id: str = "baseline") -> ClientTaxonomy:
    return ClientTaxonomy(
        client_id=client_id,
        product_types=list(DEFAULT_ACCOUNT_TYPES),
        rules=[
            "Use document evidence to match one account archetype from the taxonomy.",
            "Prefer lending_point when LendingPoint is named as issuer/originator.",
            "Prefer auto_deficiency over generic auto language when repossession or deficiency is present.",
        ],
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
        if rule.product_type in {ProductType.unknown}:
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
