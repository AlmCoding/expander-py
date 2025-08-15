from interface_expander.InterfaceExpander import InterfaceExpander
from interface_expander.I2cInterface import I2cInterface, I2cConfig, ClockFreq, AddressWidth, I2cId
from interface_expander.Memory import Memory, MemoryType, MemoryAddressWidth


if __name__ == "__main__":
    expander = InterfaceExpander()
    expander.connect()

    cfg0 = I2cConfig(clock_freq=ClockFreq.FREQ1M,
                     slave_addr=0x01,
                     slave_addr_width=AddressWidth.Bits7)
    i2c0 = I2cInterface(i2c_id=I2cId.I2C0, config=cfg0)

    mem = Memory(interface=i2c0, slave_address=0x50, memory_type=MemoryType.FRAM,
                 address_width=MemoryAddressWidth.TWO_BYTES, page_count=1, page_size=pow(2, 15))  # 32 kByte FRAM

    # Read write to memory
    data = mem.read(address=0, length=42)
    mem.write(address=0, data=data)
    mem.flush()

    # Download and upload binary and hex files
    mem.download_bin_file(0, r"littlefs_image.bin")  # mem -> file
    mem.upload_bin_file(0, r"littlefs_image.bin")  # file -> mem

    mem.download_hex_file(0, r"littlefs_image.hex")  # mem -> file
    mem.upload_hex_file(r"littlefs_image.hex")  # file -> mem

    expander.disconnect()
