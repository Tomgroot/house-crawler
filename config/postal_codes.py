POSTCODE_TO_NEIGHBORHOOD: dict[str, str] = {
    # Binnenstad (Centrum)
    "3511": "Binnenstad",
    "3512": "Binnenstad",
    "3513": "Binnenstad",
    "3514": "Binnenstad",
    "3515": "Binnenstad",
    "3516": "Binnenstad",
    # Lombok / Transwijk
    "3531": "Lombok",
    "3532": "Lombok",
    "3533": "Lombok",
    # Wittevrouwen / Oudwijk
    "3581": "Wittevrouwen/Oudwijk",
    "3582": "Wittevrouwen/Oudwijk",
    "3583": "Wittevrouwen/Oudwijk",
    "3584": "Wittevrouwen/Oudwijk",
    # Rivierenwijk / Dichterswijk
    "3522": "Rivierenwijk/Dichterswijk",
    "3523": "Rivierenwijk/Dichterswijk",
    # Tuinwijk
    "3521": "Tuinwijk",
    # Hoograven
    "3525": "Hoograven",
    "3528": "Hoograven",
    # Abstede
    "3555": "Abstede",
    "3556": "Abstede",
    # Kanaleneiland
    "3526": "Kanaleneiland",
    "3527": "Kanaleneiland",
    # Zuilen / Ondiep
    "3551": "Zuilen/Ondiep",
    "3552": "Zuilen/Ondiep",
    "3553": "Zuilen/Ondiep",
    # Overvecht
    "3562": "Overvecht",
    "3563": "Overvecht",
    "3564": "Overvecht",
    # Leidsche Rijn
    "3543": "Leidsche Rijn",
    "3544": "Leidsche Rijn",
    "3545": "Leidsche Rijn",
    "3546": "Leidsche Rijn",
    # Vleuten-De Meern
    "3451": "Vleuten-De Meern",
    "3452": "Vleuten-De Meern",
    "3453": "Vleuten-De Meern",
    "3454": "Vleuten-De Meern",
}


def resolve_neighborhood(postal_code: str) -> str | None:
    """Return neighborhood name for a Dutch postcode (first 4 digits)."""
    key = postal_code.strip()[:4]
    return POSTCODE_TO_NEIGHBORHOOD.get(key)
