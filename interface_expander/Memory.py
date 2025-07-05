from interface_expander.I2cInterface import I2cInterface, I2cMasterRequest, I2cStatusCode, I2C_MAX_READ_SIZE, \
    I2C_MAX_WRITE_SIZE
from intelhex import IntelHex
from enum import Enum


class MemoryType(Enum):
    FRAM = 0  # No write status polling required
    EEPROM = 1  # Requires write status polling
    FLASH = 2  # Requires erase before write


class MemoryAddressWidth(Enum):
    ONE_BYTE = 1
    TWO_BYTES = 2
    THREE_BYTES = 3
    FOUR_BYTES = 4


class Memory:
    def __init__(self, interface: I2cInterface, slave_address: int, memory_type: MemoryType,
                 address_width: MemoryAddressWidth, page_count: int, page_size: int):
        self.interface = interface
        self.slave_address = slave_address
        self.memory_type = memory_type
        self.address_width = address_width
        self.page_count = page_count
        self.page_size = page_size

        self.memory_size = page_count * page_size
        # Some i2c memories use bits in the slave address to extend the address space
        self.additional_address_bits = 0
        if self.memory_size.bit_length() > self.address_width.value * 8:
            # Use address bit(s) in slave address byte
            self.additional_address_bits = (self.memory_size - 1).bit_length() - self.address_width.value * 8

        self.buffer = bytearray(self.memory_size)
        self.updated_sections = list()

    def _pack_slave_address(self, address: int) -> None:
        # Pack the additional address bits into the slave address byte (used by some FRAMs/EEPROMs)
        additional_address = address >> (self.address_width.value * 8)
        if additional_address.bit_length() > self.additional_address_bits:
            raise ValueError(f"Address {address} exceeds the maximum allowed with additional address bits!")
        self.slave_address = (self.slave_address & ~((1 << self.additional_address_bits) - 1) - 1) | (
                    additional_address << 1)

    def read(self, address: int, length: int) -> bytes:
        if length == -1:
            length = self.memory_size - address
        if length < 0 or address < 0 or address + length > self.memory_size:
            raise ValueError("Invalid address or length for read operation!")

        request_count = length // I2C_MAX_READ_SIZE + 1
        for i in range(request_count):
            offset = i * I2C_MAX_READ_SIZE
            current_address = address + offset
            read_length = min(I2C_MAX_READ_SIZE, length - offset)

            address_bytes = current_address.to_bytes(self.address_width.value, 'big')
            if self.additional_address_bits > 0:
                self._pack_slave_address(current_address)  # Part of the address is in the slave address byte

            request = I2cMasterRequest(
                slave_addr=self.slave_address,
                write_data=address_bytes,
                read_size=read_length
            )
            rid = self.interface.send_request(request=request)
            response = self.interface.wait_for_response(request_id=rid, timeout=0.1)
            if response.status_code != I2cStatusCode.SUCCESS:
                raise ValueError(f"Failed to read from memory at address {current_address}: {response.status_code}")

            self.buffer[current_address:current_address + read_length] = response.read_data

        return bytes(self.buffer[address:address + length])

    def write(self, address: int, data: bytes) -> None:
        if address < 0 or address + len(data) > self.memory_size:
            raise ValueError("Invalid address or data length for write operation!")

        self.buffer[address:address + len(data)] = data

        section_start = address
        section_end = address + len(data)
        for i, section in enumerate(self.updated_sections):
            start, end = section
            if start <= section_start and section_end <= end:  # Contained within existing section
                return
            elif section_start <= start and section_end >= end:  # Wraps entire section
                del self.updated_sections[i]
            elif start <= section_start <= end:  # Overlaps with start of existing section (or follows directly)
                del self.updated_sections[i]
                section_start = start
            elif start <= section_end <= end:  # Overlaps with end of existing section (or precedes directly)
                del self.updated_sections[i]
                section_end = end
            else:
                continue

        # Add the new section
        self.updated_sections.append((section_start, section_end))

    def flush(self) -> None:
        for section_start, section_end in self.updated_sections:
            if section_start < 0 or section_end > self.memory_size:
                raise ValueError("Invalid section range for flush operation!")

            self._flush_section(section_start, section_end)

        self.updated_sections.clear()

    def _flush_section(self, section_start: int, section_end: int) -> None:
        address = section_start
        length = section_end - section_start
        request_count = length // (I2C_MAX_WRITE_SIZE - self.address_width.value) + 1

        for i in range(request_count):
            offset = i * I2C_MAX_WRITE_SIZE
            current_address = address + offset
            write_length = min(I2C_MAX_WRITE_SIZE - self.address_width.value, length - offset)
            data = self.buffer[current_address:current_address + write_length]

            address_bytes = current_address.to_bytes(self.address_width.value, 'big')
            if self.additional_address_bits > 0:
                self._pack_slave_address(current_address)  # Part of the address is in the slave address byte

            self._send_write_request(address_bytes + data)

    def _send_write_request(self, write_data: bytes) -> None:
        max_retries = 100
        retry_counter = 0
        while retry_counter < max_retries:
            request = I2cMasterRequest(
                slave_addr=self.slave_address,
                write_data=write_data,
                read_size=0
            )
            rid = self.interface.send_request(request=request)
            response = self.interface.wait_for_response(request_id=rid, timeout=0.1)

            if response.status_code == I2cStatusCode.SUCCESS:
                break
            elif response.status_code == I2cStatusCode.SLAVE_NO_ACK:
                retry_counter += 1
                continue  # If the memory is busy, we may need to wait and retry
            else:
                raise ValueError(f"Failed to flush memory: {response.status_code}")

        if retry_counter >= max_retries:
            raise TimeoutError(f"Failed to write to memory after {max_retries} retries!")

    def upload_bin_file(self, address: int, file_path: str) -> None:
        # Read data from file and write to memory
        with open(file_path, 'rb') as file:
            data = file.read()
            self.write(address, data)
            self.flush()

    def download_bin_file(self, address: int, file_path: str) -> None:
        # Read data from memory and save to file
        data = self.read(address, -1)
        with open(file_path, 'wb') as file:
            file.write(data)

    def upload_hex_file(self, file_path: str) -> None:
        # Read data from hex file and write to memory
        ih = IntelHex(file_path)
        for address, data in ih.todict().items():
            self.write(address, bytes([data]))
        self.flush()

    def download_hex_file(self, address: int, file_path: str) -> None:
        # Read data from memory and save to hex file
        ih = IntelHex()
        data = self.read(address, -1)
        ih.frombytes(data, offset=address)
        ih.tofile(file_path, format='hex')
