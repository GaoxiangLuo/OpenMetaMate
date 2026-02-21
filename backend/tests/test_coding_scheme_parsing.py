"""Tests verifying that coding scheme names with spaces around '/' are parsed
consistently across the model generator and the key-lookup utility."""

import pytest

from app.core.utils import get_expected_key
from app.services.pydantic_model_generator import (
    coding_scheme_items_to_pydantic_model,
    flatten_json,
    set_in_hierarchy,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_item(name: str, *, description: str = "", include: bool = True) -> dict:
    """Shortcut to build a coding-scheme item dict."""
    return {
        "id": "1",
        "name": name,
        "data_type": "Text",
        "description": description,
        "include_in_extraction": include,
    }


def _model_field_names(model_cls) -> set[str]:
    """Return the set of field names on a Pydantic model class."""
    return set(model_cls.model_fields.keys())


# ---------------------------------------------------------------------------
# set_in_hierarchy
# ---------------------------------------------------------------------------


class TestSetInHierarchy:
    """Unit tests for the set_in_hierarchy helper."""

    def test_simple_name(self):
        node = {}
        set_in_hierarchy(["Sample Size"], node, None, "desc")
        assert "sample_size" in node

    def test_spaces_around_slash_parts(self):
        """The bug: ' Treatment ' should produce 'treatment', not '_treatment_'."""
        node = {}
        set_in_hierarchy([" Treatment "], node, None, "desc")
        assert "treatment" in node
        assert "_treatment_" not in node
        assert "_treatment" not in node
        assert "treatment_" not in node

    def test_nested_hierarchy_with_spaces(self):
        node = {}
        set_in_hierarchy([" Study ", " Design "], node, None, "desc")
        assert "study" in node
        assert "design" in node["study"]

    def test_multiple_internal_spaces(self):
        node = {}
        set_in_hierarchy(["Sample  Size"], node, None, "desc")
        assert "sample_size" in node


# ---------------------------------------------------------------------------
# get_expected_key
# ---------------------------------------------------------------------------


class TestGetExpectedKey:
    def test_no_slash(self):
        assert get_expected_key("Sample Size") == "sample_size"

    def test_slash_no_spaces(self):
        assert get_expected_key("Study/Design") == "study/design"

    def test_slash_with_spaces(self):
        """Core regression: spaces around '/' must not produce stray underscores."""
        assert get_expected_key("Study / Design") == "study/design"

    def test_multiple_levels_with_spaces(self):
        assert get_expected_key("A / B / C") == "a/b/c"

    def test_empty_string(self):
        assert get_expected_key("") == ""

    def test_trailing_slash(self):
        result = get_expected_key("Study/")
        assert result == "study"

    def test_leading_slash(self):
        result = get_expected_key("/Study")
        assert result == "study"


# ---------------------------------------------------------------------------
# coding_scheme_items_to_pydantic_model
# ---------------------------------------------------------------------------


class TestCodingSchemeModel:
    def test_flat_field(self):
        items = [_make_item("Sample Size", description="Number of participants")]
        model = coding_scheme_items_to_pydantic_model(items)
        assert model is not None
        assert "sample_size" in _model_field_names(model)

    def test_slash_no_spaces(self):
        items = [_make_item("Study/Design")]
        model = coding_scheme_items_to_pydantic_model(items)
        assert model is not None
        assert "study" in _model_field_names(model)

    def test_slash_with_spaces(self):
        """The reported bug: 'XXX / XXX' with spaces around '/'."""
        items = [_make_item("Treatment / Control")]
        model = coding_scheme_items_to_pydantic_model(items)
        assert model is not None
        fields = _model_field_names(model)
        assert "treatment" in fields
        # Must NOT have leading/trailing underscores
        assert "_treatment" not in fields
        assert "treatment_" not in fields
        assert "_treatment_" not in fields

    def test_deeply_nested_with_spaces(self):
        items = [_make_item("A / B / C")]
        model = coding_scheme_items_to_pydantic_model(items)
        assert model is not None
        # Top level should have 'a'
        assert "a" in _model_field_names(model)

    def test_excluded_items_are_skipped(self):
        items = [_make_item("Skipped", include=False)]
        model = coding_scheme_items_to_pydantic_model(items)
        # No included fields → empty model, but still valid
        assert model is not None
        assert _model_field_names(model) == set()

    def test_empty_list(self):
        assert coding_scheme_items_to_pydantic_model([]) is None


# ---------------------------------------------------------------------------
# Consistency: model field names must match get_expected_key output
# ---------------------------------------------------------------------------


class TestConsistency:
    """The model generator and get_expected_key must agree on field names."""

    @pytest.mark.parametrize(
        "name",
        [
            "Sample Size",
            "Study/Design",
            "Study / Design",
            "Treatment / Control / Dosage",
            "  Outcome  /  Measure  ",
            "A/B/C",
        ],
    )
    def test_model_fields_match_expected_keys(self, name: str):
        """For every coding scheme name, the top-level model field must equal
        the first segment of get_expected_key's output."""
        items = [_make_item(name)]
        model = coding_scheme_items_to_pydantic_model(items)
        assert model is not None

        expected_key = get_expected_key(name)
        top_level_key = expected_key.split("/")[0]
        assert top_level_key in _model_field_names(model), (
            f"name={name!r}: model has {_model_field_names(model)}, "
            f"but get_expected_key produces top-level '{top_level_key}'"
        )


# ---------------------------------------------------------------------------
# flatten_json
# ---------------------------------------------------------------------------


class TestFlattenJson:
    def test_flat_dict(self):
        assert flatten_json({"a": 1, "b": 2}) == {"a": 1, "b": 2}

    def test_nested_dict(self):
        result = flatten_json({"study": {"design": "RCT"}})
        assert result == {"study/design": "RCT"}

    def test_none_input(self):
        assert flatten_json(None) == {}

    def test_list_input(self):
        result = flatten_json([{"a": 1}, {"b": 2}])
        assert result == [{"a": 1}, {"b": 2}]
