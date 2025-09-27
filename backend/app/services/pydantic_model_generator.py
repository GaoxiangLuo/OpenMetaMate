import logging
from collections.abc import MutableMapping
from typing import Any, Dict, List, Optional

from pydantic import Field, create_model

from app.models.llm import LLMExtractionField

logger = logging.getLogger(__name__)

# A mapping function for Data Type in CSV to Python type
type_map = {
    "Text": str,
    "Numeric": float,
    "Boolean": bool,
}


def set_in_hierarchy(path_parts, node, data_type, definition):
    """
    Recursively set the field in the hierarchy dictionary.
    path_parts is a list of path tokens.
    node is the current level of the hierarchy dictionary.
    """
    if len(path_parts) == 1:
        # This is the final field
        field_name = path_parts[0]
        field_name = field_name.lower().replace(" ", "_")
        node[field_name] = (data_type, definition)
    else:
        # This is a class node
        class_name = path_parts[0]
        class_name_key = class_name.lower().replace(" ", "_")
        if class_name_key not in node:
            node[class_name_key] = {}
        set_in_hierarchy(path_parts[1:], node[class_name_key], data_type, definition)


def create_models(hierarchy_dict, class_name="Root"):
    """
    Recursively create models from the hierarchy dictionary.
    If a value is a tuple (data_type, definition), it is a field.
    If a value is a dict, it is a nested model.
    """
    fields = {}
    for k, v in hierarchy_dict.items():
        if isinstance(v, dict):
            # nested class
            nested_model = create_models(v, class_name=k.capitalize())
            fields[k] = (
                Optional[nested_model],
                Field(None, description=f"Nested group for {k.replace('_', ' ').title()}"),
            )
        elif v is not None:
            # v should be (data_type, definition) tuple
            try:
                if isinstance(v, tuple) and len(v) == 2:
                    dt_str, definition = v
                else:
                    logger.warning(
                        f"⚠️ Unexpected value type for field '{k}': {type(v)}, "
                        "using default Text type"
                    )
                    dt_str, definition = "Text", ""
            except (ValueError, TypeError) as e:
                logger.warning(f"⚠️ Error unpacking field '{k}': {e}, using default Text type")
                dt_str, definition = "Text", ""

            if dt_str not in type_map:
                logger.warning(f"⚠️ Unknown data type '{dt_str}' for '{k}', defaulting to Text")
                dt_str = "Text"

            field_description = definition or ""
            if dt_str:
                type_hint = f"Expected type: {dt_str}."
                field_description = f"{field_description} {type_hint}".strip()

            fields[k] = (
                Optional[LLMExtractionField],
                Field(None, description=field_description),
            )
        else:
            logger.warning(f"⚠️ Skipping field '{k}' with None value")
    return create_model(class_name, **fields)


def coding_scheme_items_to_pydantic_model(coding_scheme_items: List[Dict[str, Any]]):
    """
    Convert a list of CodingSchemeItem dicts to a Pydantic model.

    Args:
        coding_scheme_items: List of CodingSchemeItem dicts

    Returns:
        Pydantic model class
    """
    if not coding_scheme_items:
        logger.warning("⚠️ No coding scheme items provided")
        return None

    logger.info(f"🏗️ Building Pydantic model from {len(coding_scheme_items)} items")

    # Initialize hierarchy dictionary
    hierarchy = {}

    try:
        # Process each item in the coding scheme
        included_count = 0
        for item in coding_scheme_items:
            include_extraction = item.get(
                "include_in_extraction", item.get("includeInExtraction", False)
            )
            if include_extraction:
                name = item.get("name", "").strip()
                if not name:
                    logger.warning("⚠️ Skipping item with no name")
                    continue

                data_type = item.get("data_type", item.get("dataType", "Text")).strip()
                definition = item.get("description", "").strip()

                if data_type not in type_map:
                    logger.warning(f"⚠️ Unknown data type '{data_type}' for '{name}', using Text")
                    data_type = "Text"

                parts = name.split("/")
                logger.debug(f"🔧 Adding field: {name} ({data_type})")

                # Set in hierarchy
                set_in_hierarchy(parts, hierarchy, data_type, definition)
                included_count += 1

        logger.info(f"📊 Processed {included_count} fields for extraction")

    except Exception as e:
        logger.error(f"❌ Error processing coding scheme items: {str(e)}", exc_info=True)
        return None

    try:
        DynamicModel = create_models(hierarchy)
        DynamicModel.model_rebuild()
        logger.info("✅ Successfully created Pydantic model")
        return DynamicModel
    except Exception as e:
        logger.error(f"❌ Error creating Pydantic model: {str(e)}", exc_info=True)
        return None


def flatten_json(nested_json, parent_key="", separator="/"):
    """
    Flatten a nested JSON object into a dictionary with compound keys.

    Args:
        nested_json: A nested dictionary or list of nested dictionaries
        parent_key: Base key for nested elements (used in recursion)
        separator: Character to join nested keys (default '/')

    Returns:
        A flattened dictionary or list of flattened dictionaries
    """
    if nested_json is None:
        logger.debug("📦 No JSON to flatten")
        return {}

    items = []

    # Handle the case where input is a list of dictionaries
    if isinstance(nested_json, list):
        return [flatten_json(item, parent_key, separator) for item in nested_json]

    # Iterate through key-value pairs in the dictionary
    for key, value in nested_json.items():
        new_key = f"{parent_key}{separator}{key}" if parent_key else key

        if isinstance(value, MutableMapping) or isinstance(value, list):
            # If value is another dictionary or list, recurse
            if isinstance(value, dict):
                items.extend(flatten_json(value, new_key, separator).items())
            # Handle lists - either recurse if they contain dictionaries, or store as is
            elif isinstance(value, list):
                if value and isinstance(value[0], dict):
                    # If list contains dictionaries, flatten each one
                    for i, item in enumerate(value):
                        items.extend(
                            flatten_json(item, f"{new_key}{separator}{i}", separator).items()
                        )
                else:
                    items.append((new_key, value))
        else:
            # For non-nested values, add them directly
            items.append((new_key, value))

    return dict(items)
