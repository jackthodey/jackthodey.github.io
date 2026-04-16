# =============================================================================
# DATA QUALITY ASSESSMENT TOOL – GOVERNANCE QUESTIONNAIRE
# =============================================================================
# 20 questions across 5 DAMA-DMBOK2 dimensions.
# Each option value (1–4) represents a maturity level:
#   1 = Ad hoc / none   2 = Informal   3 = Defined   4 = Optimised / enforced
# Reference: DAMA-DMBOK2, DCAM (EDM Council), ISO 8000, ISO/IEC 27001, GDPR
# =============================================================================

DIMENSION_LABELS = {
    "governance_ownership":  "Governance & Ownership",
    "quality_management":    "Data Quality Management",
    "lineage_documentation": "Lineage & Documentation",
    "security_access":       "Security & Access Control",
    "training_compliance":   "Training & Compliance",
}

QUESTIONS = [

    # ── DIMENSION 1: Governance & Ownership ──────────────────────────────────
    {
        "id": "q1",
        "dimension": "governance_ownership",
        "text": "Does this data table have a formally designated Data Owner?",
        "reference": "DAMA-DMBOK2 Ch.3 – Data Governance; DCAM Capability 1.2",
        "options": [
            {"value": 1, "label": "No – no owner has been identified"},
            {"value": 2, "label": "Informally identified but not documented or communicated"},
            {"value": 3, "label": "Formally assigned with documented responsibilities"},
            {"value": 4, "label": "Formally assigned, responsibilities documented, and reviewed on a regular governance cycle"},
        ],
    },
    {
        "id": "q2",
        "dimension": "governance_ownership",
        "text": "Is there a designated Data Steward responsible for the ongoing quality and fitness-for-use of this table?",
        "reference": "DAMA-DMBOK2 Ch.3 – Data Stewardship",
        "options": [
            {"value": 1, "label": "No steward assigned"},
            {"value": 2, "label": "Informally assigned with no defined duties"},
            {"value": 3, "label": "Formally assigned with documented and communicated duties"},
            {"value": 4, "label": "Formally assigned, duties documented, and stewardship performance regularly reviewed"},
        ],
    },
    {
        "id": "q3",
        "dimension": "governance_ownership",
        "text": "Is the business purpose and authoritative use of this table formally documented?",
        "reference": "DAMA-DMBOK2 Ch.12 – Metadata Management; DCAM Capability 2.1",
        "options": [
            {"value": 1, "label": "No documentation exists"},
            {"value": 2, "label": "Purpose captured informally (e.g. email or verbal agreement)"},
            {"value": 3, "label": "Formally documented in a data catalogue or knowledge base"},
            {"value": 4, "label": "Formally documented, versioned, reviewed regularly, and linked to business processes"},
        ],
    },
    {
        "id": "q4",
        "dimension": "governance_ownership",
        "text": "Is there a formal data governance policy that applies to and covers this table?",
        "reference": "DAMA-DMBOK2 Ch.3 – Data Governance Policies",
        "options": [
            {"value": 1, "label": "No policy exists"},
            {"value": 2, "label": "Informal guidelines exist but are not enforced"},
            {"value": 3, "label": "Formal policy exists and is accessible to all relevant stakeholders"},
            {"value": 4, "label": "Formal policy exists, enforced via scheduled audits, and linked to organisational compliance obligations"},
        ],
    },

    # ── DIMENSION 2: Data Quality Management ─────────────────────────────────
    {
        "id": "q5",
        "dimension": "quality_management",
        "text": "Are data quality rules (business rules, validation rules, or data contracts) formally defined for this table?",
        "reference": "DAMA-DMBOK2 Ch.13 – Data Quality Management; ISO 8000-61",
        "options": [
            {"value": 1, "label": "No quality rules defined"},
            {"value": 2, "label": "Rules informally understood by a few key individuals only"},
            {"value": 3, "label": "Rules formally documented and accessible to all stakeholders"},
            {"value": 4, "label": "Rules documented, implemented in systems as technical controls, and monitored automatically"},
        ],
    },
    {
        "id": "q6",
        "dimension": "quality_management",
        "text": "Is data quality monitored and reported on a regular, scheduled basis?",
        "reference": "DAMA-DMBOK2 Ch.13 – Data Quality Monitoring & Reporting",
        "options": [
            {"value": 1, "label": "No monitoring in place"},
            {"value": 2, "label": "Ad hoc monitoring only — reactive when issues are raised"},
            {"value": 3, "label": "Regular scheduled monitoring with reports distributed to data owner/steward"},
            {"value": 4, "label": "Automated real-time monitoring with dashboards, alerting, and formal SLA targets"},
        ],
    },
    {
        "id": "q7",
        "dimension": "quality_management",
        "text": "Are there defined processes for identifying, escalating, and resolving data quality issues?",
        "reference": "DAMA-DMBOK2 Ch.13 – Issue Management & Remediation",
        "options": [
            {"value": 1, "label": "No process exists — issues are handled ad hoc"},
            {"value": 2, "label": "Issues resolved informally case-by-case, no documentation"},
            {"value": 3, "label": "Defined process documented with a clear escalation path"},
            {"value": 4, "label": "Defined process with SLAs, root cause analysis, and continuous improvement tracking"},
        ],
    },
    {
        "id": "q8",
        "dimension": "quality_management",
        "text": "Have the key data quality dimensions (completeness, accuracy, consistency, timeliness, uniqueness) been formally assessed for this table?",
        "reference": "DAMA-DMBOK2 Ch.13; ISO 8000-8 Data Quality Dimensions",
        "options": [
            {"value": 1, "label": "Never formally assessed"},
            {"value": 2, "label": "Informally assessed at some point, results not documented"},
            {"value": 3, "label": "Formally assessed with documented and shared results"},
            {"value": 4, "label": "Formally assessed on a recurring schedule with trend analysis and measurable improvement targets"},
        ],
    },

    # ── DIMENSION 3: Lineage & Documentation ─────────────────────────────────
    {
        "id": "q9",
        "dimension": "lineage_documentation",
        "text": "Is data lineage (source systems, transformations, and downstream consumers) documented for this table?",
        "reference": "DAMA-DMBOK2 Ch.12 – Data Lineage; DCAM Capability 3.1",
        "options": [
            {"value": 1, "label": "No lineage documentation exists"},
            {"value": 2, "label": "Partially documented informally (e.g. a diagram or tribal knowledge)"},
            {"value": 3, "label": "End-to-end lineage fully documented in a data catalogue or lineage tool"},
            {"value": 4, "label": "Lineage documented, automated where possible, and kept current via change management processes"},
        ],
    },
    {
        "id": "q10",
        "dimension": "lineage_documentation",
        "text": "Is there a data dictionary or metadata record for this table covering field definitions, data types, constraints, and examples?",
        "reference": "DAMA-DMBOK2 Ch.12 – Metadata; DCAM Capability 2.2",
        "options": [
            {"value": 1, "label": "No data dictionary or metadata exists"},
            {"value": 2, "label": "Partial metadata recorded informally (e.g. a spreadsheet or comments in code)"},
            {"value": 3, "label": "Full data dictionary with field definitions, types, constraints, and valid ranges documented"},
            {"value": 4, "label": "Full data dictionary, versioned, reviewed regularly, and linked to a business glossary"},
        ],
    },
    {
        "id": "q11",
        "dimension": "lineage_documentation",
        "text": "Are formal change management processes in place for schema or significant data changes to this table?",
        "reference": "DAMA-DMBOK2 Ch.3 – Data Change Management; ITIL Change Management",
        "options": [
            {"value": 1, "label": "No change management process — changes happen without notice"},
            {"value": 2, "label": "Ad hoc notification to affected parties when changes occur"},
            {"value": 3, "label": "Formal change request and approval process with communication to stakeholders"},
            {"value": 4, "label": "Formal change management with impact assessment, approval gates, versioning, and rollback procedures"},
        ],
    },
    {
        "id": "q12",
        "dimension": "lineage_documentation",
        "text": "Are the key business terms and definitions for data in this table agreed upon and consistently understood across all consuming stakeholder groups?",
        "reference": "DAMA-DMBOK2 Ch.9 – Business Glossary; DCAM Capability 2.3",
        "options": [
            {"value": 1, "label": "No agreed terminology — different teams interpret the data differently"},
            {"value": 2, "label": "Informally agreed within a single team but not wider organisation"},
            {"value": 3, "label": "Formally defined in a business glossary and communicated to all stakeholders"},
            {"value": 4, "label": "Formally defined, approved by all stakeholder groups, and integrated into data tooling and reporting"},
        ],
    },

    # ── DIMENSION 4: Security & Access Control ────────────────────────────────
    {
        "id": "q13",
        "dimension": "security_access",
        "text": "Has the data in this table been classified by sensitivity level (e.g. Public, Internal, Confidential, Restricted)?",
        "reference": "DAMA-DMBOK2 Ch.7 – Data Security; ISO/IEC 27001 A.8.2",
        "options": [
            {"value": 1, "label": "No data classification has been applied"},
            {"value": 2, "label": "Informally classified without a standard framework or register"},
            {"value": 3, "label": "Formally classified using an organisational standard and documented in a data register"},
            {"value": 4, "label": "Formally classified, access controls enforced per classification level, and reviewed on a regular cycle"},
        ],
    },
    {
        "id": "q14",
        "dimension": "security_access",
        "text": "Are role-based access controls (RBAC) formally defined and enforced for this table?",
        "reference": "DAMA-DMBOK2 Ch.7 – Data Security; NIST 800-53 AC-2; ISO/IEC 27001 A.9",
        "options": [
            {"value": 1, "label": "No access controls in place — broadly accessible"},
            {"value": 2, "label": "Basic restrictions only (e.g. database-level permissions, not role-based)"},
            {"value": 3, "label": "Role-based access controls formally defined and implemented"},
            {"value": 4, "label": "RBAC with least-privilege principles, access reviewed quarterly, and integrated with identity management (SSO/IAM)"},
        ],
    },
    {
        "id": "q15",
        "dimension": "security_access",
        "text": "Is personally identifiable information (PII) or other sensitive data in this table identified, documented, and technically protected?",
        "reference": "DAMA-DMBOK2 Ch.7; GDPR Art.25 (Privacy by Design); CCPA",
        "options": [
            {"value": 1, "label": "PII not identified or protected"},
            {"value": 2, "label": "PII identified but protections are informal or incomplete"},
            {"value": 3, "label": "PII identified, documented in a data register, and basic protections applied (e.g. masking, encryption at rest)"},
            {"value": 4, "label": "PII fully documented, protected (encryption, masking, tokenisation), and subject to regular regulatory compliance review with evidence"},
        ],
    },
    {
        "id": "q16",
        "dimension": "security_access",
        "text": "Are audit logs maintained that record who accessed or modified data in this table, and are they reviewed?",
        "reference": "DAMA-DMBOK2 Ch.7 – Audit Logging; ISO/IEC 27001 A.12.4; GDPR Art.5(2)",
        "options": [
            {"value": 1, "label": "No audit logging in place"},
            {"value": 2, "label": "Basic system-level logging only (not data-access specific, not reviewed)"},
            {"value": 3, "label": "Data-level audit logs maintained and accessible to authorised personnel"},
            {"value": 4, "label": "Comprehensive logs regularly reviewed, retained per policy, and used for compliance and security reporting"},
        ],
    },

    # ── DIMENSION 5: Training & Compliance ───────────────────────────────────
    {
        "id": "q17",
        "dimension": "training_compliance",
        "text": "Do users who enter data into the source system for this table receive formal training on correct data entry standards and expectations?",
        "reference": "DAMA-DMBOK2 Ch.3 – Data Culture & Training; DCAM Capability 6.1",
        "options": [
            {"value": 1, "label": "No training provided"},
            {"value": 2, "label": "Informal on-the-job training only — undocumented and inconsistent"},
            {"value": 3, "label": "Formal training provided but attendance is not mandatory"},
            {"value": 4, "label": "Mandatory formal training with documented competency assessment and periodic refresher requirements"},
        ],
    },
    {
        "id": "q18",
        "dimension": "training_compliance",
        "text": "Does the source system enforce validated and standardised data entry through technical controls (beyond basic type checking)?",
        "reference": "DAMA-DMBOK2 Ch.13 – Data Quality at Source; DCAM Capability 4.3",
        "options": [
            {"value": 1, "label": "No controls — free-text entry with no validation whatsoever"},
            {"value": 2, "label": "Basic controls only (e.g. field type or character-length validation)"},
            {"value": 3, "label": "Dropdown lists, picklists, or reference data validation implemented for key fields"},
            {"value": 4, "label": "Comprehensive validation: cross-field rules, reference data enforcement, and exception-handling workflows — strictly enforced"},
        ],
    },
    {
        "id": "q19",
        "dimension": "training_compliance",
        "text": "Are regulatory or compliance requirements applicable to this table identified, and are formal controls in place and evidenced?",
        "reference": "DAMA-DMBOK2 Ch.3; GDPR; SOX; HIPAA; PCI-DSS (as applicable)",
        "options": [
            {"value": 1, "label": "Compliance requirements not identified or unknown"},
            {"value": 2, "label": "Requirements identified but addressed informally without documented controls or evidence"},
            {"value": 3, "label": "Requirements formally identified with documented and implemented controls"},
            {"value": 4, "label": "Requirements fully addressed with evidence, audited on a regular cycle, and reported to governance bodies"},
        ],
    },
    {
        "id": "q20",
        "dimension": "training_compliance",
        "text": "Is there a defined and enforced data retention and disposal policy for this table?",
        "reference": "DAMA-DMBOK2 Ch.5 – Data Lifecycle Management; GDPR Art.5(1)(e) – Storage Limitation",
        "options": [
            {"value": 1, "label": "No retention or disposal policy exists"},
            {"value": 2, "label": "Policy informally understood but not documented or enforced"},
            {"value": 3, "label": "Formal policy documented, communicated to the data owner, and applied manually"},
            {"value": 4, "label": "Formal policy documented, automated enforcement where possible, reviewed regularly, and compliant with applicable regulation"},
        ],
    },
]
