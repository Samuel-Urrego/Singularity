"""Tests for SQL field name sanitization."""


from singularity.model_generator import sanitize_field_name


class TestSanitizeFieldName:
    """sanitize_field_name() converts SQL identifiers to valid Python field names."""

    # -- Basic transformations ----------------------------------------------

    def test_simple_name(self) -> None:
        """A clean name remains unchanged."""
        assert sanitize_field_name("CustomerId") == "customer_id"

    def test_spaces_to_underscores(self) -> None:
        """Spaces are replaced with underscores."""
        assert sanitize_field_name("Customer Name") == "customer_name"

    def test_dots_to_underscores(self) -> None:
        """Dots are replaced with underscores."""
        assert sanitize_field_name("Sales.OrderId") == "sales_order_id"

    def test_hyphens_to_underscores(self) -> None:
        """Hyphens are replaced with underscores."""
        assert sanitize_field_name("order-id") == "order_id"

    def test_special_chars(self) -> None:
        """Special characters are replaced with underscores."""
        assert sanitize_field_name("Order#Total") == "order_total"

    # -- Parameter prefix handling ------------------------------------------

    def test_strips_at_prefix(self) -> None:
        """Leading @ is stripped."""
        assert sanitize_field_name("@OrderId") == "order_id"

    def test_consecutive_ats(self) -> None:
        """Multiple leading @ are stripped."""
        assert sanitize_field_name("@@Variable") == "variable"

    # -- Reserved word handling ---------------------------------------------

    def test_reserved_word(self) -> None:
        """Reserved words get a 'field_' prefix."""
        assert sanitize_field_name("class") == "field_class"

    def test_reserved_word_and(self) -> None:
        assert sanitize_field_name("and") == "field_and"

    def test_reserved_word_none(self) -> None:
        assert sanitize_field_name("None") == "field_none"

    # -- Leading digit handling ---------------------------------------------

    def test_leading_digit(self) -> None:
        """Names starting with a digit get a 'field_' prefix."""
        assert sanitize_field_name("1stColumn") in ("field_1st_column", "field1stColumn")

    # -- Empty / edge cases -------------------------------------------------

    def test_all_special_chars(self) -> None:
        """A name with only special chars gets the generic name."""
        result = sanitize_field_name("@@")
        assert result == "field"

    # -- Naming conventions -------------------------------------------------

    def test_snake_case_default(self) -> None:
        """Default convention is snake_case."""
        assert sanitize_field_name("OrderId") == "order_id"

    def test_snake_case_explicit(self) -> None:
        assert sanitize_field_name("OrderId", convention="snake_case") == "order_id"

    def test_camel_case(self) -> None:
        """camelCase convention: first letter lowercase."""
        result = sanitize_field_name("OrderId", convention="camelCase")
        assert result == "orderId"

    def test_camel_case_multi_word(self) -> None:
        result = sanitize_field_name("Customer Order Total", convention="camelCase")
        assert result == "customerOrderTotal"

    def test_pascal_case(self) -> None:
        """PascalCase convention: first letter uppercase."""
        result = sanitize_field_name("OrderId", convention="PascalCase")
        assert result == "OrderId"

    def test_pascal_case_multi_word(self) -> None:
        result = sanitize_field_name("customer_order", convention="PascalCase")
        assert result == "CustomerOrder"

    # -- Mixed scenarios ----------------------------------------------------

    def test_complex_sanitization(self) -> None:
        """Multiple transformations applied together."""
        result = sanitize_field_name("@Customer#E-mail", convention="snake_case")
        assert result == "customer_e_mail"

    def test_pascal_with_underscores(self) -> None:
        """PascalCase with underscore-separated input."""
        result = sanitize_field_name("order_line_item", convention="PascalCase")
        assert result == "OrderLineItem"
