import tf.TinyFrame as TF
from enum import Enum
import proto_uart_msg as pm_uart
import proto_gpio_msg as pm_gpio


class TfMsgType(Enum):
    TYPE_CTRL = 0x00
    TYPE_UART = 0x01
    TYPE_I2C = 0x02
    TYPE_SPI = 0x03
    TYPE_CAN = 0x04
    TYPE_GPIO = 0x05
    TYPE_PWM = 0x06
    TYPE_ADC = 0x07


def tf_init(write_callback):
    tf = TF.TinyFrame()
    tf.SOF_BYTE = 0x01
    tf.ID_BYTES = 1
    tf.LEN_BYTES = 1
    tf.TYPE_BYTES = 1
    tf.CKSUM_TYPE = 'xor'
    tf.write = write_callback

    # Add frame type listeners
    tf.add_fallback_listener(fallback_listener)
    tf.add_type_listener(TfMsgType.TYPE_UART.value, uart_listener)
    tf.add_type_listener(TfMsgType.TYPE_GPIO.value, gpio_listener)
    return tf


def fallback_listener(tf, msg):
    print("Fallback listener")
    print(msg.data)


def uart_listener(tf, msg):
    pm_uart.decode_uart_msg(bytes(msg.data))


def gpio_listener(tf, msg):
    pm_gpio.decode_gpio_msg(bytes(msg.data))
