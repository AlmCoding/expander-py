#!/usr/bin/env python

"""A simple python script template.
"""

import sys
import enum
import time
import string
import random
import serial
import tiny_frame
import proto_i2c_msg as pm

REQUEST_LOOPS = 100


def print_error(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def generate_master_write_read_requests(count: int) -> list[pm.I2cMasterRequest]:
    master_requests = []
    for _ in range(count):
        reg_addr = random.choice([0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26])
        reg_val = random.randint(0, 255)
        write_request = pm.I2cMasterRequest(slave_addr=25, write_data=bytes([reg_addr, reg_val]), read_size=0)
        read_request = pm.I2cMasterRequest(slave_addr=25, write_data=bytes([reg_addr]), read_size=1)
        master_requests.append(write_request)
        master_requests.append(read_request)
    return master_requests


def check_complete_requests(requests: list[pm.I2cMasterRequest]):
    for idx, request in enumerate(requests):
        if request.status_code != pm.I2cMasterStatusCode.COMPLETE:
            print_error("Request (id: {}, code: {}) [failed]".format(request.request_id, request.status_code))
            continue

        if request.read_size == 0:
            print("Write request (id: {}) [ok]".format(request.request_id))
            continue

        write_data = requests[idx-1].write_data[1:]
        if request.read_data != write_data:
            print_error("Request (id: {}, code: {}) data mismatch {} != {}"
                        .format(request.request_id, request.status_code, request.read_data, write_data))
        else:
            print("Read request (id: {}) [ok]".format(request.request_id))

    requests.clear()


def i2c_send(i2c_int, request_queue):
    if len(request_queue) == 0:
        return

    # request = pm.I2cMasterRequest(slave_addr=25, write_data=tx_data, read_size=0)
    # request = pm.I2cMasterRequest(slave_addr=25, write_data=bytes.fromhex("20"), read_size=30)

    if i2c_int.can_accept_request(request_queue[0]):
        i2c_int.send_master_request_msg(request=request_queue[0])
        request_queue.pop(0)


def main(arguments):
    global REQUEST_LOOPS
    print("Uart test sender")

    with serial.Serial('COM4', 115200, timeout=1) as ser:
        tf = tiny_frame.tf_init(ser.write)
        i2c_int = pm.I2cInterface(i2c_id=pm.I2cId.I2C0, i2c_addr=0x01, i2c_clock=400000)

        # Configure i2c
        # i2c_int.send_config_msg()
        time.sleep(1)

        requests_pipeline = generate_master_write_read_requests(REQUEST_LOOPS // 2)
        requests_count = len(requests_pipeline)
        requests_done = []

        while True:
            i2c_send(i2c_int, requests_pipeline)

            requests = i2c_int.pop_complete_master_requests()
            if len(requests):
                requests_done += requests.values()

            if len(requests_pipeline) == 0 and len(requests_done) == requests_count:
                check_complete_requests(requests_done)
                exit(0)

            if ser.in_waiting > 0:
                # Read the incoming data
                rx_data = ser.read(ser.in_waiting)
                # print(data)
                tf.accept(rx_data)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
