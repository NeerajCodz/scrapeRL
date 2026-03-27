"""Verifier agent for cross-source verification."""

import re
from typing import Any

from app.core.action import Action, ActionType
from app.core.observation import ExtractedField, Observation

from .base import BaseAgent


class VerificationResult:
    """Result of a verification check."""

    def __init__(
        self,
        field_name: str,
        is_valid: bool,
        confidence: float,
        issues: list[str] | None = None,
        sources_checked: int = 0,
    ):
        """Initialize verification result."""
        self.field_name = field_name
        self.is_valid = is_valid
        self.confidence = confidence
        self.issues = issues or []
        self.sources_checked = sources_checked

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "field_name": self.field_name,
            "is_valid": self.is_valid,
            "confidence": self.confidence,
            "issues": self.issues,
            "sources_checked": self.sources_checked,
        }


class VerifierAgent(BaseAgent):
    """
    Agent responsible for verifying extracted data.
    
    The VerifierAgent handles:
    - Format validation (emails, URLs, dates, etc.)
    - Cross-source verification
    - Consistency checks across fields
    - Confidence scoring for verified data
    - Flagging suspicious or inconsistent data
    """

    def __init__(
        self,
        agent_id: str = "verifier",
        config: dict[str, Any] | None = None,
    ):
        """
        Initialize the VerifierAgent.
        
        Args:
            agent_id: Unique identifier for this agent.
            config: Optional configuration with keys:
                - min_confidence: Minimum confidence to accept (default: 0.7)
                - require_cross_validation: Require multiple sources (default: False)
                - strict_mode: Apply stricter validation rules (default: False)
        """
        super().__init__(agent_id, config)
        self.min_confidence = self.config.get("min_confidence", 0.7)
        self.require_cross_validation = self.config.get("require_cross_validation", False)
        self.strict_mode = self.config.get("strict_mode", False)
        self._validation_rules = self._init_validation_rules()
        self._verification_history: list[VerificationResult] = []

    def _init_validation_rules(self) -> dict[str, list[dict[str, Any]]]:
        """Initialize validation rules for common field types."""
        return {
            "email": [
                {
                    "type": "regex",
                    "pattern": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
                    "error": "Invalid email format",
                },
            ],
            "url": [
                {
                    "type": "regex",
                    "pattern": r"^https?://[^\s]+$",
                    "error": "Invalid URL format",
                },
            ],
            "phone": [
                {
                    "type": "regex",
                    "pattern": r"[\d\s\-\(\)\+]{7,}",
                    "error": "Invalid phone format",
                },
            ],
            "price": [
                {
                    "type": "range",
                    "min": 0,
                    "max": 1000000,
                    "error": "Price out of reasonable range",
                },
            ],
            "date": [
                {
                    "type": "regex",
                    "pattern": r"\d{1,4}[-/]\d{1,2}[-/]\d{1,4}",
                    "error": "Invalid date format",
                },
            ],
            "rating": [
                {
                    "type": "range",
                    "min": 0,
                    "max": 5,
                    "error": "Rating out of range",
                },
            ],
        }

    async def act(self, observation: Observation) -> Action:
        """
        Select the best verification action based on observation.
        
        Determines which extracted fields need verification and
        selects the appropriate verification method.
        
        Args:
            observation: The current state observation.
            
        Returns:
            The verification action to execute.
        """
        try:
            # Find unverified fields
            unverified = [
                f for f in observation.extracted_so_far
                if not f.verified
            ]

            if not unverified:
                return Action(
                    action_type=ActionType.DONE,
                    parameters={"success": True, "message": "All fields verified"},
                    reasoning="No unverified fields remaining",
                    confidence=1.0,
                    agent_id=self.agent_id,
                )

            # Verify the first unverified field
            field = unverified[0]
            result = await self._verify_field(field, observation)

            if result.is_valid and result.confidence >= self.min_confidence:
                return Action(
                    action_type=ActionType.VERIFY_FIELD,
                    parameters={
                        "field_name": field.field_name,
                        "verified": True,
                        "confidence": result.confidence,
                        "issues": result.issues,
                    },
                    reasoning=f"Field {field.field_name} verified with confidence {result.confidence:.2f}",
                    confidence=result.confidence,
                    agent_id=self.agent_id,
                )
            else:
                # Verification failed - may need re-extraction
                return self._create_reverify_action(field, result)

        except Exception as e:
            return Action(
                action_type=ActionType.FAIL,
                parameters={"success": False, "message": str(e)},
                reasoning=f"Verification error: {e}",
                confidence=1.0,
                agent_id=self.agent_id,
            )

    async def plan(self, observation: Observation) -> list[Action]:
        """
        Create a verification plan for all extracted fields.
        
        Args:
            observation: The current state observation.
            
        Returns:
            A list of planned verification actions.
        """
        try:
            actions: list[Action] = []

            # Plan verification for each unverified field
            for field in observation.extracted_so_far:
                if field.verified:
                    continue

                # Basic format verification
                actions.append(
                    Action(
                        action_type=ActionType.VERIFY_FIELD,
                        parameters={
                            "field_name": field.field_name,
                            "expected_type": self._infer_field_type(field.field_name),
                        },
                        reasoning=f"Verify format of {field.field_name}",
                        confidence=0.8,
                        agent_id=self.agent_id,
                    )
                )

                # Cross-source verification if required
                if self.require_cross_validation:
                    actions.append(
                        Action(
                            action_type=ActionType.VERIFY_FACT,
                            parameters={
                                "claim": f"{field.field_name}: {field.value}",
                                "confidence_threshold": self.min_confidence,
                            },
                            reasoning=f"Cross-validate {field.field_name} with other sources",
                            confidence=0.7,
                            agent_id=self.agent_id,
                        )
                    )

            return actions

        except Exception as e:
            return [
                Action(
                    action_type=ActionType.FAIL,
                    parameters={"message": f"Verification planning failed: {e}"},
                    reasoning=str(e),
                    confidence=1.0,
                    agent_id=self.agent_id,
                )
            ]

    async def _verify_field(
        self,
        field: ExtractedField,
        observation: Observation,
    ) -> VerificationResult:
        """
        Verify a single field.
        
        Args:
            field: The field to verify.
            observation: Current observation context.
            
        Returns:
            Verification result.
        """
        issues: list[str] = []
        confidence = field.confidence
        sources_checked = 1

        # Apply validation rules
        field_type = self._infer_field_type(field.field_name)
        format_valid, format_issues = self._validate_format(
            field.value,
            field_type,
        )

        if not format_valid:
            issues.extend(format_issues)
            confidence *= 0.5

        # Check for empty or null values
        if field.value is None or (
            isinstance(field.value, str) and not field.value.strip()
        ):
            issues.append("Empty value")
            confidence = 0.0

        # Check against memory context for consistency
        consistency_issues = self._check_consistency(field, observation)
        if consistency_issues:
            issues.extend(consistency_issues)
            confidence *= 0.8

        # Create result
        result = VerificationResult(
            field_name=field.field_name,
            is_valid=len(issues) == 0,
            confidence=confidence,
            issues=issues,
            sources_checked=sources_checked,
        )

        self._verification_history.append(result)
        return result

    def _validate_format(
        self,
        value: Any,
        field_type: str,
    ) -> tuple[bool, list[str]]:
        """
        Validate value format against rules.
        
        Args:
            value: The value to validate.
            field_type: The expected field type.
            
        Returns:
            Tuple of (is_valid, list of issues).
        """
        if value is None:
            return False, ["Value is None"]

        issues: list[str] = []
        rules = self._validation_rules.get(field_type, [])

        value_str = str(value)

        for rule in rules:
            rule_type = rule.get("type")

            if rule_type == "regex":
                pattern = rule.get("pattern", "")
                if not re.match(pattern, value_str):
                    issues.append(rule.get("error", "Format validation failed"))

            elif rule_type == "range":
                try:
                    num_value = float(value_str.replace(",", "").replace("$", ""))
                    min_val = rule.get("min", float("-inf"))
                    max_val = rule.get("max", float("inf"))
                    if not (min_val <= num_value <= max_val):
                        issues.append(rule.get("error", "Value out of range"))
                except ValueError:
                    issues.append("Cannot convert to number for range check")

            elif rule_type == "length":
                min_len = rule.get("min", 0)
                max_len = rule.get("max", float("inf"))
                if not (min_len <= len(value_str) <= max_len):
                    issues.append(rule.get("error", "Length validation failed"))

        return len(issues) == 0, issues

    def _check_consistency(
        self,
        field: ExtractedField,
        observation: Observation,
    ) -> list[str]:
        """
        Check field consistency with other data.
        
        Args:
            field: The field to check.
            observation: Current observation.
            
        Returns:
            List of consistency issues.
        """
        issues: list[str] = []

        # Check against other extracted fields
        for other in observation.extracted_so_far:
            if other.field_name == field.field_name:
                continue

            # Example: price should be less than total_price
            if field.field_name == "price" and other.field_name == "total_price":
                try:
                    price = float(str(field.value).replace("$", "").replace(",", ""))
                    total = float(str(other.value).replace("$", "").replace(",", ""))
                    if price > total:
                        issues.append("Price exceeds total_price")
                except (ValueError, TypeError):
                    pass

        # Check against memory for historical consistency
        memory = observation.memory_context
        if memory.long_term_relevant:
            for mem in memory.long_term_relevant:
                if mem.get("field") == field.field_name:
                    historical_value = mem.get("value")
                    if historical_value and historical_value != field.value:
                        # Different from historical - flag for review
                        issues.append(
                            f"Value differs from historical: {historical_value}"
                        )

        return issues

    def _infer_field_type(self, field_name: str) -> str:
        """Infer the field type from its name."""
        field_lower = field_name.lower()

        type_keywords = {
            "email": ["email", "mail"],
            "url": ["url", "link", "href", "website"],
            "phone": ["phone", "tel", "mobile", "fax"],
            "price": ["price", "cost", "amount", "total", "fee"],
            "date": ["date", "time", "created", "updated", "published"],
            "rating": ["rating", "score", "stars"],
        }

        for field_type, keywords in type_keywords.items():
            for keyword in keywords:
                if keyword in field_lower:
                    return field_type

        return "text"

    def _create_reverify_action(
        self,
        field: ExtractedField,
        result: VerificationResult,
    ) -> Action:
        """Create an action to handle failed verification."""
        if result.confidence < 0.3:
            # Very low confidence - suggest re-extraction
            return Action(
                action_type=ActionType.EXTRACT_FIELD,
                parameters={
                    "field_name": field.field_name,
                    "reason": "Re-extracting due to verification failure",
                },
                reasoning=f"Verification failed with issues: {result.issues}",
                confidence=0.6,
                agent_id=self.agent_id,
            )
        else:
            # Moderate confidence - try cross-validation
            return Action(
                action_type=ActionType.VERIFY_FACT,
                parameters={
                    "claim": f"{field.field_name}: {field.value}",
                    "sources": None,
                    "confidence_threshold": self.min_confidence,
                },
                reasoning=f"Attempting cross-validation for {field.field_name}",
                confidence=0.5,
                agent_id=self.agent_id,
            )

    def add_validation_rule(
        self,
        field_type: str,
        rule: dict[str, Any],
    ) -> None:
        """
        Add a custom validation rule.
        
        Args:
            field_type: The field type this rule applies to.
            rule: The validation rule dictionary.
        """
        if field_type not in self._validation_rules:
            self._validation_rules[field_type] = []
        self._validation_rules[field_type].append(rule)

    def get_verification_history(self) -> list[dict[str, Any]]:
        """Get verification history as dictionaries."""
        return [r.to_dict() for r in self._verification_history]

    def reset(self) -> None:
        """Reset the verifier state."""
        super().reset()
        self._verification_history.clear()
