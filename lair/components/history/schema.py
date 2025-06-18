import jsonschema

MESSAGES_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "role": {"type": "string", "enum": ["system", "user", "assistant", "tool"]},
            "content": {
                "oneOf": [
                    {"type": "string"},
                    {
                        "type": "array",
                        "description": "Structured content with text and/or image URLs.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "enum": ["text", "image_url"],
                                    "description": "Defines the type of content block.",
                                },
                                "text": {"type": "string", "description": "Text content, present if type is 'text'."},
                                "image_url": {
                                    "type": "object",
                                    "description": "Image content, present if type is 'image_url'.",
                                    "properties": {
                                        "url": {
                                            "type": "string",
                                            "format": "uri",
                                            "description": "A valid URI for the image, including base64-encoded data URLs.",
                                        }
                                    },
                                    "required": ["url"],
                                },
                            },
                            "required": ["type"],
                            "anyOf": [{"required": ["text"]}, {"required": ["image_url"]}],
                        },
                    },
                ],
                "description": "The primary text content of the message, or structured content (text and images).",
            },
            "tool_calls": {
                "type": ["array", "null"],
                "description": "List of tools called by the assistant.",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "Unique identifier for the tool call."},
                        "type": {
                            "type": "string",
                            "enum": ["function"],
                            "description": "The type of tool call (e.g., function).",
                        },
                        "function": {
                            "type": "object",
                            "description": "Function call details.",
                            "properties": {
                                "name": {"type": "string", "description": "The function's name being invoked."},
                                "arguments": {
                                    "type": "string",
                                    "description": "Arguments passed to the function, typically as a JSON string.",
                                },
                            },
                            "required": ["name", "arguments"],
                        },
                        "index": {"type": "integer", "description": "Index of the tool call in the sequence."},
                    },
                    "required": ["id", "type", "function"],
                },
            },
            "refusal": {
                "type": ["string", "null"],
                "description": "A message explaining why the assistant refused to respond.",
            },
            "file_attachments": {
                "type": ["array", "null"],
                "description": "List of file attachments included in the message.",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "Unique identifier for the attached file."},
                        "name": {"type": "string", "description": "Original filename."},
                        "mime_type": {"type": "string", "description": "MIME type of the file."},
                        "size": {"type": "integer", "description": "Size of the file in bytes."},
                        "url": {
                            "type": "string",
                            "format": "uri",
                            "description": "A URL where the file can be accessed (if applicable).",
                        },
                    },
                    "required": ["id", "name", "mime_type", "size"],
                },
            },
        },
        "required": ["role"],
        "anyOf": [
            {"required": ["content"]},
            {"required": ["tool_calls"]},
            {"required": ["refusal"]},
            {"required": ["file_attachments"]},
        ],
    },
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
