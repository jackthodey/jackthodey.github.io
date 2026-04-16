# =============================================================================
# DATA QUALITY ASSESSMENT TOOL – REFERENCE DATA STANDARDS
# =============================================================================
# Each standard defines a regex pattern (and/or custom check) that values in a
# mapped column must satisfy to be counted as "valid".
# Users map their CSV columns to these standards in the UI.
# Reference: ISO 8000, RFC standards, national format authorities.
# =============================================================================

import re

# Boolean values accepted as valid for the "boolean" standard
_BOOLEAN_VALUES = {"true", "false", "yes", "no", "1", "0", "t", "f", "y", "n"}

# ISO 3166-1 Alpha-2 reference set (selected; full list can replace this)
_ISO2_COUNTRIES = {
    "AF","AX","AL","DZ","AS","AD","AO","AI","AQ","AG","AR","AM","AW","AU","AT",
    "AZ","BS","BH","BD","BB","BY","BE","BZ","BJ","BM","BT","BO","BQ","BA","BW",
    "BV","BR","IO","BN","BG","BF","BI","CV","KH","CM","CA","KY","CF","TD","CL",
    "CN","CX","CC","CO","KM","CG","CD","CK","CR","CI","HR","CU","CW","CY","CZ",
    "DK","DJ","DM","DO","EC","EG","SV","GQ","ER","EE","SZ","ET","FK","FO","FJ",
    "FI","FR","GF","PF","TF","GA","GM","GE","DE","GH","GI","GR","GL","GD","GP",
    "GU","GT","GG","GN","GW","GY","HT","HM","VA","HN","HK","HU","IS","IN","ID",
    "IR","IQ","IE","IM","IL","IT","JM","JP","JE","JO","KZ","KE","KI","KP","KR",
    "KW","KG","LA","LV","LB","LS","LR","LY","LI","LT","LU","MO","MG","MW","MY",
    "MV","ML","MT","MH","MQ","MR","MU","YT","MX","FM","MD","MC","MN","ME","MS",
    "MA","MZ","MM","NA","NR","NP","NL","NC","NZ","NI","NE","NG","NU","NF","MK",
    "MP","NO","OM","PK","PW","PS","PA","PG","PY","PE","PH","PN","PL","PT","PR",
    "QA","RE","RO","RU","RW","BL","SH","KN","LC","MF","PM","VC","WS","SM","ST",
    "SA","SN","RS","SC","SL","SG","SX","SK","SI","SB","SO","ZA","GS","SS","ES",
    "LK","SD","SR","SJ","SE","CH","SY","TW","TJ","TZ","TH","TL","TG","TK","TO",
    "TT","TN","TR","TM","TC","TV","UG","UA","AE","GB","US","UM","UY","UZ","VU",
    "VE","VN","VG","VI","WF","EH","YE","ZM","ZW",
}

DATA_STANDARDS = {

    # ── Contact / Communication ───────────────────────────────────────────────
    "email": {
        "name": "Email Address",
        "category": "Contact",
        "description": "Valid email address (RFC 5322 simplified)",
        "example": "user@example.com",
        "pattern": r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$",
    },
    "uk_phone": {
        "name": "UK Phone Number",
        "category": "Contact",
        "description": "UK landline or mobile number (with or without +44)",
        "example": "07911123456 or +447911123456",
        "pattern": r"^(\+44\s?|0)[1-9](\s?\d){8,9}$",
    },
    "intl_phone": {
        "name": "International Phone (E.164)",
        "category": "Contact",
        "description": "International format per ITU-T E.164",
        "example": "+12025551234",
        "pattern": r"^\+[1-9]\d{6,14}$",
    },
    "url": {
        "name": "URL",
        "category": "Contact",
        "description": "Valid HTTP or HTTPS web address",
        "example": "https://www.example.com/path",
        "pattern": r"^https?://[^\s/$.?#].[^\s]*$",
    },

    # ── Dates & Times ─────────────────────────────────────────────────────────
    "date_iso": {
        "name": "Date – ISO 8601 (YYYY-MM-DD)",
        "category": "Date & Time",
        "description": "Calendar date in international standard format",
        "example": "2024-01-31",
        "pattern": r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$",
        "is_date": True,
    },
    "date_uk": {
        "name": "Date – UK (DD/MM/YYYY)",
        "category": "Date & Time",
        "description": "Calendar date in British format",
        "example": "31/01/2024",
        "pattern": r"^(0[1-9]|[12]\d|3[01])/(0[1-9]|1[0-2])/\d{4}$",
        "is_date": True,
        "date_format": "%d/%m/%Y",
    },
    "date_us": {
        "name": "Date – US (MM/DD/YYYY)",
        "category": "Date & Time",
        "description": "Calendar date in US format",
        "example": "01/31/2024",
        "pattern": r"^(0[1-9]|1[0-2])/(0[1-9]|[12]\d|3[01])/\d{4}$",
        "is_date": True,
        "date_format": "%m/%d/%Y",
    },
    "datetime_iso": {
        "name": "DateTime – ISO 8601",
        "category": "Date & Time",
        "description": "Date and time in ISO 8601 format",
        "example": "2024-01-31T14:30:00",
        "pattern": r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])[T ]([01]\d|2[0-3]):[0-5]\d:[0-5]\d",
        "is_date": True,
        "date_format": "%Y-%m-%dT%H:%M:%S",
    },

    # ── Numeric ───────────────────────────────────────────────────────────────
    "integer": {
        "name": "Integer",
        "category": "Numeric",
        "description": "Whole number (positive, negative, or zero)",
        "example": "42, -7, 0",
        "pattern": r"^-?\d+$",
    },
    "positive_integer": {
        "name": "Positive Integer",
        "category": "Numeric",
        "description": "Whole positive number greater than zero",
        "example": "1, 42, 10000",
        "pattern": r"^[1-9]\d*$",
    },
    "decimal": {
        "name": "Decimal Number",
        "category": "Numeric",
        "description": "Numeric value with optional decimal places",
        "example": "3.14, -2.5, 100",
        "pattern": r"^-?\d+(\.\d+)?$",
    },
    "percentage": {
        "name": "Percentage (0–100)",
        "category": "Numeric",
        "description": "Numeric value between 0 and 100 (inclusive)",
        "example": "0, 50.5, 100",
        "custom_check": "percentage",
    },
    "currency": {
        "name": "Currency Amount",
        "category": "Numeric",
        "description": "Monetary value (numeric, no currency symbol, max 2 d.p.)",
        "example": "9.99, 1250.00, 0.50",
        "pattern": r"^\d+(\.\d{1,2})?$",
    },

    # ── Geographic ────────────────────────────────────────────────────────────
    "uk_postcode": {
        "name": "UK Postcode",
        "category": "Geographic",
        "description": "Royal Mail UK postcode format",
        "example": "SW1A 2AA, M1 1AE, EC1A 1BB",
        "pattern": r"^[A-Z]{1,2}[0-9][0-9A-Z]?\s?[0-9][A-Z]{2}$",
        "flags": re.IGNORECASE,
    },
    "us_zipcode": {
        "name": "US ZIP Code",
        "category": "Geographic",
        "description": "5-digit ZIP or ZIP+4 format",
        "example": "90210, 90210-1234",
        "pattern": r"^\d{5}(-\d{4})?$",
    },
    "iso2_country": {
        "name": "Country Code – ISO 3166-1 Alpha-2",
        "category": "Geographic",
        "description": "Two-letter ISO country code (uppercase)",
        "example": "GB, US, DE, FR",
        "custom_check": "iso2_country",
    },
    "iso3_country": {
        "name": "Country Code – ISO 3166-1 Alpha-3",
        "category": "Geographic",
        "description": "Three-letter ISO country code (uppercase)",
        "example": "GBR, USA, DEU, FRA",
        "pattern": r"^[A-Z]{3}$",
    },
    "latitude": {
        "name": "Latitude (decimal degrees)",
        "category": "Geographic",
        "description": "WGS-84 latitude: -90 to +90",
        "example": "51.5074, -33.8688",
        "custom_check": "latitude",
    },
    "longitude": {
        "name": "Longitude (decimal degrees)",
        "category": "Geographic",
        "description": "WGS-84 longitude: -180 to +180",
        "example": "-0.1278, 151.2093",
        "custom_check": "longitude",
    },

    # ── Identifiers ───────────────────────────────────────────────────────────
    "uuid": {
        "name": "UUID (v1–v5)",
        "category": "Identifier",
        "description": "Universally Unique Identifier in standard hyphenated format",
        "example": "550e8400-e29b-41d4-a716-446655440000",
        "pattern": r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        "flags": re.IGNORECASE,
    },
    "ipv4": {
        "name": "IPv4 Address",
        "category": "Identifier",
        "description": "Valid dotted-decimal IPv4 address",
        "example": "192.168.1.1, 10.0.0.1",
        "pattern": r"^((25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(25[0-5]|2[0-4]\d|[01]?\d\d?)$",
    },

    # ── Finance & Banking ─────────────────────────────────────────────────────
    "iban": {
        "name": "IBAN",
        "category": "Finance",
        "description": "International Bank Account Number (ISO 13616)",
        "example": "GB29NWBK60161331926819",
        "pattern": r"^[A-Z]{2}[0-9]{2}[A-Z0-9]{4}[0-9]{7}([A-Z0-9]?){0,16}$",
    },
    "uk_sort_code": {
        "name": "UK Sort Code",
        "category": "Finance",
        "description": "UK bank sort code (hyphenated or 6-digit)",
        "example": "12-34-56 or 123456",
        "pattern": r"^(\d{2}-\d{2}-\d{2}|\d{6})$",
    },

    # ── UK Government / Regulatory ────────────────────────────────────────────
    "uk_ni_number": {
        "name": "UK National Insurance Number",
        "category": "UK Regulatory",
        "description": "HMRC NI Number format (AB123456C)",
        "example": "AB123456C",
        "pattern": r"^[A-CEGHJ-PR-TW-Z]{1}[A-CEGHJ-NPR-TW-Z]{1}[0-9]{6}[A-D]?$",
        "flags": re.IGNORECASE,
    },
    "uk_company_number": {
        "name": "UK Companies House Number",
        "category": "UK Regulatory",
        "description": "8-digit Companies House registration number",
        "example": "00000006, SC123456",
        "pattern": r"^(([A-Z]{2}|[0-9]{2})[0-9]{6})$",
        "flags": re.IGNORECASE,
    },
    "uk_vat_number": {
        "name": "UK VAT Registration Number",
        "category": "UK Regulatory",
        "description": "HMRC VAT number (GB + 9 digits)",
        "example": "GB123456789",
        "pattern": r"^GB[0-9]{9}$",
        "flags": re.IGNORECASE,
    },

    # ── Categorical / Boolean ─────────────────────────────────────────────────
    "boolean": {
        "name": "Boolean",
        "category": "Categorical",
        "description": "True/False, Yes/No, 1/0, T/F, Y/N (case-insensitive)",
        "example": "True, False, Yes, No, 1, 0",
        "custom_check": "boolean",
    },
    "gender": {
        "name": "Gender (inclusive vocabulary)",
        "category": "Categorical",
        "description": "Standardised gender values per UK government guidance",
        "example": "Male, Female, Non-binary, Prefer not to say",
        "custom_check": "gender",
    },

    # ── Text ──────────────────────────────────────────────────────────────────
    "alpha_only": {
        "name": "Alphabetic Text Only",
        "category": "Text",
        "description": "Contains only alphabetic characters and spaces (no digits or symbols)",
        "example": "John Smith, New York",
        "pattern": r"^[A-Za-z\s\-'\.]+$",
    },
    "alphanumeric": {
        "name": "Alphanumeric",
        "category": "Text",
        "description": "Contains only letters, digits, and common word separators",
        "example": "ABC123, order-456",
        "pattern": r"^[A-Za-z0-9\s\-_]+$",
    },
}

# ── Gender reference values ───────────────────────────────────────────────────
_GENDER_VALUES = {
    "male", "female", "non-binary", "nonbinary", "non binary",
    "prefer not to say", "prefer not to disclose", "other",
    "m", "f", "nb", "x", "unknown",
}

# ── Check function ─────────────────────────────────────────────────────────────

def check_value(value, standard_id: str) -> bool:
    """Return True if *value* conforms to the named data standard."""
    if value is None:
        return False
    str_val = str(value).strip()
    if str_val == "" or str_val.lower() in ("nan", "none", "null", "na", "n/a"):
        return False  # nulls are handled by completeness; don't double-penalise

    std = DATA_STANDARDS.get(standard_id)
    if not std:
        return True   # unknown standard – don't penalise

    cc = std.get("custom_check")

    if cc == "boolean":
        return str_val.lower() in _BOOLEAN_VALUES

    if cc == "percentage":
        try:
            return 0.0 <= float(str_val) <= 100.0
        except (ValueError, TypeError):
            return False

    if cc == "iso2_country":
        return str_val.upper() in _ISO2_COUNTRIES

    if cc == "latitude":
        try:
            return -90.0 <= float(str_val) <= 90.0
        except (ValueError, TypeError):
            return False

    if cc == "longitude":
        try:
            return -180.0 <= float(str_val) <= 180.0
        except (ValueError, TypeError):
            return False

    if cc == "gender":
        return str_val.lower() in _GENDER_VALUES

    pattern = std.get("pattern")
    if pattern:
        flags = std.get("flags", 0)
        return bool(re.match(pattern, str_val, flags))

    return True
