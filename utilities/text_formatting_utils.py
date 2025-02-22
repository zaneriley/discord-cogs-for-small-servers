import logging

import wcwidth

logger = logging.getLogger(__name__)

def calculate_display_width(text):
    return sum(wcwidth.wcwidth(char) for char in text)


def pad_string(text, total_width, alignment="right"):
    """Pad the string for display with alignment within total_width"""
    text_width = calculate_display_width(text)
    padding = total_width - text_width
    if alignment == "right":
        return " " * padding + text
    elif alignment == "left":
        return text + " " * padding
    return None


def format_row(row, keys, widths, alignments):
    """
    Format a single row based on dynamic widths and specified alignments for each column.

    Parameters
    ----------
    - row (dict): A dictionary representing a single row of data.
    - keys (list of str): The keys that determine the order and selection of data in the row.
    - widths (dict): A dictionary mapping each key to its maximum width.
    - alignments (list of str): A list of alignments ('left' or 'right') corresponding to each key.

    Returns
    -------
    - str: A formatted string representing the row with each column aligned and padded according to the specified widths and alignments.

    Example:
    >>> row = {'city': 'New York', 'condition': 'Cloudy', 'temperature': '85°F', 'precipitation': '20%'}
    >>> keys = ['city', 'condition', 'temperature', 'precipitation']
    >>> widths = {'city': 10, 'condition': 15, 'temperature': 8, 'precipitation': 12}
    >>> alignments = ['right', 'left', 'right', 'left']
    >>> format_row(row, keys, widths, alignments)
    '   New York Cloudy          85°F    20%         '

    """
    formatted_row = []
    for key, alignment in zip(keys, alignments, strict=False):
        padded = pad_string(row.get(key, "-"), widths[key], alignment)
        formatted_row.append(padded)
    return " ".join(formatted_row)


def get_max_widths(data, keys):
    """
    Calculate the maximum display widths for specified keys in a list of dictionaries.

    Parameters
    ----------
    - data (list of dict): A list of dictionaries from which to extract the values.
    - keys (list of str): The keys for which the maximum widths are to be calculated.

    Returns
    -------
    - dict: A dictionary where each key corresponds to one of the specified keys and
            the value is the maximum width of the values associated with that key in the data.

    Example:
    >>> data = [{'name': 'Alice', 'occupation': 'Engineer'}, {'name': 'Bob', 'occupation': 'Doctor'}]
    >>> keys = ['name', 'occupation']
    >>> get_max_widths(data, keys)
    {'name': 5, 'occupation': 8}

    """
    max_widths = {key: len(key) for key in keys}  # Initialize with header widths

    for row in data:
        for key in keys:
            if key in row:
                text_width = calculate_display_width(str(row[key]))
                max_widths[key] = max(max_widths[key], text_width)
    return max_widths
