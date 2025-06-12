def clean_title(title: str) -> str:
    """Clean a title by removing special characters."""
    return ''.join(filter(lambda x: x not in "|&/<>\"'\\\n", title))
