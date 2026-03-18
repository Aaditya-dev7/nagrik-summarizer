"""
Profanity Filter for Nagrik Smart Grievance Portal
===================================================
Strict content filtering before AI processing.

- Loads profanity_data.json once at startup
- Whole-word matching only (no false positives)
- Supports English, Hindi (basic), Marathi (basic)
- Blocks submission completely if profanity detected
"""

import json
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ValidationResult:
    """Result of profanity validation."""
    is_clean: bool
    severity_level: Optional[str]  # "high", "low", or None
    detected_words: List[str]
    message: str


class ProfanityFilter:
    """
    Strict profanity filter for civic grievance portal.
    
    Usage:
        filter = ProfanityFilter("profanity_data.json")
        result = filter.validate_text("Some user input")
        if not result.is_clean:
            # Block submission
            return error
    """
    
    def __init__(self, json_path: str = "profanity_data.json"):
        """Load and compile profanity patterns once at startup."""
        self.json_path = Path(json_path)
        self._high_severity_words: set = set()
        self._low_severity_words: set = set()
        self._high_pattern: Optional[re.Pattern] = None
        self._low_pattern: Optional[re.Pattern] = None
        
        self._load_data()
        self._compile_patterns()
    
    def _load_data(self) -> None:
        """Load profanity data from JSON file."""
        try:
            with open(self.json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Convert to lowercase sets for O(1) lookup
            self._high_severity_words = {
                word.lower().strip() 
                for word in data.get("high_severity", [])
                if word and word.strip()
            }
            self._low_severity_words = {
                word.lower().strip()
                for word in data.get("low_severity", [])
                if word and word.strip()
            }
            
            print(f"[ProfanityFilter] Loaded {len(self._high_severity_words)} high-severity words")
            print(f"[ProfanityFilter] Loaded {len(self._low_severity_words)} low-severity words")
            
        except FileNotFoundError:
            print(f"[ProfanityFilter] WARNING: {self.json_path} not found. Using empty filter.")
            self._high_severity_words = set()
            self._low_severity_words = set()
        except json.JSONDecodeError as e:
            print(f"[ProfanityFilter] ERROR: Invalid JSON in {self.json_path}: {e}")
            raise
    
    def _compile_patterns(self) -> None:
        """
        Compile regex patterns for whole-word matching.
        
        Uses word boundaries (\b) to match whole words only.
        This prevents false positives like:
        - "assignment" being flagged for "ass"
        - "class" being flagged for "ass"
        - "analysis" being flagged for "anal"
        """
        # Escape special regex characters and join with |
        if self._high_severity_words:
            escaped_high = [re.escape(word) for word in self._high_severity_words]
            pattern_high = r'\b(' + '|'.join(escaped_high) + r')\b'
            self._high_pattern = re.compile(pattern_high, re.IGNORECASE)
        else:
            self._high_pattern = None
        
        if self._low_severity_words:
            escaped_low = [re.escape(word) for word in self._low_severity_words]
            pattern_low = r'\b(' + '|'.join(escaped_low) + r')\b'
            self._low_pattern = re.compile(pattern_low, re.IGNORECASE)
        else:
            self._low_pattern = None
    
    def _find_matches(self, text: str, pattern: re.Pattern) -> List[str]:
        """Find all whole-word matches in text."""
        matches = pattern.findall(text)
        # findall returns list of tuples if groups exist, flatten
        if matches and isinstance(matches[0], tuple):
            matches = [m[0] if isinstance(m, tuple) else m for m in matches]
        return [m.lower() for m in matches]
    
    def validate_text(
        self, 
        user_input: str, 
        strict_mode: bool = True
    ) -> ValidationResult:
        """
        Validate text for profanity content.
        
        Args:
            user_input: The text to validate
            strict_mode: If True, block low-severity words too
        
        Returns:
            ValidationResult with:
            - is_clean: True if text passes filter
            - severity_level: "high", "low", or None
            - detected_words: List of detected profane words
            - message: Human-readable result message
        """
        if not user_input or not user_input.strip():
            return ValidationResult(
                is_clean=True,
                severity_level=None,
                detected_words=[],
                message="Text is empty"
            )
        
        # Normalize text for matching
        text = user_input.strip()
        
        # Check high-severity first (always block)
        high_matches = []
        if self._high_pattern:
            high_matches = self._find_matches(text, self._high_pattern)
        
        if high_matches:
            return ValidationResult(
                is_clean=False,
                severity_level="high",
                detected_words=list(set(high_matches)),
                message=f"Report blocked: Inappropriate language detected. Please use respectful language in civic complaints."
            )
        
        # Check low-severity (block in strict mode)
        low_matches = []
        if self._low_pattern:
            low_matches = self._find_matches(text, self._low_pattern)
        
        if low_matches and strict_mode:
            return ValidationResult(
                is_clean=False,
                severity_level="low",
                detected_words=list(set(low_matches)),
                message=f"Report blocked: Please use professional language in civic complaints."
            )
        
        # Text is clean
        return ValidationResult(
            is_clean=True,
            severity_level=None,
            detected_words=[],
            message="Text passed content filter"
        )
    
    def validate_report(
        self,
        description: str,
        category: Optional[str] = None,
        location: Optional[str] = None,
        reporter_name: Optional[str] = None,
        strict_mode: bool = True
    ) -> ValidationResult:
        """
        Validate all text fields in a report.
        
        Args:
            description: Main report description
            category: Category text (optional)
            location: Location text (optional)
            reporter_name: Reporter name (optional)
            strict_mode: Block low-severity words
        
        Returns:
            Combined validation result
        """
        # Check description (main content)
        result = self.validate_text(description, strict_mode)
        if not result.is_clean:
            result.message = f"Description: {result.message}"
            return result
        
        # Check optional fields
        for field_name, field_value in [
            ("Category", category),
            ("Location", location),
            ("Reporter name", reporter_name)
        ]:
            if field_value:
                field_result = self.validate_text(field_value, strict_mode)
                if not field_result.is_clean:
                    field_result.message = f"{field_name}: {field_result.message}"
                    return field_result
        
        return ValidationResult(
            is_clean=True,
            severity_level=None,
            detected_words=[],
            message="All fields passed content filter"
        )


# Singleton instance for app-wide use
_filter_instance: Optional[ProfanityFilter] = None


def get_filter(json_path: str = "profanity_data.json") -> ProfanityFilter:
    """Get or create singleton ProfanityFilter instance."""
    global _filter_instance
    if _filter_instance is None:
        _filter_instance = ProfanityFilter(json_path)
    return _filter_instance


def validate_text(user_input: str, strict_mode: bool = True) -> ValidationResult:
    """Convenience function using singleton filter."""
    return get_filter().validate_text(user_input, strict_mode)


def validate_report(
    description: str,
    category: Optional[str] = None,
    location: Optional[str] = None,
    reporter_name: Optional[str] = None,
    strict_mode: bool = True
) -> ValidationResult:
    """Convenience function for full report validation."""
    return get_filter().validate_report(
        description, category, location, reporter_name, strict_mode
    )


# Example usage and testing
if __name__ == "__main__":
    # Initialize filter
    pf = ProfanityFilter("profanity_data.json")
    
    # Test cases
    test_cases = [
        # Should PASS (clean text)
        ("There is a pothole on Main Street near the bus stop.", True),
        ("Garbage has not been collected for 3 days.", True),
        ("The street light is not working properly.", True),
        ("Water leakage from the main pipeline.", True),
        ("I need to submit an assignment about analysis.", True),  # Contains "ass" but should pass
        ("The class was about classification.", True),  # Contains "ass" but should pass
        
        # Should FAIL (profane text)
        ("This fucking pothole is annoying.", False),
        ("The municipality is full of idiots.", False),
        ("Damn garbage everywhere.", False),
        ("This is bullshit service.", False),
    ]
    
    print("\n" + "="*60)
    print("PROFANITY FILTER TEST RESULTS")
    print("="*60)
    
    for text, expected_clean in test_cases:
        result = pf.validate_text(text)
        status = "✓ PASS" if result.is_clean == expected_clean else "✗ FAIL"
        print(f"\n{status}")
        print(f"  Input: {text[:50]}...")
        print(f"  Clean: {result.is_clean}")
        print(f"  Severity: {result.severity_level}")
        if result.detected_words:
            print(f"  Detected: {result.detected_words}")
