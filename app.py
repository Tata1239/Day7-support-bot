
import json
import logging
import os
import time
import uuid

from flask import Flask, jsonify, request
from llm import call_llm

app = Flask(__name__)

app.config["MAX_CONTENT_LENGTH"] = 16 * 1024

API_KEY = os.getenv("LLM_API_KEY", "")

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    filename="logs/app.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

ORDERS = {
    "10231": {"status": "Shipped", "amount": 1299},
    "10232": {"status": "Delivered", "amount": 799},
    "10233": {"status": "Processing", "amount": 2499},
}

CUSTOMERS = {
    "ravi.kumar@example.com": {
        "name": "Ravi Kumar",
        "phone": "+91 98480 12345",
        "active": True,
    },
    "priya.sharma@example.com": {
        "name": "Priya Sharma",
        "phone": "+91 98765 43210",
        "active": True,
    },
    "priya.s@example.com": {
        "name": "Priya Sharma",
        "phone": "+91 98765 43210",
        "active": True,
    },
}

REFUNDS = []


def get_order_status(order_id):
    order = ORDERS.get(str(order_id))

    if not order:
        return "Order not found"

    return order["status"]


def issue_refund(order_id, amount):
    order_id = str(order_id)

    if order_id not in ORDERS:
        return "Order not found"

    REFUNDS.append(
        {
            "order_id": order_id,
            "amount": amount,
        }
    )

    return "Refund processed"


def delete_customer_account(customer_email):
    customer = CUSTOMERS.get(customer_email)

    if not customer:
        return "Customer not found"

    customer["active"] = False

    return "Account deactivated"


TOOLS = {
    "get_order_status": get_order_status,
    "issue_refund": issue_refund,
    "delete_customer_account": delete_customer_account,
}

ALLOWED_ACTIONS = list(TOOLS.keys())


def validate_customer_email(email):
    if not isinstance(email, str):
        return False

    email = email.strip()

    if len(email) > 254:
        return False

    if "@" not in email:
        return False

    parts = email.split("@")

    if len(parts) != 2:
        return False

    local_part, domain = parts

    if not local_part or not domain:
        return False

    if "." not in domain:
        return False

    return True


def validate_message(message):
    if not isinstance(message, str):
        return False

    message = message.strip()

    if not message:
        return False

    if len(message) > 2000:
        return False

    return True


def validate_action(action, args, customer_email):
    if action not in ALLOWED_ACTIONS:
        return False, "Invalid action"

    if not isinstance(args, dict):
        return False, "Invalid action arguments"

    if action == "get_order_status":
        order_id = str(args.get("order_id", ""))

        if not order_id:
            return False, "Missing order ID"

        # Allow unknown order IDs so the tool can return
        # "Order not found" as the action result.
        return True, None

    if action == "issue_refund":
        order_id = str(args.get("order_id", ""))
        amount = args.get("amount")

        if order_id not in ORDERS:
            return False, "Invalid order ID"

        if not isinstance(amount, (int, float)) or isinstance(amount, bool):
            return False, "Invalid refund amount"

        if amount <= 0:
            return False, "Refund amount must be positive"

        if amount != ORDERS[order_id]["amount"]:
            return False, "Refund amount validation failed"

        # Refunds require human approval.
        return True, "approval_required"

    if action == "delete_customer_account":
        requested_email = args.get("customer_email")

        if requested_email != customer_email:
            return False, "Customer identity validation failed"

        if customer_email not in CUSTOMERS:
            return False, "Customer not found"

        # Account deletion requires human approval.
        return True, "approval_required"

    return False, "Action not permitted"


def estimate_cost(input_tokens, output_tokens):
    input_cost = input_tokens * 0.000001
    output_cost = output_tokens * 0.000002

    return round(input_cost + output_cost, 6)


@app.post("/chat")
def chat():
    request_id = str(uuid.uuid4())
    start_time = time.time()

    model_name = "fake-offline-model"

    input_tokens = 0
    output_tokens = 0
    action = None
    status = "success"

    try:
        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            status = "invalid_request"

            return jsonify(
                {
                    "error": "Invalid JSON request",
                    "request_id": request_id,
                }
            ), 400

        email = data.get("customer_email", "")
        message = data.get("message", "")

        if not validate_customer_email(email):
            status = "invalid_email"

            return jsonify(
                {
                    "error": "Invalid customer email",
                    "request_id": request_id,
                }
            ), 400

        if not validate_message(message):
            status = "invalid_message"

            return jsonify(
                {
                    "error": "Message must be between 1 and 2000 characters",
                    "request_id": request_id,
                }
            ), 400

        customer = CUSTOMERS.get(email)

        if not customer:
            status = "customer_not_found"

            return jsonify(
                {
                    "error": "Customer not found",
                    "request_id": request_id,
                }
            ), 404

        if not customer.get("active", False):
            status = "inactive_customer"

            return jsonify(
                {
                    "error": "Customer account is inactive",
                    "request_id": request_id,
                }
            ), 403

        prompt = (
            "You are a helpful customer support agent.\n"
            "Answer customer questions using the available tools.\n"
            "Never execute unauthorized actions.\n"
            "Customer name: "
            + customer["name"]
            + "\n"
            "Customer message: "
            + message
        )

        text, usage = call_llm(prompt, API_KEY)

        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)

        result = json.loads(text)

        reply = result.get(
            "reply",
            "Unable to process your request.",
        )

        action = result.get("action")
        action_result = None

        if action:
            args = result.get("args", {})

            # Replace placeholder with the request's customer email.
            if action == "delete_customer_account":
                if args.get("customer_email") == "from_request":
                    args["customer_email"] = email

            valid, validation_result = validate_action(
                action,
                args,
                email,
            )

            if not valid:
                action_result = "Action rejected: " + validation_result

                logging.warning(
                    "request_id=%s action=%s status=action_rejected",
                    request_id,
                    action,
                )

            elif validation_result == "approval_required":
                action_result = (
                    "Action requires human approval. "
                    "No action has been executed."
                )

                logging.warning(
                    "request_id=%s action=%s status=approval_required",
                    request_id,
                    action,
                )

            else:
                # Execute only validated, non-sensitive actions.
                action_result = TOOLS[action](**args)

                logging.info(
                    "request_id=%s action=%s status=executed",
                    request_id,
                    action,
                )

        return jsonify(
            {
                "reply": reply,
                "action_result": action_result,
                "request_id": request_id,
            }
        ), 200

    except json.JSONDecodeError:
        status = "invalid_model_response"

        logging.error(
            "request_id=%s status=invalid_model_response",
            request_id,
        )

        return jsonify(
            {
                "error": "Invalid AI response",
                "request_id": request_id,
            }
        ), 500

    except Exception:
        status = "error"

        logging.exception(
            "request_id=%s status=error",
            request_id,
        )

        return jsonify(
            {
                "error": "Internal server error",
                "request_id": request_id,
            }
        ), 500

    finally:
        latency_ms = round(
            (time.time() - start_time) * 1000,
            2,
        )

        estimated_cost = estimate_cost(
            input_tokens,
            output_tokens,
        )

        logging.info(
            "MONITORING request_id=%s model=%s latency_ms=%s "
            "input_tokens=%s output_tokens=%s estimated_cost=%s "
            "action=%s status=%s",
            request_id,
            model_name,
            latency_ms,
            input_tokens,
            output_tokens,
            estimated_cost,
            action,
            status,
        )


@app.errorhandler(413)
def request_too_large(error):
    return jsonify(
        {
            "error": "Request payload too large",
        }
    ), 413


@app.errorhandler(404)
def not_found(error):
    return jsonify(
        {
            "error": "Endpoint not found",
        }
    ), 404


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
    )
