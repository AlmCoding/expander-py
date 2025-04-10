#!/usr/bin/env python

""" Write and read requests to the I2C slave memory (no I2C communication involved)
"""

import sys
import random
import serial
from msg import I2cInterface as pm
import msg.tiny_frame as tiny_frame
from helper import get_com_port, print_error, generate_ascii_data


REQUEST_LOOPS = 4 * 10000
MIN_DATA_SIZE = 1
MAX_DATA_SIZE = 64

MAX_DATA_SIZE -= tiny_frame.TF_FRAME_OVERHEAD_SIZE + 24
if MIN_DATA_SIZE >= MAX_DATA_SIZE:
    MIN_DATA_SIZE = MAX_DATA_SIZE


def generate_slave_write_read_requests(count: int) -> list[pm.I2cSlaveRequest]:
    global MIN_DATA_SIZE, MAX_DATA_SIZE
    slave_requests = []
    for _ in range(count):
        tx_data = generate_ascii_data(MIN_DATA_SIZE, MAX_DATA_SIZE)
        mem_addr = random.randint(0, pm.I2C_SLAVE_BUFFER_SPACE - len(tx_data) - 1)

        write_request = pm.I2cSlaveRequest(write_addr=mem_addr, write_data=tx_data, read_addr=0, read_size=0)
        read_request = pm.I2cSlaveRequest(write_addr=0, write_data=bytes(), read_addr=mem_addr, read_size=len(tx_data))

        slave_requests.append(write_request)
        slave_requests.append(read_request)
    return slave_requests


def check_complete_requests(requests: list[pm.I2cSlaveRequest]):
    for idx, request in enumerate(requests):
        if request.status_code != pm.I2cSlaveStatusCode.COMPLETE:
            print_error("Request (id: {}, code: {}) [failed]".format(request.request_id, request.status_code))
            continue

        if request.read_size == 0:
            print("Write request (id: {}) [ok]".format(request.request_id))
            continue

        write_data = requests[idx-1].write_data
        if request.mem_data != write_data:
            print_error("Request (id: {}, code: {}) data mismatch {} != {}"
                        .format(request.request_id, request.status_code, request.mem_data.hex(), write_data.hex()))
        else:
            print("Read request (id: {}) [ok]".format(request.request_id))
    requests.clear()


def i2c_send(i2c_int, request_queue):
    if len(request_queue) == 0:
        return

    if len(i2c_int.get_pending_slave_request_ids()) > 0:
        return

    if i2c_int.can_accept_request(request_queue[0]):
        rid = i2c_int.send_slave_request_msg(request=request_queue[0])
        print("Req: {}, w_data: {} ({}), r_size: {}".format(
              rid, request_queue[0].write_data, len(request_queue[0].write_data), request_queue[0].read_size))
        request_queue.pop(0)


def main(arguments):
    global REQUEST_LOOPS
    print("I2cSlave memory testing")

    with serial.Serial(get_com_port(), 115200, timeout=1) as ser:
        tf = tiny_frame.tf_init(ser.write)
        i2c_int0 = pm.I2cInterface(i2c_id=pm.I2cId.I2C0, i2c_addr=0x01, i2c_clock=400000, i2c_pullups=True)
        i2c_int1 = pm.I2cInterface(i2c_id=pm.I2cId.I2C1, i2c_addr=0x02, i2c_clock=400000, i2c_pullups=False)

        # Configure i2c
        # i2c_int0.send_config_msg()
        # i2c_int1.send_config_msg()

        requests_pipeline0 = generate_slave_write_read_requests(REQUEST_LOOPS // 4)
        requests_pipeline1 = generate_slave_write_read_requests(REQUEST_LOOPS // 4)
        requests_count0 = len(requests_pipeline0)
        requests_count1 = len(requests_pipeline1)
        requests_done0 = []
        requests_done1 = []

        while True:
            i2c_send(i2c_int0, requests_pipeline0)
            i2c_send(i2c_int1, requests_pipeline1)

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
