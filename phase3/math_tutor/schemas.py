"""function_declarations = [
    {
        "name": "multiply",
        "description": "Multiply two integers",
        "parameters": {
            "type": "object",
            "properties": {
                "a": {"type": "integer"},
                "b": {"type": "integer"}
            },
            "required": ["a", "b"]
        }
    }
]
""" 

function_declarations = [
    {
        "name": "convert_image_to_latex",
        "description": "Convert a math image into LaTeX",
        "parameters": {
            "type": "object",
            "properties": {
                "image_description": {
                    "type": "string",
                    "description": "Math expression extracted from the image"
                }
            },
            "required": ["image_description"]
        }
    },

    {
        "name": "solve_mathematical_problem",
        "description": "Solve a mathematical problem step-by-step",
        "parameters": {
            "type": "object",
            "properties": {
                "problem": {
                    "type": "string",
                    "description": "Math problem to solve"
                }
            },
            "required": ["problem"]
        }
    },
    {
        "name": "explain_concept",
        "description": "Explain a math concept in simple terms",
        "parameters": {
            "type": "object",
            "properties": {
                "concept": {
                    "type": "string",
                    "description": "Concept name"
                }
            },
            "required": ["concept"]
        }
    }
]
