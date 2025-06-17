import json

def create_task_response(requestId: str, task: str, status: str, message: str = "") -> str:
    """Generate standardized JSON response for task status updates."""
    response = {
        "RequestId": requestId,
        "Task": task,
        "Status": status,
        "Message": message,
    }
    return json.dumps(response)
