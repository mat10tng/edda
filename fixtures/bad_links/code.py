"""remove does FIX-001's operation, written against its v1."""


# FIX-001@1
def remove(order):
    order.status = "removed"
