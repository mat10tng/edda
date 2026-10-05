"""remove reaches mark; tidy is reached by no linked function."""


# FIX-001@1
def remove(order):
    mark(order, "removed")


def mark(order, status):
    order.status = status


def tidy(order):
    order.units_sent = 0
