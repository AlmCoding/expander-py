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

REQUEST_LOOPS = 1
MIN_TX_SIZE = 1
MAX_DATA_SIZE = 64
TX_HISTORY = bytearray()
REQUEST_COUNTER = 0
REQUEST_IDS = []

MASTER_WRITE_REQUESTS = [{"write": ''.join(random.choice(string.ascii_letters + string.digits)
                          for _ in range(random.randint(4, 6))),
                          "read": 0} for i in range(10)]


def i2c_send(i2c_int):
    global REQUEST_COUNTER, TX_HISTORY, REQUEST_IDS

    write_data = "This is a test. ({}).".format(REQUEST_COUNTER)
    read_size = 0

    if (i2c_int.can_accept_master_request(len(write_data), read_size)
            and REQUEST_COUNTER < REQUEST_LOOPS):
        print("Data: '{}'".format(write_data))
        tx_data = bytes(write_data, 'ascii')

        request = pm.I2cMasterWriteRequest(slave_addr=0x05, write_data=tx_data)
        REQUEST_IDS.append(i2c_int.send_master_request_msg(request=request))

        REQUEST_COUNTER += 1
        TX_HISTORY += tx_data


def main(arguments):
    global TX_HISTORY, REQUEST_IDS
    print("Uart test sender")

    with serial.Serial('COM4', 115200, timeout=1) as ser:
        tf = tiny_frame.tf_init(ser.write)
        i2c_int = pm.I2cInterface(i2c_id=pm.I2cId.I2C0, i2c_addr=0x01, i2c_clock=400000)

        # Configure i2c
        # i2c_int.send_config_msg()
        time.sleep(1)

        while True:
            if len(REQUEST_IDS) == 0:
                i2c_send(i2c_int)

            ids = i2c_int.get_completed_master_request_ids()

            if ser.in_waiting > 0:
                # Read the incoming data
                rx_data = ser.read(ser.in_waiting)
                # print(data)
                tf.accept(rx_data)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
