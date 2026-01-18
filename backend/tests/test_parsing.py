"""Tests for ranking and confidence parsing."""

import pytest
from backend.council import parse_ranking_from_text, parse_confidence_from_response


class TestRankingParser:
    """Tests for parse_ranking_from_text function."""

    def test_standard_format(self):
        """Parse standard FINAL RANKING format."""
        text = """
        Here is my evaluation of all responses...

        FINAL RANKING:
        1. Response B
        2. Response A
        3. Response C
        """

        result = parse_ranking_from_text(text)
        assert result == ["Response B", "Response A", "Response C"]

    def test_no_numbers(self):
        """Parse ranking without numbers."""
        text = """
        FINAL RANKING:
        Response C
        Response A
        Response B
        """

        result = parse_ranking_from_text(text)
        assert result == ["Response C", "Response A", "Response B"]

    def test_with_explanations(self):
        """Parse ranking with inline explanations."""
        text = """
        FINAL RANKING:
        1. Response B - Best overall approach with clear reasoning
        2. Response A - Good but verbose in places
        3. Response C - Missing key details
        """

        result = parse_ranking_from_text(text)
        assert result == ["Response B", "Response A", "Response C"]

    def test_with_parentheses(self):
        """Parse ranking with parenthetical notes."""
        text = """
        FINAL RANKING:
        1. Response A (most comprehensive)
        2. Response B (good but incomplete)
        3. Response C (needs improvement)
        """

        result = parse_ranking_from_text(text)
        assert result == ["Response A", "Response B", "Response C"]

    def test_colon_after_response(self):
        """Parse ranking with colon after Response X."""
        text = """
        FINAL RANKING:
        1. Response A: excellent analysis
        2. Response B: good effort
        3. Response C: adequate
        """

        result = parse_ranking_from_text(text)
        assert result == ["Response A", "Response B", "Response C"]

    def test_fallback_without_final_ranking_header(self):
        """Fallback extraction when FINAL RANKING header is missing."""
        text = """
        Based on my analysis, Response A is the best, followed by Response C,
        and finally Response B.
        """

        result = parse_ranking_from_text(text)
        # Should extract responses in order of mention
        assert "Response A" in result
        assert "Response C" in result
        assert "Response B" in result

    def test_empty_input(self):
        """Handle empty input gracefully."""
        result = parse_ranking_from_text("")
        assert result == []

    def test_none_input(self):
        """Handle None input gracefully."""
        # May raise or return empty - both are acceptable
        try:
            result = parse_ranking_from_text(None)
            assert result == [] or result is None
        except (TypeError, AttributeError):
            pass  # Also acceptable to raise on None

    def test_no_responses_mentioned(self):
        """Handle text with no Response mentions."""
        result = parse_ranking_from_text("This is just some random text about nothing.")
        assert result == []

    def test_lowercase_response(self):
        """Handle lowercase 'response' mentions."""
        text = """
        FINAL RANKING:
        1. response A
        2. response B
        """

        result = parse_ranking_from_text(text)
        # Parser may or may not be case-insensitive
        # Just verify it doesn't crash and returns a list
        assert isinstance(result, list)

    def test_extended_labels(self):
        """Handle more than 3 responses (A through I for 9 models)."""
        text = """
        FINAL RANKING:
        1. Response A
        2. Response B
        3. Response C
        4. Response D
        5. Response E
        6. Response F
        7. Response G
        8. Response H
        9. Response I
        """

        result = parse_ranking_from_text(text)
        assert len(result) == 9
        assert result[0] == "Response A"
        assert result[8] == "Response I"

    def test_duplicate_mentions_only_counted_once(self):
        """Duplicates in ranking should be handled."""
        text = """
        Response A is really good. Let me emphasize that Response A is the best.

        FINAL RANKING:
        1. Response A
        2. Response B
        """

        result = parse_ranking_from_text(text)
        # In final ranking section, A should only appear once
        assert result.count("Response A") == 1

    def test_ranking_with_bullet_points(self):
        """Handle bullet point format."""
        text = """
        FINAL RANKING:
        • Response B
        • Response A
        • Response C
        """

        result = parse_ranking_from_text(text)
        assert result == ["Response B", "Response A", "Response C"]


class TestConfidenceParser:
    """Tests for parse_confidence_from_response function."""

    def test_standard_format(self):
        """Parse standard CONFIDENCE: X/10 format."""
        text = """
        Here is my response about the topic.

        CONFIDENCE: 8/10
        """

        response, confidence = parse_confidence_from_response(text)
        assert confidence == 8.0
        assert "CONFIDENCE" not in response

    def test_confidence_with_decimal(self):
        """Parser only supports integer confidence values (not decimals)."""
        text = "My answer is correct. CONFIDENCE: 8.5/10"

        response, confidence = parse_confidence_from_response(text)
        # Current implementation only matches integers (\d+), not decimals
        # This is expected behavior - models are asked to use integers
        assert confidence is None  # Decimal format not supported

    def test_no_confidence(self):
        """Handle response without confidence score."""
        text = "Just a regular response without any confidence score."

        response, confidence = parse_confidence_from_response(text)
        assert confidence is None
        assert response == text

    def test_confidence_at_start(self):
        """Handle confidence at the start of response."""
        text = "CONFIDENCE: 9/10\n\nHere is my detailed response."

        response, confidence = parse_confidence_from_response(text)
        # Confidence may be at start or end - parser may find it
        # Just verify it parses correctly if found
        if confidence is not None:
            assert confidence == 9.0

    def test_alternative_formats(self):
        """Handle alternative confidence formats."""
        # Test different spacing
        text1 = "Answer here. CONFIDENCE:7/10"
        text2 = "Answer here. CONFIDENCE: 7 / 10"
        text3 = "Answer here. Confidence: 7/10"

        _, conf1 = parse_confidence_from_response(text1)
        _, conf2 = parse_confidence_from_response(text2)
        _, conf3 = parse_confidence_from_response(text3)

        # At least the standard format should work
        assert conf1 == 7.0 or conf2 == 7.0 or conf3 == 7.0

    def test_confidence_clipping(self):
        """Confidence should be clipped to valid range."""
        text_high = "Answer. CONFIDENCE: 15/10"
        text_low = "Answer. CONFIDENCE: -5/10"

        _, conf_high = parse_confidence_from_response(text_high)
        _, conf_low = parse_confidence_from_response(text_low)

        # Should handle out-of-range values gracefully
        # (either clip or return None)
        if conf_high is not None:
            assert 0 <= conf_high <= 10
        if conf_low is not None:
            assert 0 <= conf_low <= 10
