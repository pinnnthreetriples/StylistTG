from __future__ import annotations

from collections.abc import Iterator
from copy import deepcopy
from typing import Any, cast

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.schemas import ApiErrorRead


def build_custom_openapi(app: FastAPI) -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        routes=app.routes,
    )
    _document_standard_error_responses(openapi_schema)
    _strip_query_parameter_nullability(openapi_schema)
    app.openapi_schema = openapi_schema
    return openapi_schema


def _api_error_schema_components() -> dict[str, Any]:
    schema = ApiErrorRead.model_json_schema(ref_template="#/components/schemas/{model}")
    defs = cast(dict[str, Any], schema.pop("$defs", {}))
    return {**defs, "ApiErrorRead": schema}


def _iter_openapi_operations(openapi_schema: dict[str, Any]) -> Iterator[dict[str, Any]]:
    paths = cast(dict[str, Any], openapi_schema.get("paths", {}))
    for path_item in paths.values():
        if not isinstance(path_item, dict):
            continue
        path_item_dict = cast(dict[str, Any], path_item)
        for raw_operation in path_item_dict.values():
            if not isinstance(raw_operation, dict):
                continue
            yield cast(dict[str, Any], raw_operation)


def _document_standard_error_responses(openapi_schema: dict[str, Any]) -> None:
    components = cast(dict[str, Any], openapi_schema.setdefault("components", {}))
    schemas = cast(dict[str, Any], components.setdefault("schemas", {}))
    schemas.update(_api_error_schema_components())
    bad_request_response = {
        "description": "Bad Request",
        "content": {"application/json": {"schema": {"type": "object"}}},
    }
    not_found_response = {
        "description": "Not Found",
        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ApiErrorRead"}}},
    }
    conflict_response = {
        "description": "Conflict",
        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ApiErrorRead"}}},
    }
    for operation in _iter_openapi_operations(openapi_schema):
        if "responses" not in operation:
            continue
        responses = cast(dict[str, Any], operation["responses"])
        responses.setdefault("400", deepcopy(bad_request_response))
        responses.setdefault("404", deepcopy(not_found_response))
        responses.setdefault("409", deepcopy(conflict_response))


def _strip_query_parameter_nullability(openapi_schema: dict[str, Any]) -> None:
    for operation in _iter_openapi_operations(openapi_schema):
        parameters = operation.get("parameters", [])
        if not isinstance(parameters, list):
            continue
        for raw_parameter in cast(list[Any], parameters):
            if not isinstance(raw_parameter, dict):
                continue
            parameter = cast(dict[str, Any], raw_parameter)
            if parameter.get("in") != "query":
                continue
            schema = parameter.get("schema")
            if isinstance(schema, dict):
                _remove_null_schema_variant(cast(dict[str, Any], schema))


def _remove_null_schema_variant(schema: dict[str, Any]) -> None:
    any_of = schema.get("anyOf")
    if not isinstance(any_of, list):
        return
    any_of_variants = cast(list[Any], any_of)
    non_null_variants: list[Any] = [
        variant for variant in any_of_variants if not _is_null_schema_variant(variant)
    ]
    if len(non_null_variants) == 1 and isinstance(non_null_variants[0], dict):
        schema.pop("anyOf")
        schema.update(cast(dict[str, Any], non_null_variants[0]))
    elif len(non_null_variants) != len(any_of_variants):
        schema["anyOf"] = non_null_variants


def _is_null_schema_variant(variant: Any) -> bool:
    if not isinstance(variant, dict):
        return False
    return cast(dict[str, Any], variant).get("type") == "null"
