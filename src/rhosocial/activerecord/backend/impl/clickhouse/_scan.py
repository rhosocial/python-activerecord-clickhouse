# src/rhosocial/activerecord/backend/impl/clickhouse/_scan.py
"""Character scanning for ClickHouse type spellings.

This backend's ``src`` tree deliberately does not import the standard-library
regular-expression module.  Every spelling the introspection parser reads is a
short, server-shaped word -- ``Int8``, ``Decimal(10, 2)``, ``Tuple(a Int32)`` --
so the rules are stated as plain scans: a leading word, a balanced parenthesis,
a top-level comma, a digit run, a quoted number pair.

The helpers here are the vocabulary those scans share.  They are deliberately
small and side-effect free: each answers one question about a string and says
which part of the string it read, so the parser keeps its behaviour without
carrying a pattern language it does not need.
"""


def is_word_char(char: str) -> bool:
    """Whether *char* is a word character in the word-boundary sense.

    Letters, digits and the underscore.  Used to read a whole leading word, so
    ``INT8X`` stays one word and is not mistaken for ``Int8`` followed by a
    non-word character.
    """
    return char == "_" or char.isalnum()


def leading_word(text: str) -> str:
    """The run of word characters at the start of *text* (``""`` if none)."""
    end = 0
    length = len(text)
    while end < length and is_word_char(text[end]):
        end += 1
    return text[:end]


def leading_word_upper(text: str) -> str:
    """The upper-cased leading word, the form the type-family sets are keyed by."""
    return leading_word(text).upper()


def leading_ascii_letters(text: str) -> str:
    """The run of ``A``-``Z`` characters at the start of *text* (``""`` if none)."""
    end = 0
    length = len(text)
    while end < length and "A" <= text[end] <= "Z":
        end += 1
    return text[:end]


def contains_word(text: str, word: str) -> bool:
    """Whether *word* occurs in *text* as a whole word, case-insensitively."""
    target = word.upper()
    index = 0
    length = len(text)
    while index < length:
        if not is_word_char(text[index]):
            index += 1
            continue
        end = index
        while end < length and is_word_char(text[end]):
            end += 1
        if text[index:end].upper() == target:
            return True
        index = end
    return False


def is_ascii_identifier(text: str) -> bool:
    """Whether *text* is exactly ``[A-Za-z_][A-Za-z0-9_]*``.

    The stricter, ASCII-only predicate used for tuple field names: those are
    identifiers the dialect renders, not arbitrary server words.
    """
    if not text:
        return False
    first = text[0]
    if not (first == "_" or "A" <= first <= "Z" or "a" <= first <= "z"):
        return False
    for char in text[1:]:
        if not (char == "_" or "A" <= char <= "Z" or "a" <= char <= "z" or "0" <= char <= "9"):
            return False
    return True


def digit_runs(text: str) -> list:
    """Every run of decimal digits in *text*, as integers, left to right."""
    runs = []
    index = 0
    length = len(text)
    while index < length:
        if not text[index].isdecimal():
            index += 1
            continue
        end = index
        while end < length and text[end].isdecimal():
            end += 1
        runs.append(int(text[index:end]))
        index = end
    return runs


def parenthesised_digit_runs(text: str) -> list:
    """Integers written immediately as ``(<digits>)``, left to right.

    A group such as ``(3, 'UTC')`` is not one of them: the digits have to be
    the whole group, so a time zone after the precision is not read as one.
    """
    runs = []
    index = 0
    length = len(text)
    while index < length:
        if text[index] != "(":
            index += 1
            continue
        end = index + 1
        while end < length and text[end].isdecimal():
            end += 1
        if end > index + 1 and end < length and text[end] == ")":
            runs.append(int(text[index + 1 : end]))
        index = end
    return runs


def group_body(text: str) -> str:
    """The body of the first balanced parenthesised group (``""`` if none).

    The body runs from the first ``(`` to the ``)`` that closes it; nested
    groups are kept whole.  An unbalanced group runs to the end, which is how
    the original parser collected its arguments.
    """
    start = text.find("(")
    if start < 0:
        return ""
    depth = 0
    for index in range(start + 1, len(text)):
        char = text[index]
        if char == "(":
            depth += 1
        elif char == ")":
            if depth == 0:
                return text[start + 1 : index]
            depth -= 1
    return text[start + 1 :]


def split_top_level_commas(text: str) -> list:
    """Split *text* on commas that are not inside parentheses.

    Empty leading and interior entries are kept; a trailing empty entry is
    dropped.  That is the shape the parser's argument list always had.
    """
    parts = []
    current = []
    depth = 0
    for char in text:
        if char == "(":
            depth += 1
            current.append(char)
        elif char == ")":
            if depth == 0:
                break
            depth -= 1
            current.append(char)
        elif char == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if current:
        parts.append("".join(current).strip())
    return parts


def number_after_marker(text: str, marker: str) -> int | None:
    """The first integer after *marker* and at least one whitespace character.

    Used for ``SRID 4326``, which may appear at the end of a spatial spelling.
    A later occurrence of *marker* is tried when this one is not followed by
    whitespace and digits.
    """
    search_from = 0
    length = len(text)
    while True:
        index = text.find(marker, search_from)
        if index < 0:
            return None
        cursor = index + len(marker)
        while cursor < length and text[cursor].isspace():
            cursor += 1
        if cursor > index + len(marker):
            end = cursor
            while end < length and text[end].isdecimal():
                end += 1
            if end > cursor:
                return int(text[cursor:end])
        search_from = index + 1


def quoted_number_pairs(text: str) -> list:
    """``('name' = <int>)`` pairs, left to right, with the integer parsed.

    Reads the quoted name, an equals sign and an optionally negative integer;
    whitespace around the equals sign is allowed.  Enum labels are ordered by
    this integer on the server, so the caller sorts the pairs by the value.
    """
    pairs = []
    index = 0
    length = len(text)
    while index < length:
        if text[index] != "'":
            index += 1
            continue
        close = text.find("'", index + 1)
        if close < 0:
            break
        name = text[index + 1 : close]
        cursor = close + 1
        while cursor < length and text[cursor].isspace():
            cursor += 1
        if cursor >= length or text[cursor] != "=":
            index += 1
            continue
        cursor += 1
        while cursor < length and text[cursor].isspace():
            cursor += 1
        negative = False
        if cursor < length and text[cursor] == "-":
            negative = True
            cursor += 1
        digits_start = cursor
        while cursor < length and text[cursor].isdecimal():
            cursor += 1
        if cursor == digits_start:
            index += 1
            continue
        value = int(text[digits_start:cursor])
        pairs.append((name, -value if negative else value))
        index = cursor
    return pairs
