TCU_TO_PC = 0.01


def pc2tcu(val: float) -> int:
    val /= TCU_TO_PC
    if val >= 0:
        return int(val + 0.5)
    return int(val - 0.5)


def tcu2pc(val):
    return val * TCU_TO_PC
