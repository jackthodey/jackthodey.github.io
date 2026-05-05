# =============================================================================
# DATA QUALITY ASSESSMENT TOOL – REFERENCE DATA STANDARDS
# =============================================================================
# This file defines every data standard that a user can map to a CSV column.
# Each standard describes the expected format of values in that column.
# When a user maps a column to a standard, every non-null value is tested
# against that standard's pattern or custom check.
# The proportion of passing values is the column's validity score.
#
# Two validation approaches are used:
#   1. "pattern"      – a compiled regex; the value must match the full pattern.
#   2. "custom_check" – a named code path in check_value() for logic that
#                       cannot be expressed as a simple regex (e.g. range checks,
#                       set membership lookups).
#
# Reference: ISO 8000, RFC standards, national format authorities.
# =============================================================================

import re  # Python standard library regex module — used to compile and match patterns in check_value()

# ── Pre-built reference sets ──────────────────────────────────────────────────
# These sets are used by custom_check paths in check_value() for O(1) lookup.

# All string representations that are accepted as a valid Boolean value.
# Lower-cased before comparison so the check is case-insensitive.
_BOOLEAN_VALUES = {"true", "false", "yes", "no", "1", "0", "t", "f", "y", "n"}

# ISO 3166-1 Alpha-2 two-letter country codes (uppercase).
# A Python set is used instead of a list for O(1) membership testing.
# The full UN-recognised set of 249 territories is included here.
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

# ── DATA_STANDARDS dictionary ─────────────────────────────────────────────────
# Each key is a short identifier (standard_id) the user picks in the column
# mapping UI.  The value is a metadata dict with these fields:
#
#   name          – human-readable name shown in the dropdown and report
#   category      – grouping label (used to build <optgroup> in the UI)
#   description   – tooltip text describing what format is expected
#   example       – one or more example values shown in the tooltip
#   pattern       – Python regex string; must match the ENTIRE value (via re.match)
#   flags         – optional re flags (e.g. re.IGNORECASE) applied to the pattern
#   is_date       – if True, _check_timeliness() will treat this column as a date column
#   date_format   – strptime format string (informational; used by some date tools)
#   custom_check  – string key directing check_value() to a specialised code path
#                   instead of a regex match
DATA_STANDARDS = {

    # ── Contact / Communication ───────────────────────────────────────────────

    "email": {
        "name": "Email Address",
        "category": "Contact",
        "description": "Valid email address (RFC 5322 simplified)",
        "example": "user@example.com",
        # Pattern breakdown:
        #   ^[a-zA-Z0-9._%+\-]+  – local part: letters, digits, dots, %, +, -
        #   @                     – literal @ separator
        #   [a-zA-Z0-9.\-]+       – domain name: letters, digits, dots, hyphens
        #   \.                    – literal dot before TLD
        #   [a-zA-Z]{2,}$         – TLD: at least 2 letters (e.g. "com", "co.uk")
        "pattern": r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$",
    },
    "uk_phone": {
        "name": "UK Phone Number",
        "category": "Contact",
        "description": "UK landline or mobile number (with or without +44)",
        "example": "07911123456 or +447911123456",
        # Pattern breakdown:
        #   ^(\+44\s?|0)   – starts with +44 (optional space) OR leading 0
        #   [1-9]           – first significant digit (not 0)
        #   (\s?\d){8,9}$  – 8 or 9 more digits, each optionally preceded by a space
        "pattern": r"^(\+44\s?|0)[1-9](\s?\d){8,9}$",
    },
    "intl_phone": {
        "name": "International Phone (E.164)",
        "category": "Contact",
        "description": "International format per ITU-T E.164",
        "example": "+12025551234",
        # Pattern breakdown:
        #   ^\+         – must start with +
        #   [1-9]       – country code first digit (not 0)
        #   \d{6,14}$   – 6 to 14 more digits (total number length 7–15 per E.164)
        "pattern": r"^\+[1-9]\d{6,14}$",
    },
    "url": {
        "name": "URL",
        "category": "Contact",
        "description": "Valid HTTP or HTTPS web address",
        "example": "https://www.example.com/path",
        # Pattern breakdown:
        #   ^https?://          – http:// or https://
        #   [^\s/$.?#]          – first character of host: not whitespace, /, $, ., ?, #
        #   .[^\s]*$            – followed by any non-whitespace characters
        "pattern": r"^https?://[^\s/$.?#].[^\s]*$",
    },

    # ── Dates & Times ─────────────────────────────────────────────────────────

    "date_iso": {
        "name": "Date – ISO 8601 (YYYY-MM-DD)",
        "category": "Date & Time",
        "description": "Calendar date in international standard format",
        "example": "2024-01-31",
        # Pattern breakdown:
        #   ^\d{4}-          – 4-digit year, hyphen
        #   (0[1-9]|1[0-2])- – month 01–12, hyphen
        #   (0[1-9]|[12]\d|3[01])$ – day 01–31
        "pattern": r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$",
        "is_date": True,       # Flag so timeliness checker includes this column
    },
    "date_uk": {
        "name": "Date – UK (DD/MM/YYYY)",
        "category": "Date & Time",
        "description": "Calendar date in British format",
        "example": "31/01/2024",
        # Pattern breakdown:
        #   ^(0[1-9]|[12]\d|3[01])/  – day 01–31, slash
        #   (0[1-9]|1[0-2])/          – month 01–12, slash
        #   \d{4}$                     – 4-digit year
        "pattern": r"^(0[1-9]|[12]\d|3[01])/(0[1-9]|1[0-2])/\d{4}$",
        "is_date": True,
        "date_format": "%d/%m/%Y",   # strptime format for date parsing tools
    },
    "date_us": {
        "name": "Date – US (MM/DD/YYYY)",
        "category": "Date & Time",
        "description": "Calendar date in US format",
        "example": "01/31/2024",
        # Same structure as date_uk but month and day positions are swapped
        "pattern": r"^(0[1-9]|1[0-2])/(0[1-9]|[12]\d|3[01])/\d{4}$",
        "is_date": True,
        "date_format": "%m/%d/%Y",
    },
    "datetime_iso": {
        "name": "DateTime – ISO 8601",
        "category": "Date & Time",
        "description": "Date and time in ISO 8601 format",
        "example": "2024-01-31T14:30:00",
        # Pattern breakdown:
        #   ^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])  – date part (YYYY-MM-DD)
        #   [T ]                                              – separator: T or a space
        #   ([01]\d|2[0-3]):[0-5]\d:[0-5]\d                 – time HH:MM:SS (24-hour)
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
        # Pattern: optional leading minus, then one or more digits
        "pattern": r"^-?\d+$",
    },
    "positive_integer": {
        "name": "Positive Integer",
        "category": "Numeric",
        "description": "Whole positive number greater than zero",
        "example": "1, 42, 10000",
        # Pattern: starts with a non-zero digit, followed by any digits
        # This correctly rejects 0 because [1-9] does not match '0'
        "pattern": r"^[1-9]\d*$",
    },
    "decimal": {
        "name": "Decimal Number",
        "category": "Numeric",
        "description": "Numeric value with optional decimal places",
        "example": "3.14, -2.5, 100",
        # Pattern: optional minus, digits, optionally followed by a dot and more digits
        # The decimal part (\.\d+)? is optional — whole numbers are also valid
        "pattern": r"^-?\d+(\.\d+)?$",
    },
    "percentage": {
        "name": "Percentage (0–100)",
        "category": "Numeric",
        "description": "Numeric value between 0 and 100 (inclusive)",
        "example": "0, 50.5, 100",
        # A regex cannot enforce numeric range boundaries, so a custom_check is used.
        # check_value() handles "percentage" by converting to float and checking 0 ≤ x ≤ 100.
        "custom_check": "percentage",
    },
    "currency": {
        "name": "Currency Amount",
        "category": "Numeric",
        "description": "Monetary value (numeric, no currency symbol, max 2 d.p.)",
        "example": "9.99, 1250.00, 0.50",
        # Pattern: digits, optionally followed by a dot and 1 or 2 decimal places
        # No minus allowed (currency amounts expected to be non-negative here)
        # No currency symbol allowed (GBP, USD symbols should be stripped before storage)
        "pattern": r"^\d+(\.\d{1,2})?$",
    },

    # ── Geographic ────────────────────────────────────────────────────────────

    "uk_postcode": {
        "name": "UK Postcode",
        "category": "Geographic",
        "description": "Royal Mail UK postcode format",
        "example": "SW1A 2AA, M1 1AE, EC1A 1BB",
        # Pattern breakdown:
        #   ^[A-Z]{1,2}    – 1 or 2 letter area code (e.g. SW, M, EC)
        #   [0-9]          – district digit
        #   [0-9A-Z]?      – optional district sub-code (letter or digit)
        #   \s?            – optional space between outward and inward codes
        #   [0-9]          – sector digit
        #   [A-Z]{2}$      – 2-letter unit code
        # re.IGNORECASE flag allows lower-case input (e.g. "sw1a 2aa")
        "pattern": r"^[A-Z]{1,2}[0-9][0-9A-Z]?\s?[0-9][A-Z]{2}$",
        "flags": re.IGNORECASE,  # Accept upper and lower case
    },
    "us_zipcode": {
        "name": "US ZIP Code",
        "category": "Geographic",
        "description": "5-digit ZIP or ZIP+4 format",
        "example": "90210, 90210-1234",
        # Pattern: exactly 5 digits, optionally followed by a hyphen and 4 more digits
        "pattern": r"^\d{5}(-\d{4})?$",
    },
    "iso2_country": {
        "name": "Country Code – ISO 3166-1 Alpha-2",
        "category": "Geographic",
        "description": "Two-letter ISO country code (uppercase)",
        "example": "GB, US, DE, FR",
        # Regex cannot validate against a known-good set efficiently, so a custom_check
        # is used — check_value() looks up the uppercased value in _ISO2_COUNTRIES set.
        "custom_check": "iso2_country",
    },
    "iso3_country": {
        "name": "Country Code – ISO 3166-1 Alpha-3",
        "category": "Geographic",
        "description": "Three-letter ISO country code (uppercase)",
        "example": "GBR, USA, DEU, FRA",
        # Pattern: exactly 3 uppercase letters — structural check only (not against a set)
        "pattern": r"^[A-Z]{3}$",
    },
    "latitude": {
        "name": "Latitude (decimal degrees)",
        "category": "Geographic",
        "description": "WGS-84 latitude: -90 to +90",
        "example": "51.5074, -33.8688",
        # Range checking (-90 to +90) cannot be done with regex, so custom_check handles it
        "custom_check": "latitude",
    },
    "longitude": {
        "name": "Longitude (decimal degrees)",
        "category": "Geographic",
        "description": "WGS-84 longitude: -180 to +180",
        "example": "-0.1278, 151.2093",
        # Range checking (-180 to +180) cannot be done with regex, so custom_check handles it
        "custom_check": "longitude",
    },

    # ── Identifiers ───────────────────────────────────────────────────────────

    "uuid": {
        "name": "UUID (v1–v5)",
        "category": "Identifier",
        "description": "Universally Unique Identifier in standard hyphenated format",
        "example": "550e8400-e29b-41d4-a716-446655440000",
        # Pattern: 8-4-4-4-12 hex digits with hyphens, case-insensitive
        "pattern": r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        "flags": re.IGNORECASE,  # UUIDs may be stored in upper or lower case
    },
    "ipv4": {
        "name": "IPv4 Address",
        "category": "Identifier",
        "description": "Valid dotted-decimal IPv4 address",
        "example": "192.168.1.1, 10.0.0.1",
        # Pattern breakdown (four identical octet groups joined by dots):
        #   25[0-5]        – 250–255
        #   2[0-4]\d       – 200–249
        #   [01]?\d\d?     – 0–199 (optional leading 0 or 1)
        # Each group is separated by \. (literal dot)
        "pattern": r"^((25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(25[0-5]|2[0-4]\d|[01]?\d\d?)$",
    },

    # ── Finance & Banking ─────────────────────────────────────────────────────

    "iban": {
        "name": "IBAN",
        "category": "Finance",
        "description": "International Bank Account Number (ISO 13616)",
        "example": "GB29NWBK60161331926819",
        # Pattern breakdown:
        #   ^[A-Z]{2}       – 2-letter country code
        #   [0-9]{2}        – 2-digit check digits
        #   [A-Z0-9]{4}     – 4-character BBAN prefix
        #   [0-9]{7}        – minimum 7 digits
        #   ([A-Z0-9]?){0,16}$ – up to 16 more alphanumeric characters
        "pattern": r"^[A-Z]{2}[0-9]{2}[A-Z0-9]{4}[0-9]{7}([A-Z0-9]?){0,16}$",
    },
    "uk_sort_code": {
        "name": "UK Sort Code",
        "category": "Finance",
        "description": "UK bank sort code (hyphenated or 6-digit)",
        "example": "12-34-56 or 123456",
        # Pattern: either 2-2-2 hyphenated digits OR 6 plain digits (no hyphens)
        "pattern": r"^(\d{2}-\d{2}-\d{2}|\d{6})$",
    },

    # ── UK Government / Regulatory ────────────────────────────────────────────

    "uk_ni_number": {
        "name": "UK National Insurance Number",
        "category": "UK Regulatory",
        "description": "HMRC NI Number format (AB123456C)",
        "example": "AB123456C",
        # Pattern breakdown:
        #   ^[A-CEGHJ-PR-TW-Z]{1}  – first letter: excludes D, F, I, Q, U, V (invalid prefixes)
        #   [A-CEGHJ-NPR-TW-Z]{1}  – second letter: excludes D, F, I, O, Q, U, V
        #   [0-9]{6}                – 6 digits
        #   [A-D]?$                 – optional suffix letter A, B, C, or D
        "pattern": r"^[A-CEGHJ-PR-TW-Z]{1}[A-CEGHJ-NPR-TW-Z]{1}[0-9]{6}[A-D]?$",
        "flags": re.IGNORECASE,
    },
    "uk_company_number": {
        "name": "UK Companies House Number",
        "category": "UK Regulatory",
        "description": "8-digit Companies House registration number",
        "example": "00000006, SC123456",
        # Pattern: either 2 letters + 6 digits (e.g. SC123456) OR 2 digits + 6 digits
        "pattern": r"^(([A-Z]{2}|[0-9]{2})[0-9]{6})$",
        "flags": re.IGNORECASE,
    },
    "uk_vat_number": {
        "name": "UK VAT Registration Number",
        "category": "UK Regulatory",
        "description": "HMRC VAT number (GB + 9 digits)",
        "example": "GB123456789",
        # Pattern: literal "GB" (case-insensitive) followed by exactly 9 digits
        "pattern": r"^GB[0-9]{9}$",
        "flags": re.IGNORECASE,
    },

    # ── Categorical / Boolean ─────────────────────────────────────────────────

    "boolean": {
        "name": "Boolean",
        "category": "Categorical",
        "description": "True/False, Yes/No, 1/0, T/F, Y/N (case-insensitive)",
        "example": "True, False, Yes, No, 1, 0",
        # Set membership check is simpler and more readable than a regex alternative
        "custom_check": "boolean",
    },
    "gender": {
        "name": "Gender (inclusive vocabulary)",
        "category": "Categorical",
        "description": "Standardised gender values per UK government guidance",
        "example": "Male, Female, Non-binary, Prefer not to say",
        # Set membership check against _GENDER_VALUES (defined below)
        "custom_check": "gender",
    },

    # ── Text ──────────────────────────────────────────────────────────────────

    "alpha_only": {
        "name": "Alphabetic Text Only",
        "category": "Text",
        "description": "Contains only alphabetic characters and spaces (no digits or symbols)",
        "example": "John Smith, New York",
        # Pattern: one or more letters, spaces, hyphens, or apostrophes/periods
        # (covers names like "O'Brien", "St. James", "Jean-Claude")
        "pattern": r"^[A-Za-z\s\-'\.]+$",
    },
    "alphanumeric": {
        "name": "Alphanumeric",
        "category": "Text",
        "description": "Contains only letters, digits, and common word separators",
        "example": "ABC123, order-456",
        # Pattern: letters, digits, spaces, hyphens, underscores
        "pattern": r"^[A-Za-z0-9\s\-_]+$",
    },
}

# ── Gender reference values ───────────────────────────────────────────────────
# Accepted lower-cased values for the gender standard.
# Based on UK government data collection guidance for inclusive gender terminology.
# check_value() lower-cases the input before comparing to this set.
_GENDER_VALUES = {
    "male", "female", "non-binary", "nonbinary", "non binary",
    "prefer not to say", "prefer not to disclose", "other",
    "m", "f", "nb", "x", "unknown",
}


# =============================================================================
# Public validation entry point
# =============================================================================

def check_value(value, standard_id: str) -> bool:
    """
    Return True if *value* conforms to the named data standard.

    This function is called for every non-null value in every mapped column.
    It dispatches to:
      a) A custom code path for standards with "custom_check" defined.
      b) A regex pattern match for standards with "pattern" defined.

    Null/empty values always return False here — they are handled separately
    by the completeness checker and should not be double-penalised as invalid.
    """
    if value is None:
        return False   # Null Python object — never valid

    str_val = str(value).strip()  # Convert to string and remove leading/trailing whitespace

    # Treat common null-like string representations as null — completeness handles these;
    # we don't want them flagged as invalid as well (that would double-penalise missing data).
    if str_val == "" or str_val.lower() in ("nan", "none", "null", "na", "n/a"):
        return False

    # Look up the standard definition dict by its ID
    std = DATA_STANDARDS.get(standard_id)

    if not std:
        return True   # Unknown standard ID — assume valid to avoid false penalisation

    # Determine if this standard uses a custom check path
    cc = std.get("custom_check")  # Will be a string key like "boolean", or None

    # ── Custom check: boolean ──────────────────────────────────────────────────
    if cc == "boolean":
        # Check whether the lower-cased string is in the accepted boolean value set
        return str_val.lower() in _BOOLEAN_VALUES

    # ── Custom check: percentage ───────────────────────────────────────────────
    if cc == "percentage":
        # Attempt to parse as a float and verify the value is in range 0–100
        try:
            return 0.0 <= float(str_val) <= 100.0  # True if numeric and within range
        except (ValueError, TypeError):
            return False  # Not parseable as a number — invalid

    # ── Custom check: ISO 3166-1 Alpha-2 country code ─────────────────────────
    if cc == "iso2_country":
        # Upper-case the value and check membership in the pre-built set
        return str_val.upper() in _ISO2_COUNTRIES

    # ── Custom check: latitude ─────────────────────────────────────────────────
    if cc == "latitude":
        # WGS-84 latitude must be a number in the range -90.0 to +90.0
        try:
            return -90.0 <= float(str_val) <= 90.0
        except (ValueError, TypeError):
            return False

    # ── Custom check: longitude ────────────────────────────────────────────────
    if cc == "longitude":
        # WGS-84 longitude must be a number in the range -180.0 to +180.0
        try:
            return -180.0 <= float(str_val) <= 180.0
        except (ValueError, TypeError):
            return False

    # ── Custom check: gender ───────────────────────────────────────────────────
    if cc == "gender":
        # Lower-case and check against the inclusive gender vocabulary set
        return str_val.lower() in _GENDER_VALUES

    # ── Regex pattern check ────────────────────────────────────────────────────
    pattern = std.get("pattern")  # The raw regex string, or None if not defined
    if pattern:
        flags = std.get("flags", 0)   # re flags like re.IGNORECASE; default 0 (no flags)
        # re.match() anchors to the start of the string.
        # The patterns also include ^ and $ anchors so the entire string must match.
        return bool(re.match(pattern, str_val, flags))

    # If no pattern and no custom_check, the standard is defined but has no validation rule.
    # Default to True (valid) — don't penalise for an incomplete standard definition.
    return True
