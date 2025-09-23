#!/usr/bin/env python

"""Testing I2c master write/read and slave notifications"""

import pytest
from interface_expander.InterfaceExpander import InterfaceExpander
from interface_expander.I2cInterface import (
    I2cInterface,
    I2cConfig,
    ClockFreq,
    AddressWidth,
    I2cId,
    I2cMasterRequest,
    I2cSlaveRequest,
    I2C_SLAVE_BUFFER_SPACE,
)
from tests.helper import (
    generate_slave_config_requests,
    generate_master_write_read_requests,
    i2c_send_request,
    verify_master_write_read_requests,
)


class TestI2cMasterSlave:
    REQUEST_COUNT = 4 * 2000
    DATA_SIZE_MIN = 1
    DATA_SIZE_MAX = 128

    I2C_CLOCK_FREQ = ClockFreq.FREQ400K
    I2C0_SLAVE_ADDR = 0x01
    I2C1_SLAVE_ADDR = 0x02

    @staticmethod
    def verify_request_notification_flow(i2c_int0: I2cInterface, i2c_int1: I2cInterface):
        access_id_max0 = max(
            [
                0,
            ]
            + list(i2c_int0.get_slave_access_notifications().keys())
        )
        access_id_max1 = max(
            [
                0,
            ]
            + list(i2c_int1.get_slave_access_notifications().keys())
        )
        request_id_max0 = max(
            [
                0,
            ]
            + list(i2c_int0.master_requests.keys())
        )
        request_id_max1 = max(
            [
                0,
            ]
            + list(i2c_int1.master_requests.keys())
        )

        if access_id_max1 > request_id_max0:
            pytest.fail(
                "No corresponding master(0) request for slave(1) access notification (id: %d) found!"
                % (access_id_max1,)
            )

        if access_id_max0 > request_id_max1:
            pytest.fail(
                "No corresponding master(1) request for slave(0) access notification (id: %d) found!"
                % (access_id_max0,)
            )

    @staticmethod
    def verify_slave_notifications(i2c_int: I2cInterface, complete_master_requests: list[I2cMasterRequest]):
        # This only holds true if slave notifications are always serviced before master request responses
        if len(i2c_int.get_slave_access_notifications()) < len(complete_master_requests):
            pytest.fail(
                "More complete master(%d) requests (cnt: %d) than slave notifications (cnt: %d) detected!"
                % (i2c_int.i2c_id.value, len(complete_master_requests), len(i2c_int.get_slave_access_notifications()))
            )
        slave_notifications = i2c_int.pop_slave_access_notifications(len(complete_master_requests)).values()
        slave_id = i2c_int.i2c_id
        master_id = I2cId.I2C0 if slave_id == I2cId.I2C1 else I2cId.I2C1

        for master_req, slave_not in zip(complete_master_requests, slave_notifications):
            if slave_not.access_id != master_req.request_id:
                pytest.fail(
                    "Master(%d) request (id: %d) and slave access (id: %d) id mismatch!"
                    % (i2c_int.i2c_id.value, master_req.request_id, slave_not.access_id)
                )

            if master_req.read_size == 0 and len(master_req.write_data) >= 2:
                # Master write request
                TestI2cMasterSlave.verify_slave_master_write_notification(
                    master_id.value, master_req, slave_id.value, slave_not
                )
            elif master_req.read_size > 0 and len(master_req.write_data) == 2:
                # Master read request
                TestI2cMasterSlave.verify_slave_master_read_notification(
                    master_id.value, master_req, slave_id.value, slave_not
                )
            else:
                pytest.fail(
                    "Master(%d) request (id: %d) invalid configuration (w_size: %d, r_size: %d) detected!"
                    % (i2c_int.i2c_id.value, master_req.request_id, len(master_req.write_data), master_req.read_size)
                )

    @staticmethod
    def verify_slave_master_write_notification(master_id: int, master_req, slave_id: int, slave_not):
        master_req_addr = int.from_bytes(master_req.write_data[:2], byteorder="big")
        slave_not_addr = int.from_bytes(slave_not.write_data[:2], byteorder="big")
        if master_req_addr != slave_not_addr:
            pytest.fail(
                "Master(%d) request (id: %d, write_addr: %d) and "
                "slave(%d) indication (id: %d, write_addr: %d) write_addr mismatch!"
                % (master_id, master_req.request_id, master_req_addr, slave_id, slave_not.access_id, slave_not_addr)
            )

        if master_req.write_data != slave_not.write_data:
            pytest.fail(
                "Master(%d) request (id: %d) and slave(%d) indication (id: %d) write_data (%s != %s) mismatch!"
                % (
                    master_id,
                    master_req.request_id,
                    slave_id,
                    slave_not.access_id,
                    master_req.write_data[2:],
                    slave_not_addr,
                )
            )

    @staticmethod
    def verify_slave_master_read_notification(master_id: int, master_req, slave_id: int, slave_not):
        master_req_addr = int.from_bytes(master_req.write_data[:2], byteorder="big")
        slave_not_addr = int.from_bytes(slave_not.write_data[:2], byteorder="big")
        if master_req_addr != slave_not_addr:
            pytest.fail(
                "Master(%d) request (id: %d, read_addr: %d) and "
                "slave(%d) indication (id: %d, read_addr: %d) read_addr mismatch!"
                % (master_id, master_req.request_id, master_req_addr, slave_id, slave_not.access_id, slave_not_addr)
            )

        if master_req.read_size != len(slave_not.read_data):
            pytest.fail(
                "Master(%d) request (id: %d, read_size: %d) and "
                "slave(%d) indication (id: %d, read_size: %d) read_size mismatch!"
                % (
                    master_id,
                    master_req.request_id,
                    master_req.read_size,
                    slave_id,
                    slave_not.access_id,
                    len(slave_not.read_data),
                )
            )

    def test_i2c_master_slave_write_read(self):
        # Test master and slave simultaneously
        expander = InterfaceExpander()
        expander.reset()
        expander.connect()

        cfg0 = I2cConfig(
            clock_freq=TestI2cMasterSlave.I2C_CLOCK_FREQ,
            slave_addr=0x01,
            slave_addr_width=AddressWidth.Bits7,
            mem_addr_width=AddressWidth.Bits16,
        )
        cfg1 = I2cConfig(
            clock_freq=TestI2cMasterSlave.I2C_CLOCK_FREQ,
            slave_addr=0x02,
            slave_addr_width=AddressWidth.Bits7,
            mem_addr_width=AddressWidth.Bits16,
        )

        i2c0 = I2cInterface(i2c_id=I2cId.I2C0, config=cfg0, callback_fn=None)
        i2c1 = I2cInterface(i2c_id=I2cId.I2C1, config=cfg1, callback_fn=None)
        i2c0.request_id_counter = 0  # Rest request id counter to 0 for request id and notification id matching
        i2c1.request_id_counter = 0  # Rest request id counter to 0 for request id and notification id matching

        requests_pipeline0 = generate_master_write_read_requests(
            slave_addr=TestI2cMasterSlave.I2C1_SLAVE_ADDR,
            min_addr=0,
            max_addr=I2C_SLAVE_BUFFER_SPACE - 1,
            min_size=TestI2cMasterSlave.DATA_SIZE_MIN,
            max_size=TestI2cMasterSlave.DATA_SIZE_MAX,
            count=TestI2cMasterSlave.REQUEST_COUNT // 4,
        )
        requests_pipeline1 = generate_master_write_read_requests(
            slave_addr=TestI2cMasterSlave.I2C0_SLAVE_ADDR,
            min_addr=0,
            max_addr=I2C_SLAVE_BUFFER_SPACE - 1,
            min_size=TestI2cMasterSlave.DATA_SIZE_MIN,
            max_size=TestI2cMasterSlave.DATA_SIZE_MAX,
            count=TestI2cMasterSlave.REQUEST_COUNT // 4,
        )

        while len(requests_pipeline0) > 0 or len(requests_pipeline1) > 0:
            rid = i2c_send_request(i2c0, requests_pipeline0)  # Write data
            i2c0.wait_for_response(request_id=rid, timeout=0.1)
            TestI2cMasterSlave.verify_request_notification_flow(i2c0, i2c1)

            rid = i2c_send_request(i2c0, requests_pipeline0)  # Read data
            i2c0.wait_for_response(request_id=rid, timeout=0.1)
            TestI2cMasterSlave.verify_request_notification_flow(i2c0, i2c1)

            complete_master_requests = verify_master_write_read_requests(i2c0)
            TestI2cMasterSlave.verify_slave_notifications(i2c1, complete_master_requests)

            rid = i2c_send_request(i2c1, requests_pipeline1)
            i2c1.wait_for_response(request_id=rid, timeout=0.1)
            TestI2cMasterSlave.verify_request_notification_flow(i2c1, i2c0)

            rid = i2c_send_request(i2c1, requests_pipeline1)
            i2c1.wait_for_response(request_id=rid, timeout=0.1)
            TestI2cMasterSlave.verify_request_notification_flow(i2c1, i2c0)

            complete_master_requests = verify_master_write_read_requests(i2c1)
            TestI2cMasterSlave.verify_slave_notifications(i2c0, complete_master_requests)

        expander.disconnect()

    @staticmethod
    def generate_master_read_requests(
        slave_addr: int, mem_addr_width: AddressWidth, config_pipeline: list[I2cSlaveRequest]
    ):
        # Generate master read requests
        master_requests = []

        for request in config_pipeline:
            # Generate master read request
            mem_addr = request.write_addr
            read_size = len(request.write_data)
            if mem_addr_width == AddressWidth.Bits8:
                tx_bytes = bytes(mem_addr.to_bytes(1, "big"))
            else:
                tx_bytes = bytes(mem_addr.to_bytes(2, "big"))

            read_request = I2cMasterRequest(slave_addr=slave_addr, write_data=tx_bytes, read_size=read_size)
            master_requests.append(read_request)

        return master_requests

    def test_i2c_master_slave_2byte_mem_address(self):
        # Test master and slave simultaneously
        expander = InterfaceExpander()
        expander.reset()
        expander.connect()

        # Two byte mem address width
        cfg0 = I2cConfig(
            clock_freq=TestI2cMasterSlave.I2C_CLOCK_FREQ,
            slave_addr=0x01,
            slave_addr_width=AddressWidth.Bits7,
            mem_addr_width=AddressWidth.Bits16,
        )  # <========= 2 Bytes
        cfg1 = I2cConfig(
            clock_freq=TestI2cMasterSlave.I2C_CLOCK_FREQ,
            slave_addr=0x02,
            slave_addr_width=AddressWidth.Bits7,
            mem_addr_width=AddressWidth.Bits16,
        )  # <========= 2 Bytes

        i2c0 = I2cInterface(i2c_id=I2cId.I2C0, config=cfg0, callback_fn=None)
        i2c1 = I2cInterface(i2c_id=I2cId.I2C1, config=cfg1, callback_fn=None)
        i2c0.request_id_counter = 0  # Rest request id counter to 0 for request id and notification id matching
        i2c1.request_id_counter = 0  # Rest request id counter to 0 for request id and notification id matching

        config_pipeline = generate_slave_config_requests(
            min_addr=0,
            max_addr=I2C_SLAVE_BUFFER_SPACE - 1,
            min_size=TestI2cMasterSlave.DATA_SIZE_MIN,
            max_size=TestI2cMasterSlave.DATA_SIZE_MAX,
            count=TestI2cMasterSlave.REQUEST_COUNT // 4,
            with_read=False,
        )  # Only write config requests needed
        read_pipeline = TestI2cMasterSlave.generate_master_read_requests(
            slave_addr=cfg0.slave_addr, mem_addr_width=cfg0.mem_addr_width, config_pipeline=config_pipeline
        )

        while len(config_pipeline) > 0 or len(read_pipeline) > 0:
            rid = i2c_send_request(i2c0, config_pipeline)  # Send slave configuration (write)
            write_req = i2c0.wait_for_response(request_id=rid, timeout=0.1)

            rid = i2c_send_request(i2c1, read_pipeline)  # Read slave configuration using i2c
            notification = i2c0.wait_for_slave_notification(access_id=None, timeout=0.1)
            read_req = i2c1.wait_for_response(request_id=rid, timeout=0.1)

            assert read_req.read_data == write_req.write_data
            assert read_req.read_data == notification.read_data

    def test_i2c_master_slave_1byte_mem_address(self):
        # Test master and slave simultaneously
        expander = InterfaceExpander()
        expander.reset()
        expander.connect()

        # Two byte mem address width
        cfg0 = I2cConfig(
            clock_freq=TestI2cMasterSlave.I2C_CLOCK_FREQ,
            slave_addr=0x01,
            slave_addr_width=AddressWidth.Bits7,
            mem_addr_width=AddressWidth.Bits8,
        )  # <========= 1 Byte
        cfg1 = I2cConfig(
            clock_freq=TestI2cMasterSlave.I2C_CLOCK_FREQ,
            slave_addr=0x02,
            slave_addr_width=AddressWidth.Bits7,
            mem_addr_width=AddressWidth.Bits8,
        )  # <========= 1 Byte

        i2c0 = I2cInterface(i2c_id=I2cId.I2C0, config=cfg0, callback_fn=None)
        i2c1 = I2cInterface(i2c_id=I2cId.I2C1, config=cfg1, callback_fn=None)
        i2c0.request_id_counter = 0  # Rest request id counter to 0 for request id and notification id matching
        i2c1.request_id_counter = 0  # Rest request id counter to 0 for request id and notification id matching

        config_pipeline = generate_slave_config_requests(
            min_addr=0,
            max_addr=pow(2, 8) - 1,
            min_size=TestI2cMasterSlave.DATA_SIZE_MIN,
            max_size=TestI2cMasterSlave.DATA_SIZE_MAX,
            count=TestI2cMasterSlave.REQUEST_COUNT // 4,
            with_read=False,
        )  # Only write config requests needed
        read_pipeline = TestI2cMasterSlave.generate_master_read_requests(
            slave_addr=cfg0.slave_addr, mem_addr_width=cfg0.mem_addr_width, config_pipeline=config_pipeline
        )

        while len(config_pipeline) > 0 or len(read_pipeline) > 0:
            rid = i2c_send_request(i2c0, config_pipeline)  # Send slave configuration (write)
            write_req = i2c0.wait_for_response(request_id=rid, timeout=0.1)

            rid = i2c_send_request(i2c1, read_pipeline)  # Read slave configuration using i2c
            notification = i2c0.wait_for_slave_notification(access_id=None, timeout=0.1)
            read_req = i2c1.wait_for_response(request_id=rid, timeout=0.1)

            assert read_req.read_data == write_req.write_data
            assert read_req.read_data == notification.read_data
