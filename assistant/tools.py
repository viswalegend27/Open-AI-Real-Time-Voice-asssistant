mahindra_vehicles_schema = {
    "name": "list_mahindra_vehicles",
    "description": "Retrieve a list of currently available Mahindra passenger vehicles in India with details.",
    "parameters": {
        "type": "object",
        "properties": {
            "vehicles": {
                "type": "object",
                "description": "Dictionary mapping model name to details",
                "additionalProperties": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "description": "e.g. SUV, EV"
                        },
                        "segment": {
                            "type": "string",
                            "description": "e.g. premium, compact"
                        },
                        "features": {
                            "type": "array",
                            "description": "Notable features and highlights",
                            "items": {"type": "string"}
                        }
                    },
                    "required": ["type", "segment", "features"]
                }
            }
        },
        "required": ["vehicles"]
    }
}