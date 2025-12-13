def normalize_currency(node):
    if node is None:
        return None
    v = node.get("__value__", None)
    try:
        return float(v)
    except Exception:
        return None
