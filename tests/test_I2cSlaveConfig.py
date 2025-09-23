#!/usr/bin/env python

"""Testing I2c slave write and read memory updates (no physical I2c communication involved)"""

from interface_expander.InterfaceExpander import InterfaceExpander
from interface_expander.I2cInterface import (
    I2cInterface,
    I2cConfig,
    ClockFreq,
    AddressWidth,
    I2cId,
    I2C_SLAVE_BUFFER_SPACE,
    I2cStatusCode,
)
from tests.helper import generate_slave_config_requests, i2c_send_request


class TestI2cSlaveConfig:
    REQUEST_COUNT = 4 * 1000
    DATA_SIZE_MIN = 1
    DATA_SIZE_MAX = 128

    I2C_CLOCK_FREQ = ClockFreq.FREQ400K
    I2C0_SLAVE_ADDR = 0x01
    I2C1_SLAVE_ADDR = 0x02

    @staticmethod
    def verify_requests(i2c_int):
        assert len(i2c_int.get_pending_slave_request_ids()) == 0

        complete_count = len(i2c_int.get_complete_slave_request_ids())
        if (complete_count % 2 != 0) or (complete_count == 0):
            return

        previous_write_request = None
        for request in i2c_int.pop_complete_slave_requests().values():
            assert request.status_code == I2cStatusCode.SUCCESS
            if request.read_size == 0:  # Write request
                assert len(request.write_data) > 0
                previous_write_request = request
            else:  # Read request
                assert request.read_data == previous_write_request.write_data

    def test_i2c_slave_write_read(self):
        expander = InterfaceExpander()
        expander.reset()
        expander.connect()

        cfg0 = I2cConfig(
            clock_freq=TestI2cSlaveConfig.I2C_CLOCK_FREQ,
            slave_addr=0x01,
            slave_addr_width=AddressWidth.Bits7,
            mem_addr_width=AddressWidth.Bits16,
        )
        cfg1 = I2cConfig(
            clock_freq=TestI2cSlaveConfig.I2C_CLOCK_FREQ,
            slave_addr=0x02,
            slave_addr_width=AddressWidth.Bits7,
            mem_addr_width=AddressWidth.Bits16,
        )

        i2c0 = I2cInterface(i2c_id=I2cId.I2C0, config=cfg0, callback_fn=None)
        i2c1 = I2cInterface(i2c_id=I2cId.I2C1, config=cfg1, callback_fn=None)

        requests_pipeline0 = generate_slave_config_requests(
            min_addr=0,
            max_addr=I2C_SLAVE_BUFFER_SPACE - 1,
            min_size=TestI2cSlaveConfig.DATA_SIZE_MIN,
            max_size=TestI2cSlaveConfig.DATA_SIZE_MAX,
            count=TestI2cSlaveConfig.REQUEST_COUNT // 4,
        )
        requests_pipeline1 = generate_slave_config_requests(
            min_addr=0,
            max_addr=I2C_SLAVE_BUFFER_SPACE - 1,
            min_size=TestI2cSlaveConfig.DATA_SIZE_MIN,
            max_size=TestI2cSlaveConfig.DATA_SIZE_MAX,
            count=TestI2cSlaveConfig.REQUEST_COUNT // 4,
        )

        while len(requests_pipeline0) > 0 or len(requests_pipeline1) > 0:
            _ = i2c_send_request(i2c0, requests_pipeline0)  # Write data
            ridr = i2c_send_request(i2c0, requests_pipeline0)  # Read data
            i2c0.wait_for_response(request_id=ridr, timeout=0.1)
            TestI2cSlaveConfig.verify_requests(i2c0)

            _ = i2c_send_request(i2c1, requests_pipeline1)
            ridr = i2c_send_request(i2c1, requests_pipeline1)
            i2c1.wait_for_response(request_id=ridr, timeout=0.1)
            TestI2cSlaveConfig.verify_requests(i2c1)

        expander.disconnect()
