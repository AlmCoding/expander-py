#!/usr/bin/env python

""" Read write commands to I2C master (Suitable for external slave, e.g. FRAM)
"""

import sys
import serial
from msg import proto_i2c_msg as pm
from msg import tiny_frame
from helper import (get_com_port, print_error, generate_master_write_read_requests,
                    i2c_send_master_request, verify_master_write_read_requests)

REQUEST_LOOPS = 4 * 10
MAX_DATA_SIZE = 32


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

        requests_pipeline0 = generate_master_write_read_requests(slave_addr=0x02,
                                                                 min_addr=0, max_addr=pm.I2C_SLAVE_BUFFER_SPACE - 1,
                                                                 max_size=MAX_DATA_SIZE, count=REQUEST_LOOPS // 4)
        requests_pipeline1 = generate_master_write_read_requests(slave_addr=0x01,
                                                                 min_addr=0, max_addr=pm.I2C_SLAVE_BUFFER_SPACE - 1,
                                                                 max_size=MAX_DATA_SIZE, count=REQUEST_LOOPS // 4)
        # requests_pipeline1 = []
        requests_count0 = len(requests_pipeline0)
        requests_count1 = len(requests_pipeline1)
        requests0 = []
        requests1 = []

        while True:
            i2c_send_master_request(i2c_int0, requests_pipeline0)
            i2c_send_master_request(i2c_int1, requests_pipeline1)

            requests0 += i2c_int0.pop_complete_master_requests().values()
            requests1 +=  i2c_int1.pop_complete_master_requests().values()

            if len(requests0 + requests1) == (requests_count0 + requests_count1):
                verify_master_write_read_requests(requests0 + requests1)
                exit(0)

            if ser.in_waiting > 0:
                # Read the incoming data
                rx_data = ser.read(ser.in_waiting)
                # print(data)
                tf.accept(rx_data)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
