def filter_numeric_ports(port_list):
    """
    Given a list of ports (which may include non-numeric entries like "unknown"),
    return a set of integer ports.
    """
    filtered = set()
    for port in port_list:
        # If the port is already an integer (or float), add it.
        if isinstance(port, (int, float)):
            filtered.add(int(port))
        # If it's a string that represents a number, convert and add.
        elif isinstance(port, str) and port.isdigit():
            filtered.add(int(port))
        # Otherwise, ignore it.
    return filtered
