"""FIX-001 is approved at v2; this code was written against v1."""


# FIX-001@1
def remove(order):
    order.status = "removed"
