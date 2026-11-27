"""Shared policy for the private-holder view and alert delivery."""


def status(address, config):
    if address in config["labels"]:
        return "service"
    registry = config.get("private_review")
    if registry is None:
        return "approved"
    record = registry.get(address, {})
    if record.get("status") == "approved" and record.get("source") and record.get("reason"):
        return "approved"
    if record.get("status") == "service" and record.get("source") and record.get("reason"):
        return "service"
    return "candidate"


def approved(address, config):
    return status(address, config) == "approved"


def private_payment(row, config, allowed):
    if "private_review" not in config:
        return True
    return row["kind"] == "payment" and bool({row["sender"], row["recipient"]} & allowed)


def private_signal(row, config, allowed=None):
    address = row["address"]
    included = approved(address, config) if allowed is None else address in allowed
    return included and ("private_review" not in config or (
        row["kind"] != "exchange" and (row["kind"] != "large" or row.get("private_direct"))))
