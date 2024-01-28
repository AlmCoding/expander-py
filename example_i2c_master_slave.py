#!/usr/bin/env python

""" A simple python script template.
"""

import sys
import serial
from msg import proto_i2c_msg as pm
from msg import tiny_frame
from helper import (get_com_port, print_error, generate_master_write_read_requests,
                    i2c_send_master_request, verify_master_write_read_requests)


REQUEST_LOOPS = 4 * 10000
MAX_DATA_SIZE = 32
IGNORE_SLAVE_NOTIFICATIONS = True  # For testing master only (and slave hal, but no slave notify logic)


def verify_slave_notifications(slave_notifications: list[pm.I2cSlaveAccess], master_requests: list[pm.I2cMasterRequest]):
    for slave_not, master_req in zip(slave_notifications, master_requests):
        master_req_addr = int.from_bytes(master_req.write_data[:2], byteorder='big')
        if master_req.read_size == 0 and len(master_req.write_data):
            # Write request
            if master_req_addr != slave_not.write_addr:
                raise Exception("Master request and slave notification register address mismatch!")
            if len(master_req.write_data[2:]) != len(slave_not.write_data):
                raise Exception("Master request and slave notification write_size mismatch!")
            if master_req.write_data[2:] != slave_not.write_data:
                raise Exception("Master request and slave notification data mismatch!")
            print("Slave write access notification (master_req_id: {}, slave_acc_id: {}) [ok]"
                  .format(master_req.request_id, slave_not.access_id))
        elif master_req.read_size > 0:
            # Read request
            if master_req_addr != slave_not.read_addr:
                raise Exception("Master request and slave notification register address mismatch!")
            if master_req.read_size != slave_not.read_size:
                raise Exception("Master request (master_req_id: {}, slave_acc_id: {}) and slave notification read_size mismatch ({} != {})"
                                .format(master_req.request_id, slave_not.access_id, master_req.read_size, slave_not.read_size))
            print("Slave read access notification (master_req_id: {}, slave_acc_id: {}) [ok]"
                  .format(master_req.request_id, slave_not.access_id))
        else:
            raise Exception("Invalid master request (id: {})".format(master_req.id))


def main(arguments):
    global REQUEST_LOOPS, IGNORE_SLAVE_NOTIFICATIONS
    print("I2cMaster and I2cSlave testing")

    with serial.Serial(get_com_port(), 115200, timeout=1) as ser:
        tf = tiny_frame.tf_init(ser.write)
        i2c_int0 = pm.I2cInterface(i2c_id=pm.I2cId.I2C0, i2c_addr=0x01, i2c_clock=400000, i2c_pullups=True)
        i2c_int1 = pm.I2cInterface(i2c_id=pm.I2cId.I2C1, i2c_addr=0x02, i2c_clock=400000, i2c_pullups=False)

        # Configure i2c
        # i2c_int0.send_config_msg()
        # i2c_int1.send_config_msg()

        count = REQUEST_LOOPS // 4
        requests_pipeline0 = generate_master_write_read_requests(slave_addr=0x02,
                                                                 min_addr=0, max_addr=pm.I2C_SLAVE_BUFFER_SPACE - 1,
                                                                 max_size=MAX_DATA_SIZE, count=count)
        requests_pipeline1 = generate_master_write_read_requests(slave_addr=0x01,
                                                                 min_addr=0, max_addr=pm.I2C_SLAVE_BUFFER_SPACE - 1,
                                                                 max_size=MAX_DATA_SIZE, count=count)
        # requests_pipeline1 = []
        requests_count0 = len(requests_pipeline0)
        requests_count1 = len(requests_pipeline1)
        requests0 = []
        requests1 = []
        notifications0 = []
        notifications1 = []
        requests_send_count = 0
        requests_done_count = 0
        notifications_received_count = 0

        while True:
            if notifications_received_count == requests_send_count or IGNORE_SLAVE_NOTIFICATIONS:
                if i2c_send_master_request(i2c_int0, requests_pipeline0):
                    requests_send_count += 1
                # i2c_send_master_request(i2c_int1, requests_pipeline1)

            requests0 += i2c_int0.pop_complete_master_requests().values()
            requests1 += i2c_int1.pop_complete_master_requests().values()
            requests_done_count = len(requests0 + requests1)

            notifications0 += i2c_int0.pop_slave_access_notifications().values()
            notifications1 += i2c_int1.pop_slave_access_notifications().values()
            notifications_received_count = len(notifications0 + notifications1)

            if requests_done_count == requests_send_count \
                    and (notifications_received_count == requests_send_count or IGNORE_SLAVE_NOTIFICATIONS):
                verify_master_write_read_requests(requests0 + requests1)
                if not IGNORE_SLAVE_NOTIFICATIONS:
                    verify_slave_notifications(notifications0 + notifications1, requests0 + requests1)
                exit(0)

            if ser.in_waiting > 0:
                # Read the incoming data
                rx_data = ser.read(ser.in_waiting)
                # print(data)
                tf.accept(rx_data)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
