#!/usr/bin/env python

""" A simple python script template.
"""

import sys
import random
import serial
from msg import proto_i2c_msg as pm
import msg.tiny_frame as tiny_frame
from helper import get_com_port, print_error, generate_ascii_data

REQUEST_LOOPS = 4
MIN_DATA_SIZE = 1
MAX_DATA_SIZE = 64

MAX_DATA_SIZE -= tiny_frame.TF_FRAME_OVERHEAD_SIZE + 24
if MIN_DATA_SIZE >= MAX_DATA_SIZE:
    MIN_DATA_SIZE = MAX_DATA_SIZE


def generate_master_write_requests(slave_addr: int, count: int) -> list[pm.I2cMasterRequest]:
    global MIN_DATA_SIZE, MAX_DATA_SIZE
    master_requests = []
    for _ in range(count):
        tx_data = generate_ascii_data(MIN_DATA_SIZE, MAX_DATA_SIZE)
        mem_addr = 42  # random.randint(0, pm.I2C_SLAVE_BUFFER_SPACE - len(tx_data) - 1)
        tx_bytes = bytearray(mem_addr.to_bytes(2, 'little')) + bytearray(tx_data)
        write_request = pm.I2cMasterRequest(slave_addr=slave_addr, write_data=bytes(tx_bytes), read_size=0)
        master_requests.append(write_request)
    return master_requests


def generate_master_read_requests(slave_addr: int, count: int) -> list[pm.I2cMasterRequest]:
    global MIN_DATA_SIZE, MAX_DATA_SIZE
    master_requests = []
    for _ in range(count):
        mem_addr = 42  # random.randint(0, pm.I2C_SLAVE_BUFFER_SPACE - MIN_DATA_SIZE - 1)
        read_size = 25  # random.randint(MIN_DATA_SIZE, min(pm.I2C_SLAVE_BUFFER_SPACE - mem_addr, MAX_DATA_SIZE))
        tx_bytes = mem_addr.to_bytes(2, 'little')
        write_request = pm.I2cMasterRequest(slave_addr=slave_addr, write_data=tx_bytes, read_size=read_size)
        master_requests.append(write_request)
    return master_requests


def check_complete_requests(requests: list[pm.I2cSlaveRequest]):
    for idx, request in enumerate(requests):
        if request.status_code != pm.I2cSlaveStatusCode.COMPLETE:
            print_error("Request (id: {}, code: {}) [failed]".format(request.request_id, request.status_code))
            continue

        if request.read_size == 0:
            print("Write request (id: {}) [ok]".format(request.request_id))
            continue

        write_data = requests[idx - 1].write_data
        if request.mem_data != write_data:
            print_error("Request (id: {}, code: {}) data mismatch {} != {}"
                        .format(request.request_id, request.status_code, request.mem_data.hex(), write_data.hex()))
        else:
            print("Read request (id: {}) [ok]".format(request.request_id))
    requests.clear()


def i2c_send_master_request(i2c_int, request_queue):
    if (len(request_queue) > 0) and i2c_int.can_accept_request(request_queue[0]):
        request = request_queue.pop(0)
        rid = i2c_int.send_master_request_msg(request=request)
        print("Req: {}, w_addr: '{}', w_data: {} ({}), r_size: {}".format(rid, request.write_data[:2].hex(),
                                                                          request.write_data[2:],
                                                                          len(request.write_data[2:]),
                                                                          request.read_size))


def main(arguments):
    global REQUEST_LOOPS
    print("I2c test sender")

    with serial.Serial(get_com_port(), 115200, timeout=1) as ser:
        tf = tiny_frame.tf_init(ser.write)
        i2c_int0 = pm.I2cInterface(i2c_id=pm.I2cId.I2C0, i2c_addr=0x01, i2c_clock=400000, i2c_pullups=True)
        i2c_int1 = pm.I2cInterface(i2c_id=pm.I2cId.I2C1, i2c_addr=0x02, i2c_clock=400000, i2c_pullups=False)

        # Configure i2c
        # i2c_int0.send_config_msg()
        # i2c_int1.send_config_msg()

        master_requests_pipeline = generate_master_write_requests(slave_addr=0x02, count=REQUEST_LOOPS)
        # slave_access_expects = derive_slave_access_requests()
        # master_requests_pipeline = generate_master_read_requests(slave_addr=0x02, count=REQUEST_LOOPS)
        i2c_send_master_request(i2c_int0, master_requests_pipeline)

        exit(0)

        master_requests_count = len(master_requests_pipeline)
        master_requests_done = []

        while True:
            requests0 = i2c_int0.pop_complete_slave_requests()
            requests1 = i2c_int1.pop_complete_slave_requests()
            requests_done0 += requests0.values()
            requests_done1 += requests1.values()

            if len(requests_done0 + requests_done1) == (requests_count0 + requests_count1):
                check_complete_requests(requests_done0 + requests_done1)
                exit(0)

            if ser.in_waiting > 0:
                # Read the incoming data
                rx_data = ser.read(ser.in_waiting)
                # print(data)
                tf.accept(rx_data)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
