#!/usr/bin/env python

""" A simple python script template.
"""

import sys
import random
import serial
from msg import proto_i2c_msg as pm
from msg import tiny_frame


REQUEST_LOOPS = 4*10
SLAVE_ADDR = 0x68


def print_error(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def generate_master_write_read_requests(count: int, addresses: list) -> list[pm.I2cMasterRequest]:
    master_requests = []
    for _ in range(count):
        write_size = random.randint(1, len(addresses))
        reg_addr = random.choice(addresses)
        tx_bytes = bytearray([reg_addr]) + bytearray(random.randbytes(write_size))

        write_request = pm.I2cMasterRequest(slave_addr=SLAVE_ADDR, write_data=bytes(tx_bytes), read_size=0)
        read_request = pm.I2cMasterRequest(slave_addr=SLAVE_ADDR, write_data=bytes([reg_addr]), read_size=write_size)

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
                        .format(request.request_id, request.status_code, request.read_data.hex(), write_data.hex()))
        else:
            print("Read request (id: {}) [ok]".format(request.request_id))

    requests.clear()


def i2c_send(i2c_int, request_queue):
    if len(request_queue) == 0:
        return

    if i2c_int.can_accept_request(request_queue[0]):
        rid = i2c_int.send_master_request_msg(request=request_queue[0])
        print("Req: {}, w_data: {}, r_size: {}".format(
              rid, request_queue[0].write_data.hex(), request_queue[0].read_size))
        request_queue.pop(0)


def i2c_send_sequence(i2c_int):
    reg_addr = random.choice([0x20, 0x21, 0x22, 0x23, 0x24])
    reg_addr = reg_addr | 0x80  # Set auto addr increment bit
    tx_bytes = bytearray([reg_addr]) + bytearray(random.randbytes(3))

    write_request = pm.I2cMasterRequest(slave_addr=SLAVE_ADDR, write_data=bytes(tx_bytes), read_size=0)
    read_request = pm.I2cMasterRequest(slave_addr=SLAVE_ADDR, write_data=bytes(), read_size=3)

    rids = i2c_int.send_master_sequence([write_request, read_request])


def main(arguments):
    global REQUEST_LOOPS
    print("I2c test sender")

    with serial.Serial('COM3', 115200, timeout=1) as ser:
        tf = tiny_frame.tf_init(ser.write)
        i2c_int0 = pm.I2cInterface(i2c_id=pm.I2cId.I2C0, i2c_addr=0x01, i2c_clock=400000, i2c_pullups=True)
        i2c_int1 = pm.I2cInterface(i2c_id=pm.I2cId.I2C1, i2c_addr=0x02, i2c_clock=400000, i2c_pullups=False)

        # Configure i2c
        # i2c_int0.send_config_msg()
        # i2c_int1.send_config_msg()

        requests_pipeline0 = generate_master_write_read_requests(REQUEST_LOOPS // 4, [0x0d, 0x0e])
        requests_pipeline1 = generate_master_write_read_requests(REQUEST_LOOPS // 4, [0x13, 0x14])
        requests_count0 = len(requests_pipeline0)
        requests_count1 = len(requests_pipeline1)
        requests_done0 = []
        requests_done1 = []

        # i2c_send_sequence(i2c_int0)

        while True:
            i2c_send(i2c_int0, requests_pipeline0)
            i2c_send(i2c_int1, requests_pipeline1)

            requests0 = i2c_int0.pop_complete_master_requests()
            requests1 = i2c_int1.pop_complete_master_requests()
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
