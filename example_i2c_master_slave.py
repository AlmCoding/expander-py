#!/usr/bin/env python

""" A simple python script template.
"""

import sys
import random
import serial
from msg import proto_i2c_msg as pm
from msg import tiny_frame
from helper import get_com_port, print_error, generate_ascii_data


REQUEST_LOOPS = 4 * 100
MAX_DATA_SIZE = 32


def generate_master_write_read_requests(slave_addr: int, count: int,
                                        start_addr: int, end_addr: int) -> list[pm.I2cMasterRequest]:
    global MAX_DATA_SIZE
    master_requests = []
    for _ in range(count):
        mem_addr = random.randint(start_addr, end_addr)
        addr_bytes = mem_addr.to_bytes(2, 'big')
        data_bytes = generate_ascii_data(1, min(end_addr - mem_addr, MAX_DATA_SIZE))
        tx_bytes = bytes(bytearray(addr_bytes) + bytearray(data_bytes))

        write_request = pm.I2cMasterRequest(slave_addr=slave_addr, write_data=tx_bytes, read_size=0)
        read_request = pm.I2cMasterRequest(slave_addr=slave_addr, write_data=addr_bytes, read_size=len(data_bytes))

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

        write_data = requests[idx-1].write_data[2:]
        if request.read_data != write_data:
            print_error("Request (id: {}, code: {}) data mismatch {} != {}"
                        .format(request.request_id, request.status_code, request.read_data.hex(), write_data.hex()))
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
    print("I2cMaster testing")

    with serial.Serial(get_com_port(), 115200, timeout=1) as ser:
        tf = tiny_frame.tf_init(ser.write)
        i2c_int0 = pm.I2cInterface(i2c_id=pm.I2cId.I2C0, i2c_addr=0x01, i2c_clock=400000, i2c_pullups=True)
        i2c_int1 = pm.I2cInterface(i2c_id=pm.I2cId.I2C1, i2c_addr=0x02, i2c_clock=400000, i2c_pullups=False)

        # Configure i2c
        # i2c_int0.send_config_msg()
        # i2c_int1.send_config_msg()

        requests_pipeline0 = generate_master_write_read_requests(slave_addr=0x02, count=REQUEST_LOOPS // 4,
                                                                 start_addr=0, end_addr=pm.I2C_SLAVE_BUFFER_SPACE-1)
        requests_pipeline1 = generate_master_write_read_requests(slave_addr=0x01, count=REQUEST_LOOPS // 4,
                                                                 start_addr=0, end_addr=pm.I2C_SLAVE_BUFFER_SPACE-1)
        # requests_pipeline1 = []
        requests_count0 = len(requests_pipeline0)
        requests_count1 = len(requests_pipeline1)
        requests_done0 = []
        requests_done1 = []
        notifications0 = []
        notifications1 = []
        requests_send_count = 0
        requests_done_count = 0
        notifications_received_count = 0

        while True:
            if notifications_received_count == requests_send_count:
                i2c_send_master_request(i2c_int0, requests_pipeline0)
                i2c_send_master_request(i2c_int1, requests_pipeline1)
                requests_send_count += 2

            requests_done0 += i2c_int0.pop_complete_master_requests().values()
            requests_done1 += i2c_int1.pop_complete_master_requests().values()
            requests_done_count = len(requests_done0 + requests_done1)

            notifications0 += i2c_int0.pop_slave_access_notifications().values()
            notifications1 += i2c_int1.pop_slave_access_notifications().values()
            notifications_received_count = len(notifications0 + notifications1)

            if requests_done_count == requests_send_count and notifications_received_count == requests_send_count:
                check_complete_requests(requests_done0 + requests_done1)
                exit(0)

            if ser.in_waiting > 0:
                # Read the incoming data
                rx_data = ser.read(ser.in_waiting)
                # print(data)
                tf.accept(rx_data)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
