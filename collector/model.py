"""Public keys, exact amounts and normalized operation records."""
import base64
import binascii
import re
from decimal import Decimal

SCALE = 10_000_000


def stroops(value):
    units = Decimal(value) * SCALE
    if not units.is_finite() or units != units.to_integral_value():
        raise ValueError(f"Invalid XLM amount: {value}")
    return int(units)


def xlm(units):
    return format(Decimal(units) / SCALE, ".7f")


def valid_address(address):
    if not isinstance(address, str) or not re.fullmatch(r"G[A-Z2-7]{55}", address):
        return False
    payload = base64.b32decode(address)
    return payload[0] == 48 and binascii.crc_hqx(payload[:-2], 0) == int.from_bytes(payload[-2:], "little")


def category(balance, config):
    for label, threshold in reversed(config["categories"]):
        if balance >= stroops(threshold):
            return label
    return "До 10 000 XLM"


def movements(operation):
    """Known native legs; routed payments expose their two endpoints separately."""
    kind = operation["type"]
    source = operation.get("source_account")
    if kind == "payment" and operation.get("asset_type") == "native":
        yield ("payment", operation.get("from"), operation.get("to"), operation["amount"])
    elif kind == "create_account":
        yield (kind, operation.get("funder"), operation.get("account"), operation["starting_balance"])
    elif kind in ("path_payment_strict_send", "path_payment_strict_receive"):
        if operation.get("source_asset_type") == "native":
            yield ("path_send", operation.get("from"), None, operation["source_amount"])
        if operation.get("asset_type") == "native":
            yield ("path_receive", None, operation.get("to"), operation["amount"])
    elif kind == "create_claimable_balance" and operation.get("asset") == "native":
        yield (kind, operation.get("sponsor") or source, None, operation["amount"])
    elif kind == "invoke_host_function":
        for change in operation.get("asset_balance_changes") or ():
            if change.get("asset_type") == "native" and change.get("amount") is not None:
                yield ("contract_" + change.get("type", "movement"), change.get("from"), change.get("to"), change["amount"])
