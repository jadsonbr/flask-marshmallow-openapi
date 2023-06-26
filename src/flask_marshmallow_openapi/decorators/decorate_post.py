import functools
from typing import Type

import marshmallow as ma
from openapi_pydantic_models import (
    Locations,
    ParameterObject,
    RequestBodyObject,
    ResponsesObject,
    SecurityRequirementObject,
)

from ..flask_paths import FlaskPathsManager
from ..schemas_registry import SchemasRegistry
from ..securities import Securities
from .helpers import _initial_docs, _update_errors


def post(
    request_schema: Type[ma.Schema],
    response_schema: Type[ma.Schema] | None = None,
    operation_id: str | None = None,
    summary: str | None = None,
    errors: dict[int, str] | None = None,
    headers: list[ParameterObject | dict] | None = None,
    security: Securities = Securities.access_token,
    additional_parameters: list[ParameterObject | dict] | None = None,
):
    """
    Decorator that will inject standard sets of our OpenAPI POST docs into decorated
    method.

    Example:

        import marshmallow as ma
        from flask_marshmallow_openapi import Securities, open_api

        class SchemaOpts(ma.SchemaOpts):
        def __init__(self, meta, *args, **kwargs):
            self.tags = getattr(meta, "tags", [])
            self.url_id_field = getattr(meta, "url_id_field", None)
            super().__init__(meta, *args, **kwargs)

        class BookSchema(ma.Schema):
            OPTIONS_CLASS = SchemaOpts

            class Meta:
                url_id_field = "id"
                tags = ["Books"]
                description = "Schema for Book model"

            id = ma.fields.Integer(as_string=True)
            title = ma.fields.String(
                allow_none=False, metadata={"description": "book.title description"}
            )

        @open_api.post(
            request_schema=BookSchema,
            security=Securities.no_token,
            errors={
                409: "title must be unique!",
                422: "title must be at least 1 character!"
            }
            additional_parameters=[
                {
                    "name": "zomg",
                    "in": "path",
                    "required": True,
                    "allowEmptyValue": False
                }
            ],
            headers=[
                {
                    "name": "X-Foo",
                    "allowEmptyValue": False
                }
            ]
        )
        def create_book(zomg):
            \"\"\"
            description: |
                Long description!
            \"\"\"
    """

    if not response_schema:
        response_schema = request_schema

    if not operation_id:
        operation_id = FlaskPathsManager.generate_operation_id(
            "post", False, response_schema
        )

    open_api_data = _initial_docs(request_schema, with_id_in_path=True)

    open_api_data.operationId = operation_id
    if security != Securities.no_token:
        open_api_data.security = [SecurityRequirementObject({f"{security.name}": []})]

    open_api_data.responses = ResponsesObject()
    # TODO: This convention of having "create" in schema name makes our code smelly,
    # come up with something more explicit
    if "deleted" in SchemasRegistry.schema_name(response_schema).lower():
        open_api_data.responses["204"] = {"description": "Resource was deleted"}
    else:
        open_api_data.responses["201"] = {
            "content": {
                "application/json": {
                    "schema": {"$ref": SchemasRegistry.schema_ref(response_schema)}
                }
            }
        }

    open_api_data.requestBody = RequestBodyObject(
        **{
            "content": {
                "application/json": {
                    "schema": {"$ref": SchemasRegistry.schema_ref(request_schema)}
                }
            }
        }
    )

    if summary:
        open_api_data.summary = summary

    url_id_field = getattr(request_schema.opts, "url_id_field", None)

    # TODO: This convention of having "create" in schema name makes our code smelly,
    # come up with something more explicit
    if (
        url_id_field
        and "create" not in SchemasRegistry.schema_name(request_schema).lower()
    ):
        open_api_data.parameters[0].name = url_id_field
    else:
        open_api_data.parameters = []

    for data in additional_parameters or []:
        if isinstance(data, dict):
            data = ParameterObject(**data)
        open_api_data.parameters.append(data)

    open_api_data.parameters = [_ for _ in open_api_data.parameters if _.name]

    open_api_data.tags = list(
        set(
            getattr(request_schema.opts, "tags", [])
            + getattr(response_schema.opts, "tags", [])
        )
    )

    _update_errors(open_api_data, errors)

    for header in headers or []:
        if isinstance(header, dict):
            header = ParameterObject(**header)
        header.in_ = Locations.header
        open_api_data.parameters.append(header)

    return functools.partial(
        FlaskPathsManager.decorate, open_api_data={"post": open_api_data.dict()}
    )
