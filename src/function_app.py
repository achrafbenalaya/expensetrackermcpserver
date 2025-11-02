import json
import logging
import os

import azure.functions as func

try:
    # prefer relative import when running as package
    from .expense_tracker_nopandas import ExpenseTracker
except Exception:
    from expense_tracker_nopandas import ExpenseTracker

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

# Constants for the Azure Blob Storage container, file, and blob path
_SNIPPET_NAME_PROPERTY_NAME = "snippetname"
_SNIPPET_PROPERTY_NAME = "snippet"
_BLOB_PATH = "snippets/{mcptoolargs." + _SNIPPET_NAME_PROPERTY_NAME + "}.json"


class ToolProperty:
    def __init__(self, property_name: str, property_type: str, description: str):
        self.propertyName = property_name
        self.propertyType = property_type
        self.description = description

    def to_dict(self):
        return {
            "propertyName": self.propertyName,
            "propertyType": self.propertyType,
            "description": self.description,
        }


# Define the tool properties using the ToolProperty class
tool_properties_save_snippets_object = [
    ToolProperty(_SNIPPET_NAME_PROPERTY_NAME, "string", "The name of the snippet."),
    ToolProperty(_SNIPPET_PROPERTY_NAME, "string", "The content of the snippet."),
]

tool_properties_get_snippets_object = [
    ToolProperty(_SNIPPET_NAME_PROPERTY_NAME, "string", "The name of the snippet.")
]

# Expense tracker tool properties
tool_properties_add_expense = [
    ToolProperty("amount", "number", "The expense amount"),
    ToolProperty("category", "string", "The expense category (e.g., Food, Transport, Entertainment)"),
    ToolProperty("description", "string", "A description of the expense"),
    ToolProperty("date", "string", "The date of the expense in YYYY-MM-DD format or 'today'"),
]

tool_properties_get_expenses = [
    ToolProperty("month", "string", "The month in YYYY-MM format (e.g., 2025-11)"),
    ToolProperty("category", "string", "Optional category filter"),
]

tool_properties_get_budget_status = [
    ToolProperty("month", "string", "The month in YYYY-MM format (e.g., 2025-11)"),
]

tool_properties_get_spending_summary = [
    ToolProperty("start_date", "string", "Start date in YYYY-MM-DD format"),
    ToolProperty("end_date", "string", "End date in YYYY-MM-DD format"),
]

tool_properties_categorize_expense = [
    ToolProperty("description", "string", "The expense description to categorize"),
]

# Convert the tool properties to JSON
tool_properties_save_snippets_json = json.dumps([prop.to_dict() for prop in tool_properties_save_snippets_object])
tool_properties_get_snippets_json = json.dumps([prop.to_dict() for prop in tool_properties_get_snippets_object])
tool_properties_add_expense_json = json.dumps([prop.to_dict() for prop in tool_properties_add_expense])
tool_properties_get_expenses_json = json.dumps([prop.to_dict() for prop in tool_properties_get_expenses])
tool_properties_get_budget_status_json = json.dumps([prop.to_dict() for prop in tool_properties_get_budget_status])
tool_properties_get_spending_summary_json = json.dumps([prop.to_dict() for prop in tool_properties_get_spending_summary])
tool_properties_categorize_expense_json = json.dumps([prop.to_dict() for prop in tool_properties_categorize_expense])


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="hello_mcp",
    description="Hello world.",
    toolProperties="[]",
)
def hello_mcp(context) -> None:
    """
    A simple function that returns a greeting message.

    Args:
        context: The trigger context (not used in this function).

    Returns:
        str: A greeting message.
    """
    return "Hello I am MCPTool!"


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="get_snippet",
    description="Retrieve a snippet by name.",
    toolProperties=tool_properties_get_snippets_json,
)
@app.generic_input_binding(arg_name="file", type="blob", connection="AzureWebJobsStorage", path=_BLOB_PATH)
def get_snippet(file: func.InputStream, context) -> str:
    """
    Retrieves a snippet by name from Azure Blob Storage.

    Args:
        file (func.InputStream): The input binding to read the snippet from Azure Blob Storage.
        context: The trigger context containing the input arguments.

    Returns:
        str: The content of the snippet or an error message.
    """
    snippet_content = file.read().decode("utf-8")
    logging.info(f"Retrieved snippet: {snippet_content}")
    return snippet_content


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="save_snippet",
    description="Save a snippet with a name.",
    toolProperties=tool_properties_save_snippets_json,
)
@app.generic_output_binding(arg_name="file", type="blob", connection="AzureWebJobsStorage", path=_BLOB_PATH)
def save_snippet(file: func.Out[str], context) -> str:
    content = json.loads(context)
    snippet_name_from_args = content["arguments"][_SNIPPET_NAME_PROPERTY_NAME]
    snippet_content_from_args = content["arguments"][_SNIPPET_PROPERTY_NAME]

    if not snippet_name_from_args:
        return "No snippet name provided"

    if not snippet_content_from_args:
        return "No snippet content provided"

    file.set(snippet_content_from_args)
    logging.info(f"Saved snippet: {snippet_content_from_args}")
    return f"Snippet '{snippet_content_from_args}' saved successfully"


# ---------------- Expense Tracker MCP tools ----------------
_tracker = None


def _get_tracker() -> ExpenseTracker:
    global _tracker
    if _tracker is None:
        _tracker = ExpenseTracker()
    return _tracker


def _parse_date_input(date_input: str) -> str:
    """Parse flexible date inputs like 'today' or YYYY-MM-DD."""
    from datetime import datetime
    
    if not date_input:
        return None
        
    date_input_lower = date_input.lower().strip()
    
    if date_input_lower == "today":
        return datetime.now().strftime("%Y-%m-%d")
    elif date_input_lower == "yesterday":
        from datetime import timedelta
        return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        return date_input


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="get_expenses",
    description="Retrieve expenses filtered by month and optional category.",
    toolProperties=tool_properties_get_expenses_json,
)
def get_expenses(context) -> str:
    """
    Retrieve expenses filtered by month and optional category.
    
    Args:
        context: JSON string with arguments: {"month": "YYYY-MM", "category": "optional"}
    
    Returns:
        JSON string with expenses list or error
    """
    try:
        content = json.loads(context)
        month = content.get("arguments", {}).get("month")
        category = content.get("arguments", {}).get("category")
        
        if not month:
            return json.dumps({"ok": False, "error": "month is required (YYYY-MM format, e.g., 2025-11)"})
        
        result = _get_tracker().get_expenses(month=month, category=category)
        return json.dumps({
            "ok": True, 
            "month": month,
            "category": category or "all",
            "count": len(result) if isinstance(result, list) else 0,
            "result": result
        })
    except Exception as e:
        logging.exception("get_expenses failed")
        return json.dumps({"ok": False, "error": str(e)})


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="add_expense",
    description="Add a new expense entry.",
    toolProperties=tool_properties_add_expense_json,
)
def add_expense(context) -> str:
    """
    Add a new expense entry.
    
    Args:
        context: JSON string with arguments: 
                 {"amount": number, "category": string, "description": string, "date": string}
    
    Returns:
        JSON string with success status or error
    """
    try:
        content = json.loads(context)
        args = content.get("arguments", {})
        
        amount = args.get("amount")
        category = args.get("category")
        description = args.get("description")
        date_input = args.get("date")
        
        # Validate required fields
        missing = []
        if amount in (None, ""):
            missing.append("amount")
        if not category:
            missing.append("category")
        if not description:
            missing.append("description")
        if not date_input:
            missing.append("date")
            
        if missing:
            return json.dumps({
                "ok": False, 
                "error": f"Missing required fields: {', '.join(missing)}"
            })
        
        # Validate amount
        try:
            amount = float(amount)
            if amount <= 0:
                return json.dumps({"ok": False, "error": "Amount must be a positive number"})
        except (ValueError, TypeError):
            return json.dumps({"ok": False, "error": "Invalid amount format"})
        
        # Parse date (handles 'today' and other formats)
        date_str = _parse_date_input(date_input)
        
        # Add the expense
        row = _get_tracker().add_expense(
            amount=amount, 
            category=category, 
            description=description, 
            date_str=date_str
        )
        
        return json.dumps({
            "ok": True, 
            "message": "Expense added successfully",
            "expense": {
                "amount": amount,
                "category": category,
                "description": description,
                "date": date_str
            },
            "result": row
        })
    except Exception as e:
        logging.exception("add_expense failed")
        return json.dumps({"ok": False, "error": str(e)})


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="get_budget_status",
    description="Get remaining budget for a month.",
    toolProperties=tool_properties_get_budget_status_json,
)
def get_budget_status(context) -> str:
    """
    Get remaining budget for a month.
    
    Args:
        context: JSON string with arguments: {"month": "YYYY-MM"}
    
    Returns:
        JSON string with budget status or error
    """
    try:
        content = json.loads(context)
        month = content.get("arguments", {}).get("month")
        
        if not month:
            return json.dumps({
                "ok": False, 
                "error": "month is required (YYYY-MM format, e.g., 2025-11)"
            })
        
        result = _get_tracker().get_budget_status(month=month)
        return json.dumps({"ok": True, "month": month, "result": result})
    except Exception as e:
        logging.exception("get_budget_status failed")
        return json.dumps({"ok": False, "error": str(e)})


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="get_spending_summary",
    description="Summarize spending between two dates.",
    toolProperties=tool_properties_get_spending_summary_json,
)
def get_spending_summary(context) -> str:
    """
    Summarize spending between two dates.
    
    Args:
        context: JSON string with arguments: {"start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"}
    
    Returns:
        JSON string with spending summary or error
    """
    try:
        content = json.loads(context)
        args = content.get("arguments", {})
        start_date = args.get("start_date")
        end_date = args.get("end_date")
        
        if not start_date or not end_date:
            return json.dumps({
                "ok": False, 
                "error": "start_date and end_date are required (YYYY-MM-DD format)"
            })
        
        result = _get_tracker().get_spending_summary(start_date=start_date, end_date=end_date)
        return json.dumps({
            "ok": True, 
            "start_date": start_date,
            "end_date": end_date,
            "result": result
        })
    except Exception as e:
        logging.exception("get_spending_summary failed")
        return json.dumps({"ok": False, "error": str(e)})


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="categorize_expense",
    description="Auto-categorize expense by description.",
    toolProperties=tool_properties_categorize_expense_json,
)
def categorize_expense(context) -> str:
    """
    Auto-categorize an expense by its description.
    
    Args:
        context: JSON string with arguments: {"description": string}
    
    Returns:
        JSON string with suggested category or error
    """
    try:
        content = json.loads(context)
        description = content.get("arguments", {}).get("description", "")
        
        if not description:
            return json.dumps({"ok": False, "error": "description is required"})
        
        result = _get_tracker().categorize_expense(description)
        return json.dumps({
            "ok": True, 
            "description": description,
            "category": result,
            "result": result
        })
    except Exception as e:
        logging.exception("categorize_expense failed")
        return json.dumps({"ok": False, "error": str(e)})