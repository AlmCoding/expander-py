import time

# import threading
import serial.tools.list_ports
from interface_expander.tiny_frame import tf_init
from interface_expander.CtrlInterface import CtrlInterface
from interface_expander.Singleton import Singleton


class InterfaceExpander(metaclass=Singleton):
    VendorIds = [1155]
    ProductIds = [22288]
    SerialNumbers = ["EXPV1"]

    def __init__(self):
        self.serial_port = None
        self.tf = None
        # self.read_thread = None
        # self.running = False

    @staticmethod
    def _get_port_name() -> str:
        com_ports = serial.tools.list_ports.comports()
        for com_port in com_ports:
            if (
                com_port.vid in InterfaceExpander.VendorIds
                and com_port.pid in InterfaceExpander.ProductIds
                and com_port.serial_number in InterfaceExpander.SerialNumbers
            ):
                return com_port.device
        raise Exception("No valid Serial Port found!")

    @staticmethod
    def _get_serial_port():
        port = serial.Serial(InterfaceExpander._get_port_name(), baudrate=115200, timeout=1.0)
        return port

    def connect(self):
        if self.serial_port and self.serial_port.isOpen():
            return
        self.serial_port = self._get_serial_port()
        self.tf = tf_init(self.serial_port.write)

        # self.running = True
        # self.read_thread = threading.Thread(target=self._read_loop)
        # self.read_thread.daemon = True
        # self.read_thread.start()

    def disconnect(self):
        # self.running = False
        # if self.read_thread:
        #    self.read_thread.join()
        #    self.read_thread = None

        if self.serial_port and self.serial_port.isOpen():
            self.serial_port.close()
        self.serial_port = None
        self.tf = None

    def reset(self, wait_sec=3):
        self.connect()
        # self.running = False
        CtrlInterface()._send_system_reset()
        self.disconnect()
        time.sleep(wait_sec)

    def _read_all(self):
        if self.serial_port.in_waiting > 0:
            rx_data = self.serial_port.read(self.serial_port.in_waiting)
            self.tf.accept(rx_data)

    """
    def _read_loop(self):
        while self.running and self.serial_port and self.serial_port.isOpen():
            if self.serial_port.in_waiting > 0:
                rx_data = self.serial_port.read(self.serial_port.in_waiting)
                self.tf.accept(rx_data)
            time.sleep(0.001)
    """
