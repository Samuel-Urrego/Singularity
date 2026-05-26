"""Tests for Pydantic model generation (dynamic and source modes)."""

from pydantic import BaseModel

from singularity.model_generator import generate_model


class TestDynamicMode:
    """generate_model() in 'dynamic' mode returns a BaseModel subclass."""

    def test_returns_base_model_subclass(self, sample_sp_metadata) -> None:
        """Dynamic mode returns a class that is a BaseModel subclass."""
        model = generate_model(sample_sp_metadata, mode="dynamic")
        assert isinstance(model, type)
        assert issubclass(model, BaseModel)

    def test_fields_match_columns(self, sample_sp_metadata) -> None:
        """Generated model has fields matching column names."""
        model = generate_model(sample_sp_metadata, mode="dynamic")
        field_names = set(model.model_fields.keys())
        assert "order_id" in field_names
        assert "customer_name" in field_names
        assert "order_date" in field_names
        assert "total" in field_names

    def test_nullable_optional(self, sample_sp_metadata) -> None:
        """Nullable columns get Optional types."""
        model = generate_model(sample_sp_metadata, mode="dynamic")
        hint = model.model_fields["customer_name"].annotation
        assert hint is not None

    def test_no_columns(self, no_column_metadata) -> None:
        """Empty columns produce a model with no fields."""
        model = generate_model(no_column_metadata, mode="dynamic")
        assert len(model.model_fields) == 0

    def test_snake_case_convention(self, sample_sp_metadata) -> None:
        """snake_case produces lowercase_underscore names."""
        model = generate_model(
            sample_sp_metadata, mode="dynamic", naming_convention="snake_case"
        )
        assert "order_id" in model.model_fields

    def test_camel_case_convention(self, sample_sp_metadata) -> None:
        """camelCase produces first-lowercase names."""
        model = generate_model(
            sample_sp_metadata, mode="dynamic", naming_convention="camelCase"
        )
        assert "orderId" in model.model_fields

    def test_pascal_case_convention(self, sample_sp_metadata) -> None:
        """PascalCase produces first-uppercase names."""
        model = generate_model(
            sample_sp_metadata, mode="dynamic", naming_convention="PascalCase"
        )
        assert "OrderId" in model.model_fields


class TestSourceMode:
    """generate_model() in 'source' mode returns a valid Python string."""

    def test_returns_string(self, sample_sp_metadata) -> None:
        """Source mode returns a string."""
        result = generate_model(sample_sp_metadata, mode="source")
        assert isinstance(result, str)

    def test_is_valid_python(self, sample_sp_metadata) -> None:
        """The returned string is valid Python syntax."""
        result = generate_model(sample_sp_metadata, mode="source")
        compile(result, "<test>", "exec")

    def test_contains_base_model_import(self, sample_sp_metadata) -> None:
        """Source includes BaseModel import."""
        result = generate_model(sample_sp_metadata, mode="source")
        assert "from pydantic import BaseModel" in result

    def test_contains_class_definition(self, sample_sp_metadata) -> None:
        """Source includes a class definition."""
        result = generate_model(sample_sp_metadata, mode="source")
        assert "class UspGetOrders(BaseModel):" in result

    def test_contains_field_definitions(self, sample_sp_metadata) -> None:
        """Source includes field type annotations."""
        result = generate_model(sample_sp_metadata, mode="source")
        assert "order_id: int" in result or "order_id: Optional[int]" in result
        assert "customer_name" in result
        assert "order_date" in result

    def test_no_columns_passes(self, no_column_metadata) -> None:
        """Empty columns produce a class with 'pass'."""
        result = generate_model(no_column_metadata, mode="source")
        assert "pass" in result
        assert "class UspExecuteOnly(BaseModel):" in result

    def test_optional_for_nullable(self, sample_sp_metadata) -> None:
        """Nullable columns get Optional type in source mode."""
        result = generate_model(sample_sp_metadata, mode="source")
        assert "Optional[int]" in result or "Optional[float]" in result
        assert "Optional" in result

    def test_snake_case_source(self, sample_sp_metadata) -> None:
        """snake_case is applied in source mode."""
        result = generate_model(
            sample_sp_metadata, mode="source", naming_convention="snake_case"
        )
        assert "order_id" in result


class TestAllTypes:
    """All known SQL types map correctly in generated models."""

    def test_all_types_dynamic(self, all_types_metadata) -> None:
        """All type-mapped fields are present in dynamic mode."""
        model = generate_model(all_types_metadata, mode="dynamic")
        assert "int_col" in model.model_fields
        assert "var_char_col" in model.model_fields
        assert "date_time_col" in model.model_fields
        assert "bit_col" in model.model_fields
        assert "decimal_col" in model.model_fields
        assert "guid_col" in model.model_fields
        assert "unknown_col" in model.model_fields

    def test_all_types_source(self, all_types_metadata) -> None:
        """All type-mapped fields are present in source mode."""
        result = generate_model(all_types_metadata, mode="source")
        for field in ("int_col", "var_char_col", "date_time_col", "bit_col", "decimal_col"):
            assert field in result
