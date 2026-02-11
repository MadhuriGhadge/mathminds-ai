from typing import Any, Dict, List, Optional, Tuple

class AnswerValidator:
    """
    Validates AI-generated answers against quality and safety standards.
    """

    def __init__(self, confidence_threshold: float = 0.5):
        """
        Initialize the AnswerValidator.

        Args:
            confidence_threshold: Minimum confidence score required. Defaults to 0.5.
        """
        self.confidence_threshold = confidence_threshold
        self.required_fields = ["latex", "reasoning", "final_answer", "confidence_score"]

    def validate(self, response: Dict[str, Any], is_math_problem: bool = True) -> Tuple[bool, List[str]]:
        """
        Validates the AI response.

        Args:
            response: The JSON response dictionary from the AI.
            is_math_problem: Whether the input was identified as a math problem.
                             If True, checks for LaTeX content.

        Returns:
            Tuple[bool, List[str]]: (IsValid, List of error reasons)
        """
        errors = []

        # 1. Check required fields
        for field in self.required_fields:
            if field not in response:
                errors.append(f"Missing required field: {field}")
        
        if errors:
            return False, errors

        # 2. check for hallucinated/empty content
        # sometimes models succeed but return empty strings
        if not response.get("final_answer") or str(response.get("final_answer")).strip() == "":
             errors.append("Final answer is empty.")
        
        if not response.get("reasoning") or str(response.get("reasoning")).strip() == "":
             errors.append("Reasoning is empty.")

        # 3. Verify LaTeX presence for math problems
        # We assume 'latex' field should contain some latex-like distinct characters if it's a math problem
        # or at least not be empty.
        if is_math_problem:
            latex_content = response.get("latex", "")
            if not latex_content or str(latex_content).strip() == "":
                errors.append("LaTeX content is missing for a math problem.")
            # Optional: heuristic check for common latex symbols if we want to be stricter
            # if "\\" not in latex_content and "$" not in latex_content:
            #     errors.append("LaTeX content does not appear to contain valid LaTeX syntax.")

        # 4. Confidence threshold check
        try:
            score = float(response.get("confidence_score", 0.0))
            if score < self.confidence_threshold:
                errors.append(f"Confidence score {score} is below threshold {self.confidence_threshold}.")
        except (ValueError, TypeError):
             errors.append("Invalid confidence score format.")

        return len(errors) == 0, errors
