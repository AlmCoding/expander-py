import sys
import string
import random


def print_error(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def get_com_port() -> str:
    return "COM8"


def generate_ascii_data(min_size: int, max_size: int) -> bytes:
    size = random.randint(min_size, max_size)
    tx_data = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(size))
    return tx_data.encode("utf-8")
