"""FIX-001 has one version; the marker names a second."""


# FIX-001@2
def remove(order):
    order.status = "removed"
