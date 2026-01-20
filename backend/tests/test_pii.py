"""Tests for PII detection module."""

import pytest
from backend.security.pii import detect_pii, scan_response_for_pii, PIIMatch, PIIReport


class TestPIIDetection:
    """Test PII detection logic."""

    def test_detect_ssn(self):
        """Should detect Social Security Numbers."""
        text = "My SSN is 123-45-6789"
        report = detect_pii(text)
        assert report.has_pii
        assert any(m.pii_type == "ssn" for m in report.matches)

    def test_detect_credit_card(self):
        """Should detect credit card numbers."""
        # Visa format
        text = "Card: 4111111111111111"
        report = detect_pii(text)
        assert report.has_pii
        assert any(m.pii_type == "credit_card" for m in report.matches)

    def test_detect_credit_card_spaced(self):
        """Should detect credit cards with spaces."""
        text = "Card: 4111 1111 1111 1111"
        report = detect_pii(text)
        assert report.has_pii
        assert any(m.pii_type == "credit_card_spaced" for m in report.matches)

    def test_detect_email(self):
        """Should detect email addresses."""
        text = "Contact me at john.doe@example.com"
        report = detect_pii(text)
        assert report.has_pii
        assert any(m.pii_type == "email" for m in report.matches)

    def test_detect_phone(self):
        """Should detect US phone numbers."""
        text = "Call me at (555) 123-4567"
        report = detect_pii(text)
        assert report.has_pii
        assert any(m.pii_type == "phone_us" for m in report.matches)

    def test_detect_phone_with_country_code(self):
        """Should detect phone with country code."""
        text = "Call +1-555-123-4567"
        report = detect_pii(text)
        assert report.has_pii
        assert any(m.pii_type == "phone_us" for m in report.matches)

    def test_detect_ip_address(self):
        """Should detect IP addresses."""
        text = "Server IP: 192.168.1.100"
        report = detect_pii(text)
        assert report.has_pii
        assert any(m.pii_type == "ip_address" for m in report.matches)

    def test_no_false_positive_normal_text(self):
        """Should not flag normal text."""
        text = "The answer to life is forty-two."
        report = detect_pii(text)
        assert not report.has_pii
        assert len(report.matches) == 0

    def test_no_false_positive_short_numbers(self):
        """Should not flag short numbers as SSN."""
        text = "The year is 2024 and the count is 12345."
        report = detect_pii(text)
        # 12345 is only 5 digits, not 9
        assert not any(m.pii_type == "ssn" for m in report.matches)

    def test_multiple_pii_types(self):
        """Should detect multiple PII types in one text."""
        text = "Email: test@example.com, SSN: 123-45-6789, Phone: 555-123-4567"
        report = detect_pii(text)
        assert report.has_pii
        assert len(report.matches) >= 3

    def test_redaction(self):
        """Should redact PII when requested."""
        text = "My SSN is 123-45-6789"
        report = detect_pii(text, redact=True)
        assert "123-45-6789" not in report.redacted_text
        assert "[SSN_REDACTED]" in report.redacted_text

    def test_redaction_preserves_surrounding_text(self):
        """Redaction should preserve surrounding text."""
        text = "Contact john@example.com for details"
        report = detect_pii(text, redact=True)
        assert "Contact" in report.redacted_text
        assert "for details" in report.redacted_text
        assert "[EMAIL_REDACTED]" in report.redacted_text

    def test_empty_text(self):
        """Should handle empty text."""
        report = detect_pii("")
        assert not report.has_pii
        assert report.redacted_text == ""

    def test_warnings_generated(self):
        """Should generate warnings when PII detected."""
        text = "SSN: 123-45-6789"
        report = detect_pii(text)
        assert len(report.warnings) > 0
        assert any("pii" in w.lower() for w in report.warnings)


class TestScanResponseForPII:
    """Test the simplified scan_response_for_pii function."""

    def test_returns_none_for_clean_text(self):
        """Should return None when no PII found."""
        result = scan_response_for_pii("This is a clean response")
        assert result is None

    def test_returns_dict_for_pii(self):
        """Should return dict when PII found."""
        result = scan_response_for_pii("Contact: 123-45-6789")
        assert result is not None
        assert result["pii_detected"] is True
        assert result["count"] >= 1

    def test_includes_pii_types(self):
        """Should include list of PII types found."""
        result = scan_response_for_pii("Email: test@example.com, SSN: 123-45-6789")
        assert result is not None
        assert "ssn" in result["types"]
        assert "email" in result["types"]


class TestPIIMatch:
    """Test PIIMatch dataclass."""

    def test_match_creation(self):
        """Should create match with all fields."""
        match = PIIMatch(
            pii_type="ssn",
            value="123-45-6789",
            start=10,
            end=21,
            redacted="[SSN_REDACTED]"
        )
        assert match.pii_type == "ssn"
        assert match.value == "123-45-6789"
        assert match.start == 10
        assert match.end == 21


class TestPIIReport:
    """Test PIIReport dataclass."""

    def test_report_creation(self):
        """Should create report with all fields."""
        report = PIIReport(
            has_pii=True,
            matches=[],
            redacted_text="test",
            warnings=["Warning 1"]
        )
        assert report.has_pii is True
        assert report.redacted_text == "test"
        assert len(report.warnings) == 1
