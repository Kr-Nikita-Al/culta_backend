import re

LETTER_MATCH_PATTERN_PHONE = re.compile(r"(^8|7|\+7)((\d{10})|(\s\(\d{3}\)\s\d{3}\s\d{2}\s\d{2}))")
