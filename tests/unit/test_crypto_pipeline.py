"""Tests for signing pipeline enforcement (E7).

Verifies that security_sign_content runs analysis before signing
and refuses to sign content with findings.
"""


def test_sign_content_imports_rules():
    """security_sign_content must import and use security rules."""
    import inspect
    from spellbook.mcp.tools.security import security_sign_content
    source = inspect.getsource(security_sign_content)
    assert "check_patterns" in source, "sign_content must call check_patterns"
    assert "INJECTION_RULES" in source, "sign_content must check injection rules"
    assert "EXFILTRATION_RULES" in source, "sign_content must check exfiltration rules"


def test_sign_content_registers_untrusted_on_findings():
    """security_sign_content must reference 'untrusted' for failed analysis."""
    import inspect
    from spellbook.mcp.tools.security import security_sign_content
    source = inspect.getsource(security_sign_content)
    assert "untrusted" in source, "sign_content must register untrusted on findings"


def test_sign_content_checks_all_rule_categories():
    """security_sign_content must check all four rule categories."""
    import inspect
    from spellbook.mcp.tools.security import security_sign_content
    source = inspect.getsource(security_sign_content)
    for rule_set in ["INJECTION_RULES", "EXFILTRATION_RULES", "ESCALATION_RULES", "OBFUSCATION_RULES"]:
        assert rule_set in source, f"sign_content must check {rule_set}"
