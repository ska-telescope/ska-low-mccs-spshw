import json


def _s_round(data: int, bits: int, max_width: int = 32) -> int:
    if bits == 0:
        return data
    if data == -(2 ** (max_width - 1)):
        return data
    c_half = 2 ** (bits - 1)
    if data >= 0:
        data = (data + c_half + 0) >> bits
    else:
        data = (data + c_half - 1) >> bits
    return data


x = 523
y = 5
print(_s_round(x, y, 2))
# print((43) >> 2)
print(x // 2**y + 1)
