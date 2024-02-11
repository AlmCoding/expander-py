#!/usr/bin/env python

""" Testing I2c master write/read and slave notifications
"""

import pytest
import serial
from msg import tiny_frame
from msg import proto_i2c_msg as pm
from helper import (get_com_port, generate_master_write_read_requests,
                    i2c_send_master_request, verify_master_write_read_requests)


@pytest.fixture()
def serial_port():
    with serial.Serial(get_com_port(), 115200, timeout=1) as ser:
        yield ser


class TestI2cMasterSlave:
    REQUEST_COUNT = 4 * 1000
    DATA_SIZE_MIN = 1
    DATA_SIZE_MAX = 64 - tiny_frame.TF_FRAME_OVERHEAD_SIZE - 24

    I2C_CLOCK_FREQ = 400000
    I2C0_SLAVE_ADDR = 0x01
    I2C1_SLAVE_ADDR = 0x02

    @staticmethod
    def verify_slave_notifications(i2c_int, complete_master_requests):
        # This only holds true if slave notifications are always serviced before master request responses
        if len(i2c_int.get_slave_access_notifications()) < len(complete_master_requests):
            pytest.fail("More complete master requests (count: %d) than slave notifications (count: %d) detected!"
                        % (len(i2c_int.get_slave_access_notifications()), len(complete_master_requests)))
        slave_notifications = i2c_int.pop_slave_access_notifications(len(complete_master_requests)).values()

        for master_req, slave_not in zip(complete_master_requests, slave_notifications):
            if slave_not.access_id != master_req.request_id:
                pytest.fail("Master request (id: %d) and slave access (id: %d) id mismatch!"
                            % (master_req.request_id, slave_not.access_id))

            if master_req.read_size == 0 and len(master_req.write_data) > 2:
                # Master write request
                TestI2cMasterSlave.verify_slave_master_write_notification(master_req, slave_not)
            elif master_req.read_size > 0 and len(master_req.write_data) == 2:
                # Master read request
                TestI2cMasterSlave.verify_slave_master_read_notification(master_req, slave_not)
            else:
                pytest.fail("Invalid write/read size (%d/%d) configuration of master request!"
                            % (len(master_req.write_data), master_req.read_size))

    @staticmethod
    def verify_slave_master_write_notification(master_req, slave_not):
        master_req_addr = int.from_bytes(master_req.write_data[:2], byteorder='big')
        if master_req_addr != slave_not.write_addr:
            pytest.fail("Request (id: %d, write_addr: %d) and indication (id: %d, write_addr: %d) write_addr mismatch!"
                        % (master_req.request_id, master_req_addr, slave_not.access_id, slave_not.write_addr))

        if master_req.write_data[2:] != slave_not.write_data:
            pytest.fail("Request (id: %d) and indication (id: %d) write_data (%s != %s) mismatch!"
                        % (master_req.request_id, slave_not.access_id, master_req.write_data[2:], slave_not.write_addr))

    @staticmethod
    def verify_slave_master_read_notification(master_req, slave_not):
        master_req_addr = int.from_bytes(master_req.write_data[:2], byteorder='big')
        if master_req_addr != slave_not.read_addr:
            pytest.fail("Request (id: %d, read_addr: %d) and indication (id: %d, read_addr: %d) read_addr mismatch!"
                        % (master_req.request_id, master_req_addr, slave_not.access_id, slave_not.read_addr))

        if master_req.read_size != slave_not.read_size:
            pytest.fail("Request (id: %d, read_size: %d) and indication (id: %d, read_size: %d) read_size mismatch!"
                        % (master_req.request_id, master_req.read_size, slave_not.access_id, slave_not.read_size))

    def test_i2c_master_slave_write_read(self, serial_port):
        # Test master and slave simultaneously
        tf = tiny_frame.tf_init(serial_port.write)
        i2c_int0 = pm.I2cInterface(i2c_id=pm.I2cId.I2C0, i2c_addr=TestI2cMasterSlave.I2C0_SLAVE_ADDR,
                                   i2c_clock=TestI2cMasterSlave.I2C_CLOCK_FREQ, i2c_pullups=True)
        i2c_int1 = pm.I2cInterface(i2c_id=pm.I2cId.I2C1, i2c_addr=TestI2cMasterSlave.I2C1_SLAVE_ADDR,
                                   i2c_clock=TestI2cMasterSlave.I2C_CLOCK_FREQ, i2c_pullups=False)

        requests_pipeline0 = generate_master_write_read_requests(slave_addr=TestI2cMasterSlave.I2C1_SLAVE_ADDR,
                                                                 min_addr=0,
                                                                 max_addr=pm.I2C_SLAVE_BUFFER_SPACE - 1,
                                                                 max_size=TestI2cMasterSlave.DATA_SIZE_MAX,
                                                                 count=TestI2cMasterSlave.REQUEST_COUNT // 4)
        requests_pipeline1 = generate_master_write_read_requests(slave_addr=TestI2cMasterSlave.I2C0_SLAVE_ADDR,
                                                                 min_addr=0,
                                                                 max_addr=pm.I2C_SLAVE_BUFFER_SPACE - 1,
                                                                 max_size=TestI2cMasterSlave.DATA_SIZE_MAX,
                                                                 count=TestI2cMasterSlave.REQUEST_COUNT // 4)
        # requests_pipeline1 = []
        while True:
            i2c_send_master_request(i2c_int0, requests_pipeline0)
            i2c_send_master_request(i2c_int1, requests_pipeline1)

            if serial_port.in_waiting > 0:
                # Read the incoming data
                rx_data = serial_port.read(serial_port.in_waiting)
                tf.accept(rx_data)

            complete_master_requests = verify_master_write_read_requests(i2c_int0)
            if len(complete_master_requests):
                TestI2cMasterSlave.verify_slave_notifications(i2c_int1, complete_master_requests)
            complete_master_requests = verify_master_write_read_requests(i2c_int1)
            if len(complete_master_requests):
                TestI2cMasterSlave.verify_slave_notifications(i2c_int0, complete_master_requests)

            if ((len(requests_pipeline0 + requests_pipeline1) == 0) and
                    (len(i2c_int0.get_pending_master_request_ids() + i2c_int1.get_pending_master_request_ids()) == 0)):
                break
