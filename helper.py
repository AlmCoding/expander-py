import sys
import string
import random
import serial.tools.list_ports
from msg import proto_i2c_msg as pm


def print_error(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def get_com_port() -> str:
    com_ports = serial.tools.list_ports.comports()
    if com_ports:
        for port, desc, hwid in com_ports:
            if "Serial Device" in desc:
                return port
    raise Exception("No Serial Port found!")


def generate_ascii_data(min_size: int, max_size: int) -> bytes:
    size = random.randint(min_size, max_size)
    tx_data = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(size))
    return tx_data.encode("utf-8")


def generate_master_write_read_requests(slave_addr: int, min_addr: int, max_addr: int,
                                        max_size: int, count: int) -> list[pm.I2cMasterRequest]:
    master_requests = []
    for _ in range(count):
        mem_addr = random.randint(min_addr, max_addr)
        addr_bytes = mem_addr.to_bytes(2, 'big')
        max_data_size = min(max_addr - mem_addr + 1, max_size)
        data_bytes = generate_ascii_data(1, max_data_size)
        tx_bytes = bytes(bytearray(addr_bytes) + bytearray(data_bytes))

        write_request = pm.I2cMasterRequest(slave_addr=slave_addr, write_data=tx_bytes, read_size=0)
        read_request = pm.I2cMasterRequest(slave_addr=slave_addr, write_data=addr_bytes, read_size=len(data_bytes))

        master_requests.append(write_request)
        master_requests.append(read_request)
    return master_requests


"""
def verify_master_write_read_requests(requests: list[pm.I2cMasterRequest]):
    previous_write_request = None
    for request in enumerate(requests):
        if request.status_code != pm.I2cMasterStatusCode.COMPLETE:
            print_error("[VR] Request (id: {}, code: {}) [failed]".format(request.request_id, request.status_code))
            continue

        if request.read_size == 0 and len(request.write_data):
            print("[VR] Write request (id: {}) [ok]".format(request.request_id))
            continue

        write_data = previous_write_request.write_data[2:]
        if request.read_data != write_data:
            print_error("[VR] Request (id: {}, code: {}) data mismatch {} != {}"
                        .format(request.request_id, request.status_code, request.read_data.hex(), write_data.hex()))
        else:
            print("[VR] Read request (id: {}) [ok]".format(request.request_id))
    requests.clear()
"""

"""
def verify_master_write_read_requests(i2c_int: pm.I2cInterface):
    complete_count = len(i2c_int.get_complete_master_request_ids())
    if (complete_count % 2 != 0) or (complete_count == 0):
        return

    previous_write_request = None
    for request in i2c_int.pop_complete_master_requests().values():
        assert request.status_code == pm.I2cMasterStatusCode.COMPLETE
        if request.read_size == 0:  # Write request
            assert len(request.write_data) > 0
            previous_write_request = request
        else:  # Read request
            assert request.mem_data == previous_write_request.write_data


def i2c_send_master_request(i2c_int: pm.I2cInterface, request_queue: list[pm.I2cMasterRequest]) -> bool:
    if len(request_queue) == 0:
        return False
    if len(i2c_int.get_pending_master_request_ids()) > 0:
        return False

    if i2c_int.can_accept_request(request_queue[0]):
        request = request_queue.pop(0)
        rid = i2c_int.send_master_request_msg(request=request)
        # print("Req: {}, w_addr: '{}', w_data: {} ({}), r_size: {}".format(rid, request.write_data[:2].hex(),
        #                                                                  request.write_data[2:],
        #                                                                  len(request.write_data[2:]),
        #                                                                  request.read_size))
        assert len(i2c_int.get_pending_master_request_ids()) > 0
        return True
    return False
"""