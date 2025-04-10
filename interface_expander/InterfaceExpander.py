import time
import threading
import serial.tools.list_ports
from interface_expander.tiny_frame import tf_init
from interface_expander.CtrlInterface import CtrlInterface


EXPANDER_INSTANCE = None


class InterfaceExpander:
    def __init__(self):
        self.serial_port = None
        self.tf = None
        self.read_thread = None
        self.running = False

        global EXPANDER_INSTANCE
        EXPANDER_INSTANCE = self

    def __del__(self):
        self.disconnect()
        
        global EXPANDER_INSTANCE
        EXPANDER_INSTANCE = None

    @staticmethod
    def get_port_name() -> str:
        com_ports = serial.tools.list_ports.comports()
        for com_port in com_ports:
            port, desc, hwid = com_port
            if "Serial Device" in desc:
                return port
        raise Exception("No valid Serial Port found!")

    @staticmethod
    def get_serial_port():
        port = serial.Serial(InterfaceExpander.get_port_name(), 115200, timeout=1)
        return port

    def connect(self):
        if self.serial_port and self.serial_port.isOpen():
            return
        self.serial_port = self.get_serial_port()
        self.tf = tf_init(self.serial_port.write)

        self.running = True
        # self.read_thread = threading.Thread(target=self.read)
        # self.read_thread.daemon = True
        # self.read_thread.start()

    def disconnect(self):
        self.running = False
        # if self.read_thread:
        #    self.read_thread.join()
        #    self.read_thread = None

        if self.serial_port and self.serial_port.isOpen():
            self.serial_port.close()
        self.serial_port = None
        self.tf = None

    def reset(self, wait_sec=3):
        self.connect()
        self.running = False
        CtrlInterface.send_system_reset()
        self.disconnect()
        time.sleep(wait_sec)

    """
    def read(self):
        while True:
            time.sleep(1)

        while self.running and self.serial_port and self.serial_port.isOpen():
            if self.serial_port.in_waiting > 0:
                rx_data = self.serial_port.read(self.serial_port.in_waiting)
                self.tf.accept(rx_data)
            time.sleep(0.001)
    """

    def read_all(self):
        if self.serial_port.in_waiting > 0:
            rx_data = self.serial_port.read(self.serial_port.in_waiting)
            self.tf.accept(rx_data)
