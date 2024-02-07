#!/usr/bin/env python

""" Testing I2c slave write and read memory updates (no physical I2c communication involved)
"""

import pytest
import serial
from msg import tiny_frame
from msg import proto_i2c_msg as pm
from helper import (get_com_port, generate_master_write_read_requests)


@pytest.fixture()
def serial_port():
    with serial.Serial(get_com_port(), 115200, timeout=1) as ser:
        yield ser


class TestI2cMaster:
    REQUEST_COUNT = 10
    DATA_SIZE_MIN = 1
    DATA_SIZE_MAX = 64 - tiny_frame.TF_FRAME_OVERHEAD_SIZE - 24

    @staticmethod
    def i2c_send_master_request(i2c_int: pm.I2cInterface, request_queue: list[pm.I2cMasterRequest]):
        if len(i2c_int.get_pending_master_request_ids()) > 0:
            return

        if len(request_queue) and i2c_int.can_accept_request(request_queue[0]):
            request = request_queue.pop(0)
            rid = i2c_int.send_master_request_msg(request=request)
            # print("Req: {}, w_addr: '{}', w_data: {} ({}), r_size: {}".format(rid, request.write_data[:2].hex(),
            #                                                                  request.write_data[2:],
            #                                                                  len(request.write_data[2:]),
            #                                                                  request.read_size))
            assert len(i2c_int.get_pending_master_request_ids()) > 0

    @staticmethod
    def verify_master_write_read_requests(i2c_int: pm.I2cInterface):
        complete_count = len(i2c_int.get_complete_master_request_ids())
        if (complete_count % 2 != 0) or (complete_count == 0):
            return

        previous_write_request = None
        for request in i2c_int.pop_complete_master_requests().values():
            assert request.status_code == pm.I2cMasterStatusCode.COMPLETE
            if request.read_size == 0:  # Write request
                assert len(request.write_data) > 0
                previous_write_request = request
            else:  # Read request
                assert request.read_data == previous_write_request.write_data[2:]

    def test_i2c_master_write_read(self, serial_port):
        tf = tiny_frame.tf_init(serial_port.write)
        i2c_int0 = pm.I2cInterface(i2c_id=pm.I2cId.I2C0, i2c_addr=0x01, i2c_clock=400000, i2c_pullups=True)
        i2c_int1 = pm.I2cInterface(i2c_id=pm.I2cId.I2C1, i2c_addr=0x02, i2c_clock=400000, i2c_pullups=False)

        requests_pipeline0 = generate_master_write_read_requests(slave_addr=0x02,
                                                                 min_addr=0, max_addr=pm.I2C_SLAVE_BUFFER_SPACE - 1,
                                                                 max_size=TestI2cMaster.DATA_SIZE_MAX,
                                                                 count=TestI2cMaster.REQUEST_COUNT // 4)
        requests_pipeline1 = generate_master_write_read_requests(slave_addr=0x01,
                                                                 min_addr=0, max_addr=pm.I2C_SLAVE_BUFFER_SPACE - 1,
                                                                 max_size=TestI2cMaster.DATA_SIZE_MAX,
                                                                 count=TestI2cMaster.REQUEST_COUNT // 4)
        while True:
            TestI2cMaster.i2c_send_master_request(i2c_int0, requests_pipeline0)
            TestI2cMaster.i2c_send_master_request(i2c_int1, requests_pipeline1)

            if serial_port.in_waiting > 0:
                # Read the incoming data
                rx_data = serial_port.read(serial_port.in_waiting)
                tf.accept(rx_data)

            TestI2cMaster.verify_master_write_read_requests(i2c_int0)
            TestI2cMaster.verify_master_write_read_requests(i2c_int1)

            if ((len(requests_pipeline0 + requests_pipeline1) == 0) and
                    (len(i2c_int0.get_pending_master_request_ids() + i2c_int1.get_pending_master_request_ids()) == 0)):
                break
