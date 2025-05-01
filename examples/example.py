from interface_expander.InterfaceExpander import InterfaceExpander
from interface_expander.I2cInterface import I2cInterface, I2cConfig, ClockFreq, AddressWidth, I2cId, I2cMasterRequest


def complete_cb(request):
    print(f"Request complete cb (rid: {request.request_id}, status: {request.status_code}, "
          f"write_data: {request.write_data}, read_data: {request.read_data})")


if __name__ == "__main__":
    expander = InterfaceExpander()
    expander.connect()

    cfg0 = I2cConfig(clock_freq=ClockFreq.FREQ400K,
                     slave_addr=0x01,
                     slave_addr_width=AddressWidth.Bits7,
                     mem_addr_width=AddressWidth.Bits16)
    i2c0 = I2cInterface(i2c_id=I2cId.I2C0, config=cfg0)

    request = I2cMasterRequest(slave_addr=0x50, write_data=bytes([0x00, 0x01, 0x42]), read_size=0,
                               callback_fn=complete_cb)
    rid = i2c0.send_request(request=request)
    req = i2c0.wait_for_response(request_id=rid, timeout=0.02)

    expander.disconnect()
