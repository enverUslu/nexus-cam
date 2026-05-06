"""Small QR encoder for launcher URLs."""

from __future__ import annotations


LEVEL_L = 1
FORMAT_MASK = 0x5412
FORMAT_POLY = 0x537
BYTE_MODE = 0b0100
MASK_ID = 0

VERSIONS = {
    1: {"size": 21, "data": 19, "ecc": 7, "align": []},
    2: {"size": 25, "data": 34, "ecc": 10, "align": [6, 18]},
    3: {"size": 29, "data": 55, "ecc": 15, "align": [6, 22]},
    4: {"size": 33, "data": 80, "ecc": 20, "align": [6, 26]},
}


def make_matrix(text: str) -> list[list[bool]]:
    data = text.encode("utf-8")
    version, spec = choose_version(len(data))
    data_codewords = encode_data(data, int(spec["data"]))
    codewords = data_codewords + reed_solomon(data_codewords, int(spec["ecc"]))
    size = int(spec["size"])
    modules = [[False] * size for _ in range(size)]
    reserved = [[False] * size for _ in range(size)]

    draw_function_patterns(modules, reserved, version, list(spec["align"]))
    draw_data(modules, reserved, codeword_bits(codewords))
    draw_format(modules, reserved)
    return modules


def choose_version(length: int) -> tuple[int, dict[str, int | list[int]]]:
    for version, spec in VERSIONS.items():
        if length <= int(spec["data"]) - 2:
            return version, spec
    raise ValueError("QR payload is too long")


def encode_data(data: bytes, capacity: int) -> list[int]:
    bits: list[int] = []
    append_bits(bits, BYTE_MODE, 4)
    append_bits(bits, len(data), 8)
    for byte in data:
        append_bits(bits, byte, 8)
    append_bits(bits, 0, min(4, capacity * 8 - len(bits)))
    while len(bits) % 8:
        bits.append(0)

    codewords = [bits_to_int(bits[i : i + 8]) for i in range(0, len(bits), 8)]
    pads = [0xEC, 0x11]
    while len(codewords) < capacity:
        codewords.append(pads[len(codewords) % 2])
    return codewords


def append_bits(bits: list[int], value: int, width: int) -> None:
    for shift in range(width - 1, -1, -1):
        bits.append((value >> shift) & 1)


def bits_to_int(bits: list[int]) -> int:
    value = 0
    for bit in bits:
        value = (value << 1) | bit
    return value


def codeword_bits(codewords: list[int]) -> list[int]:
    bits: list[int] = []
    for codeword in codewords:
        append_bits(bits, codeword, 8)
    return bits


def draw_function_patterns(
    modules: list[list[bool]],
    reserved: list[list[bool]],
    version: int,
    alignment: list[int],
) -> None:
    size = len(modules)
    draw_finder(modules, reserved, 0, 0)
    draw_finder(modules, reserved, size - 7, 0)
    draw_finder(modules, reserved, 0, size - 7)

    for i in range(size):
        set_module(modules, reserved, 6, i, i % 2 == 0)
        set_module(modules, reserved, i, 6, i % 2 == 0)

    for row in alignment:
        for col in alignment:
            if reserved[row][col]:
                continue
            draw_alignment(modules, reserved, col, row)

    set_module(modules, reserved, 8, 4 * version + 9, True)
    reserve_format(reserved)


def draw_finder(modules: list[list[bool]], reserved: list[list[bool]], x: int, y: int) -> None:
    size = len(modules)
    for row in range(y - 1, y + 8):
        for col in range(x - 1, x + 8):
            if 0 <= row < size and 0 <= col < size:
                reserved[row][col] = True
                modules[row][col] = False
    for row in range(7):
        for col in range(7):
            dark = col in (0, 6) or row in (0, 6) or (2 <= col <= 4 and 2 <= row <= 4)
            set_module(modules, reserved, x + col, y + row, dark)


def draw_alignment(modules: list[list[bool]], reserved: list[list[bool]], x: int, y: int) -> None:
    for row in range(-2, 3):
        for col in range(-2, 3):
            dark = max(abs(row), abs(col)) != 1
            set_module(modules, reserved, x + col, y + row, dark)


def reserve_format(reserved: list[list[bool]]) -> None:
    size = len(reserved)
    for i in range(9):
        if i != 6:
            reserved[8][i] = True
            reserved[i][8] = True
    for i in range(8):
        reserved[size - 1 - i][8] = True
        reserved[8][size - 1 - i] = True


def draw_data(modules: list[list[bool]], reserved: list[list[bool]], bits: list[int]) -> None:
    size = len(modules)
    index = 0
    upward = True
    col = size - 1
    while col > 0:
        if col == 6:
            col -= 1
        rows = range(size - 1, -1, -1) if upward else range(size)
        for row in rows:
            for current_col in (col, col - 1):
                if reserved[row][current_col]:
                    continue
                bit = bits[index] if index < len(bits) else 0
                modules[row][current_col] = bool(bit) ^ mask(row, current_col)
                index += 1
        upward = not upward
        col -= 2


def draw_format(modules: list[list[bool]], reserved: list[list[bool]]) -> None:
    size = len(modules)
    bits = format_bits((LEVEL_L << 3) | MASK_ID)
    positions_a = (
        [(8, i) for i in range(6)]
        + [(8, 7), (8, 8), (7, 8)]
        + [(5 - i, 8) for i in range(6)]
    )
    positions_b = [(size - 1 - i, 8) for i in range(8)] + [(8, size - 7 + i) for i in range(7)]
    for index, (row, col) in enumerate(positions_a):
        set_module(modules, reserved, col, row, bool((bits >> index) & 1))
    for index, (row, col) in enumerate(positions_b):
        set_module(modules, reserved, col, row, bool((bits >> index) & 1))


def format_bits(value: int) -> int:
    data = value << 10
    for shift in range(14, 9, -1):
        if (data >> shift) & 1:
            data ^= FORMAT_POLY << (shift - 10)
    return ((value << 10) | data) ^ FORMAT_MASK


def mask(row: int, col: int) -> bool:
    return (row + col) % 2 == 0


def set_module(
    modules: list[list[bool]],
    reserved: list[list[bool]],
    x: int,
    y: int,
    value: bool,
) -> None:
    modules[y][x] = value
    reserved[y][x] = True


def reed_solomon(data: list[int], degree: int) -> list[int]:
    generator = rs_generator(degree)
    remainder = [0] * degree
    for byte in data:
        factor = byte ^ remainder[0]
        remainder = remainder[1:] + [0]
        for index, coefficient in enumerate(generator[1:]):
            remainder[index] ^= gf_multiply(coefficient, factor)
    return remainder


def rs_generator(degree: int) -> list[int]:
    result = [1]
    for index in range(degree):
        result = poly_multiply(result, [1, gf_power(index)])
    return result


def poly_multiply(left: list[int], right: list[int]) -> list[int]:
    result = [0] * (len(left) + len(right) - 1)
    for i, a in enumerate(left):
        for j, b in enumerate(right):
            result[i + j] ^= gf_multiply(a, b)
    return result


def gf_power(power: int) -> int:
    value = 1
    for _ in range(power):
        value = gf_multiply(value, 2)
    return value


def gf_multiply(left: int, right: int) -> int:
    result = 0
    while right:
        if right & 1:
            result ^= left
        left <<= 1
        if left & 0x100:
            left ^= 0x11D
        right >>= 1
    return result
