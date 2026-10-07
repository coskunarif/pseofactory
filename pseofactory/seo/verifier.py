"""
Re-export MasterSEOVerifier and gates from pseofactory.verifier.
"""

from pseofactory.verifier import (
    MasterSEOVerifier,
    SEOVerificationError,
    ZyppyHTMLParser,
    audit_seo_checklist,
    run_seo_checklist_audit,
    check_snippet_eligibility_gate,
    FORBIDDEN_JARGON,
)

__all__ = [
    "MasterSEOVerifier",
    "SEOVerificationError",
    "ZyppyHTMLParser",
    "audit_seo_checklist",
    "run_seo_checklist_audit",
    "check_snippet_eligibility_gate",
    "FORBIDDEN_JARGON",
]
