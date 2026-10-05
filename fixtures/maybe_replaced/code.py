"""An optional fast version that not every import loads."""
from contextlib import suppress

# FIX-001@1
def remove(order):
    order.status = "removed"


with suppress(ImportError):
    from _fast_orders import remove
