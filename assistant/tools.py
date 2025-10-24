# function schema for summarizing Mahindra sales conversations
conversation_summary_schema = {
    "name": "summarize_sales_conversation",
    "description": "Summarize a Mahindra sales conversation and extract key information.",
    "parameters": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Short 1-3 sentence conversation summary"
            },
            "customer_name": {
                "type": ["string", "null"],
                "description": "Extracted customer name or null"
            },
            "contact_info": {
                "type": ["string", "null"],
                "description": "Customer's contact info, such as phone/email, or null"
            },
            "budget_range": {
                "type": ["string", "null"],
                "description": "Budget range mentioned, e.g. '10-15 lakh', or null"
            },
            "vehicle_type": {
                "type": ["string", "null"],
                "description": "Type/class of vehicle (e.g. SUV, MUV, EV) or null"
            },
            "use_case": {
                "type": ["string", "null"],
                "description": "Intended use (family, business, etc) or null"
            },
            "priority_features": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of prioritized features"
            },
            "recommended_vehicles": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of vehicle models recommended"
            },
            "next_actions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Suggested next followup actions"
            },
            "sentiment": {
                "type": "string",
                "description": "Customer sentiment (positive/neutral/negative)"
            },
            "engagement_score": {
                "type": "integer",
                "description": "Engagement score between 1 and 10"
            },
            "purchase_intent": {
                "type": "string",
                "description": "Purchase intent: high/medium/low"
            }
        },
        "required": ["summary", "customer_name", "contact_info", "budget_range", "vehicle_type", "use_case", "priority_features", "recommended_vehicles", "next_actions", "sentiment", "engagement_score", "purchase_intent"]
    }
}

conversation_analysis_schema = {
    "name": "analyze_customer_preferences",
    "description": "Extract customer preferences, budget, vehicle usage, interest, and priority features from a Mahindra sales conversation.",
    "parameters": {
        "type": "object",
        "properties": {
            "budget": {
                "type": ["string", "null"],
                "description": "Budget mentioned by customer, or null",
            },
            "usage": {
                "type": ["string", "null"],
                "description": "Intended vehicle usage (family, adventure, city, commercial, etc), or null",
            },
            "priority_features": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of prioritized features"
            },
            "vehicle_interest": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of Mahindra vehicle models of customer interest"
            },
            "other_insights": {
                "type": ["string", "null"],
                "description": "Any other explicit or implied user intent or need not fitting above, or null"
            }
        },
        "required": ["budget", "usage", "priority_features", "vehicle_interest", "other_insights"]
    }
}