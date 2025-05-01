import sys
import string
import random
from interface_expander.I2cInterface import I2cInterface, I2cMasterRequest, I2cStatusCode


def print_error(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def generate_ascii_data(min_size: int, max_size: int) -> bytes:
    size = random.randint(min_size, max_size)
    tx_data = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(size))
    return tx_data.encode("utf-8")


def generate_master_write_read_requests(slave_addr: int, min_addr: int, max_addr: int, min_size: int,
                                        max_size: int, count: int) -> list[I2cMasterRequest]:
    if min_addr < 0 or max_addr < 0:
        raise ValueError("Address must be non-negative!")
    if min_addr >= max_addr:
        raise ValueError("Min address must be less than max address!")
    if min_size < 0 or max_size < 0:
        raise ValueError("Size must be non-negative!")
    if min_size > max_size:
        raise ValueError("Min size must be less than max size!")
    if max_addr >= pow(2, 16):
        raise ValueError("Address size is too large!")

    max_size -= 2  # Subtract 2 bytes for address
    min_size = min(min_size, max_size)

    master_requests = []
    for _ in range(count):
        random_size = random.randint(min_size, max_size)
        mem_addr = random.randint(min_addr, max_addr - random_size + 1)
       
        data_bytes = generate_ascii_data(random_size, random_size)
        addr_bytes = mem_addr.to_bytes(2, 'big')
        tx_bytes = bytes(bytearray(addr_bytes) + bytearray(data_bytes))

        write_request = I2cMasterRequest(slave_addr=slave_addr, write_data=tx_bytes, read_size=0)
        read_request = I2cMasterRequest(slave_addr=slave_addr, write_data=addr_bytes, read_size=len(data_bytes))

        master_requests.append(write_request)
        master_requests.append(read_request)
    return master_requests


def i2c_send_master_request(i2c_int: I2cInterface, request_queue: list[I2cMasterRequest]):
    if len(request_queue) and i2c_int.can_accept_request(request_queue[0]):
        request = request_queue.pop(0)
        rid = i2c_int.send_request(request=request)
        print("Send master({}) reqeust (id: {}, w_addr: '{}', w_data: {} ({}), r_size: {})"
              .format(i2c_int.i2c_id.value, rid, request.write_data[:2].hex(),
                      request.write_data[2:], len(request.write_data[2:]), request.read_size))
        assert len(i2c_int.get_pending_master_request_ids()) > 0
        return rid
    return None


def verify_master_write_read_requests(i2c_int: I2cInterface) -> list[I2cMasterRequest]:
    complete_count = len(i2c_int.get_complete_master_request_ids())
    if (complete_count % 2 != 0) or (complete_count == 0):
        return []

    previous_write_request = None
    complete_requests = i2c_int.pop_complete_master_requests().values()
    for request in complete_requests:
        if request.status_code != I2cStatusCode.SUCCESS:
            print("Master request (id: {}) failed with status code: {}"
                  .format(request.request_id, request.status_code))
        assert request.status_code == I2cStatusCode.SUCCESS
        assert request.request_id > 0
        if request.read_size == 0:  # Write request
            assert len(request.write_data) > 0
            previous_write_request = request
        else:  # Read request
            assert len(request.write_data) == 2
            assert request.read_data == previous_write_request.write_data[2:]
    return complete_requests
