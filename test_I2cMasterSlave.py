#!/usr/bin/env python

""" Testing I2c master write/read and slave notifications
"""

import time
import pytest
from msg import tiny_frame
from msg import proto_i2c_msg as pm
from helper import (serial_port, generate_master_write_read_requests,
                    i2c_send_master_request, verify_master_write_read_requests)


class TestI2cMasterSlave:
    REQUEST_COUNT = 4 * 4000
    DATA_SIZE_MIN = 1
    DATA_SIZE_MAX = 128

    I2C_CLOCK_FREQ = 400000
    I2C0_SLAVE_ADDR = 0x01
    I2C1_SLAVE_ADDR = 0x02

    @staticmethod
    def verify_request_notification_flow(i2c_int0: pm.I2cInterface, i2c_int1: pm.I2cInterface):
        access_id_max0 = max([0, ] + list(i2c_int0.get_slave_access_notifications().keys()))
        access_id_max1 = max([0, ] + list(i2c_int1.get_slave_access_notifications().keys()))
        request_id_max0 = max([0, ] + list(i2c_int0.master_requests.keys()))
        request_id_max1 = max([0, ] + list(i2c_int1.master_requests.keys()))

        if access_id_max1 > request_id_max0:
            pytest.fail("No corresponding master(0) request for slave(1) access notification (id: %d) found!"
                        % (access_id_max1,))

        if access_id_max0 > request_id_max1:
            pytest.fail("No corresponding master(1) request for slave(0) access notification (id: %d) found!"
                        % (access_id_max0,))

    @staticmethod
    def verify_slave_notifications(i2c_int: pm.I2cInterface, complete_master_requests: list[pm.I2cMasterRequest]):
        # This only holds true if slave notifications are always serviced before master request responses
        if len(i2c_int.get_slave_access_notifications()) < len(complete_master_requests):
            pytest.fail("More complete master(%d) requests (cnt: %d) than slave notifications (cnt: %d) detected!"
                        % (i2c_int.i2c_id.value, len(complete_master_requests),
                           len(i2c_int.get_slave_access_notifications())))
        slave_notifications = i2c_int.pop_slave_access_notifications(len(complete_master_requests)).values()
        slave_id = i2c_int.i2c_id
        master_id = pm.I2cId.I2C0 if slave_id == pm.I2cId.I2C1 else pm.I2cId.I2C1

        for master_req, slave_not in zip(complete_master_requests, slave_notifications):
            if slave_not.access_id != master_req.request_id:
                pytest.fail("Master(%d) request (id: %d) and slave access (id: %d) id mismatch!"
                            % (i2c_int.i2c_id.value, master_req.request_id, slave_not.access_id))

            if master_req.read_size == 0 and len(master_req.write_data) >= 2:
                # Master write request
                TestI2cMasterSlave.verify_slave_master_write_notification(master_id.value, master_req,
                                                                          slave_id.value, slave_not)
            elif master_req.read_size > 0 and len(master_req.write_data) == 2:
                # Master read request
                TestI2cMasterSlave.verify_slave_master_read_notification(master_id.value, master_req,
                                                                         slave_id.value, slave_not)
            else:
                pytest.fail("Master(%d) request (id: %d) invalid configuration (w_size: %d, r_size: %d) detected!" %
                            (i2c_int.i2c_id.value, master_req.request_id, len(master_req.write_data), master_req.read_size))

    @staticmethod
    def verify_slave_master_write_notification(master_id: int, master_req, slave_id: int, slave_not):
        master_req_addr = int.from_bytes(master_req.write_data[:2], byteorder='big')
        slave_not_addr = int.from_bytes(slave_not.write_data[:2], byteorder='big')
        if master_req_addr != slave_not_addr:
            pytest.fail("Master(%d) request (id: %d, write_addr: %d) and "
                        "slave(%d) indication (id: %d, write_addr: %d) write_addr mismatch!"
                        % (master_id, master_req.request_id, master_req_addr,
                           slave_id, slave_not.access_id, slave_not_addr))

        if master_req.write_data != slave_not.write_data:
            pytest.fail("Master(%d) request (id: %d) and slave(%d) indication (id: %d) write_data (%s != %s) mismatch!"
                        % (master_id, master_req.request_id, slave_id,
                           slave_not.access_id, master_req.write_data[2:], slave_not_addr))

    @staticmethod
    def verify_slave_master_read_notification(master_id: int, master_req, slave_id: int, slave_not):
        master_req_addr = int.from_bytes(master_req.write_data[:2], byteorder='big')
        slave_not_addr = int.from_bytes(slave_not.write_data[:2], byteorder='big')
        if master_req_addr != slave_not_addr:
            pytest.fail("Master(%d) request (id: %d, read_addr: %d) and "
                        "slave(%d) indication (id: %d, read_addr: %d) read_addr mismatch!"
                        % (master_id, master_req.request_id, master_req_addr,
                           slave_id, slave_not.access_id, slave_not_addr))

        if master_req.read_size != len(slave_not.read_data):
            pytest.fail("Master(%d) request (id: %d, read_size: %d) and "
                        "slave(%d) indication (id: %d, read_size: %d) read_size mismatch!"
                        % (master_id, master_req.request_id, master_req.read_size,
                           slave_id, slave_not.access_id, len(slave_not.read_data)))

    def test_i2c_master_slave_write_read(self, serial_port):
        # Test master and slave simultaneously
        tf = tiny_frame.tf_init(serial_port.write)
        cfg0 = pm.I2cConfig(clock_freq=TestI2cMasterSlave.I2C_CLOCK_FREQ, slave_addr=TestI2cMasterSlave.I2C0_SLAVE_ADDR,
                            slave_addr_width=pm.AddressWidth.Bits7, mem_addr_width=pm.AddressWidth.Bits16,
                            pullups_enabled=True)
        cfg1 = pm.I2cConfig(clock_freq=TestI2cMasterSlave.I2C_CLOCK_FREQ, slave_addr=TestI2cMasterSlave.I2C1_SLAVE_ADDR,
                            slave_addr_width=pm.AddressWidth.Bits7, mem_addr_width=pm.AddressWidth.Bits16,
                            pullups_enabled=True)
        i2c_int0 = pm.I2cInterface(i2c_id=pm.I2cId.I2C0, config=cfg0)
        i2c_int1 = pm.I2cInterface(i2c_id=pm.I2cId.I2C1, config=cfg1)
        time.sleep(1)

        requests_pipeline0 = generate_master_write_read_requests(slave_addr=TestI2cMasterSlave.I2C1_SLAVE_ADDR,
                                                                 min_addr=0,
                                                                 max_addr=pm.I2C_SLAVE_BUFFER_SPACE - 1,
                                                                 min_size=TestI2cMasterSlave.DATA_SIZE_MIN,
                                                                 max_size=TestI2cMasterSlave.DATA_SIZE_MAX,
                                                                 count=TestI2cMasterSlave.REQUEST_COUNT // 4)
        requests_pipeline1 = generate_master_write_read_requests(slave_addr=TestI2cMasterSlave.I2C0_SLAVE_ADDR,
                                                                 min_addr=0,
                                                                 max_addr=pm.I2C_SLAVE_BUFFER_SPACE - 1,
                                                                 min_size=TestI2cMasterSlave.DATA_SIZE_MIN,
                                                                 max_size=TestI2cMasterSlave.DATA_SIZE_MAX,
                                                                 count=TestI2cMasterSlave.REQUEST_COUNT // 4)
        requests_pipeline1 = []

        while True:
            i2c_send_master_request(i2c_int0, requests_pipeline0)
            i2c_send_master_request(i2c_int1, requests_pipeline1)
            # time.sleep(0.015)

            if serial_port.in_waiting > 0:
                # Read the incoming data
                rx_data = serial_port.read(serial_port.in_waiting)
                tf.accept(rx_data)

            TestI2cMasterSlave.verify_request_notification_flow(i2c_int0, i2c_int1)

            complete_master_requests = verify_master_write_read_requests(i2c_int0)
            if len(complete_master_requests):
                TestI2cMasterSlave.verify_slave_notifications(i2c_int1, complete_master_requests)
            complete_master_requests = verify_master_write_read_requests(i2c_int1)
            if len(complete_master_requests):
                TestI2cMasterSlave.verify_slave_notifications(i2c_int0, complete_master_requests)

            if ((len(requests_pipeline0 + requests_pipeline1) == 0) and
                    (len(i2c_int0.get_pending_master_request_ids() + i2c_int1.get_pending_master_request_ids()) == 0)):
                break
