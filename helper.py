import sys
import time
import string
import random
import pytest
import serial.tools.list_ports
from msg import tiny_frame
from msg import proto_i2c_msg as pm
from msg import proto_ctrl_msg as ctrl_pm


def print_error(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def get_com_port() -> str:
    com_ports = serial.tools.list_ports.comports()
    if com_ports:
        for port, desc, hwid in com_ports:
            if "Serial Device" in desc:
                return port
    raise Exception("No Serial Port found!")


@pytest.fixture()
def serial_port():
    with serial.Serial(get_com_port(), 115200, timeout=1) as ser:
        tiny_frame.tf_init(ser.write)
        ctrl_pm.CtrlInterface.send_system_reset_msg()
        time.sleep(2)

    with serial.Serial(get_com_port(), 115200, timeout=1) as ser:
        yield ser


def generate_ascii_data(min_size: int, max_size: int) -> bytes:
    size = random.randint(min_size, max_size)
    tx_data = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(size))
    return tx_data.encode("utf-8")


def generate_master_write_read_requests(slave_addr: int, min_addr: int, max_addr: int, min_size: int,
                                        max_size: int, count: int) -> list[pm.I2cMasterRequest]:
    master_requests = []
    for _ in range(count):
        max_size -= 2  # Subtract 2 bytes for address
        min_size = min(min_size, max_size)
        random_size = random.randint(min_size, max_size)
        mem_addr = random.randint(min_addr, max_addr - random_size + 1)
       
        data_bytes = generate_ascii_data(random_size, random_size)
        addr_bytes = mem_addr.to_bytes(2, 'big')
        tx_bytes = bytes(bytearray(addr_bytes) + bytearray(data_bytes))

        write_request = pm.I2cMasterRequest(slave_addr=slave_addr, write_data=tx_bytes, read_size=0)
        read_request = pm.I2cMasterRequest(slave_addr=slave_addr, write_data=addr_bytes, read_size=len(data_bytes))

        master_requests.append(write_request)
        master_requests.append(read_request)
    return master_requests


def i2c_send_master_request(i2c_int: pm.I2cInterface, request_queue: list[pm.I2cMasterRequest]):
    if len(i2c_int.get_pending_master_request_ids()) > 0:
        return

    if len(request_queue) and i2c_int.can_accept_request(request_queue[0]):
        request = request_queue.pop(0)
        rid = i2c_int.send_master_request_msg(request=request)
        print("Send master({}) reqeust (id: {}, w_addr: '{}', w_data: {} ({}), r_size: {})"
              .format(i2c_int.i2c_id.value, rid, request.write_data[:2].hex(),
                      request.write_data[2:], len(request.write_data[2:]), request.read_size))
        assert len(i2c_int.get_pending_master_request_ids()) > 0


def verify_master_write_read_requests(i2c_int: pm.I2cInterface) -> list[pm.I2cMasterRequest]:
    complete_count = len(i2c_int.get_complete_master_request_ids())
    if (complete_count % 2 != 0) or (complete_count == 0):
        return []

    previous_write_request = None
    complete_requests = i2c_int.pop_complete_master_requests().values()
    for request in complete_requests:
        if request.status_code != pm.I2cStatusCode.SUCCESS:
            print("Master request (id: {}) failed with status code: {}"
                  .format(request.request_id, request.status_code))
        assert request.status_code == pm.I2cStatusCode.SUCCESS
        assert request.request_id > 0
        if request.read_size == 0:  # Write request
            assert len(request.write_data) > 0
            previous_write_request = request
        else:  # Read request
            assert len(request.write_data) == 2
            assert request.read_data == previous_write_request.write_data[2:]
    return complete_requests
