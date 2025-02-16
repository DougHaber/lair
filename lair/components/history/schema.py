import jsonschema


MESSAGES_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "role": {
                "type": "string",
                "enum": ["system", "user", "assistant", "tool"]
            },
            "content": {
                "type": ["string", "null"],
                "description": "The primary text content of the message. Null if tool call or file attachment is present."
            },
            "tool_calls": {
                "type": ["array", "null"],
                "description": "List of tools called by the assistant.",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "Unique identifier for the tool call."
                        },
                        "name": {
                            "type": "string",
                            "description": "The tool's name being invoked."
                        },
                        "arguments": {
                            "type": "object",
                            "description": "Arguments passed to the tool.",
                            "additionalProperties": True
                        }
                    },
                    "required": ["id", "name", "arguments"]
                }
            },
            "refusal": {
                "type": ["string", "null"],
                "description": "A message explaining why the assistant refused to respond."
            },
            "file_attachments": {
                "type": ["array", "null"],
                "description": "List of file attachments included in the message.",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "Unique identifier for the attached file."
                        },
                        "name": {
                            "type": "string",
                            "description": "Original filename."
                        },
                        "mime_type": {
                            "type": "string",
                            "description": "MIME type of the file."
                        },
                        "size": {
                            "type": "integer",
                            "description": "Size of the file in bytes."
                        },
                        "url": {
                            "type": "string",
                            "format": "uri",
                            "description": "A URL where the file can be accessed (if applicable)."
                        }
                    },
                    "required": ["id", "name", "mime_type", "size"]
                }
            }
        },
        "required": ["role"],
        "anyOf": [
            {"required": ["content"]},
            {"required": ["tool_calls"]},
            {"required": ["refusal"]},
            {"required": ["file_attachments"]}
        ]
    }
}


def validate_messages(messages):
    """
    Validate a list of messages
    Raise an exception if it is invalid
    """
    try:
        jsonschema.validate(instance=messages, schema=MESSAGES_SCHEMA)
    except jsonschema.exceptions.ValidationError as error:
        # ValidationErrors when stringified return the entire schema
        # This rewrites the error message to only be the error and adds in a path
        if error.path:
            path_list = list(error.path)  # Convert to a list explicitly
            error_location = f"[{path_list[0]}]"

            if len(path_list) > 1:
                error_location += "." + ".".join(str(p) for p in path_list[1:])
        else:
            error_location = "root"

        raise jsonschema.ValidationError(f"Validation failed at '{error_location}': {error.message}")
