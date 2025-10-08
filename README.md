# USB Interface Expander

**`interface-expander`** is a lightweight Python library that allows you to communicate with **USB Interface Expander** devices.  
It provides a simple API for interacting with I²C peripherals and controlling analog outputs (±12 V, 2-channels) directly from Python.

## 🧩 Features

- **USB → I²C bridge** — communicate with I²C sensors and devices from your PC  
- **USB → ±12 V DAC output** — set precise analog voltages from Python  
- **Cross-platform** — works on Windows, macOS, and Linux   
- **Plug-and-play** — automatically detects connected Interface Expander devices (no additional drivers needed)

## 🚀 Getting Started

### ✅ Prerequisites
To use this python library, you will need one of the following two **USB Interface Expander** devices:

- 🔗 [**USB to I²C Converter with GUI**](https://www.tindie.com/products/almcoding/usb-to-i2c-converter-with-gui/)  

- 🔗 [**USB to ±12V DAC Module, 16-bit, 2-Channel Analog**](https://www.tindie.com/products/almcoding/usb-to-12v-dac-module-16-bit-2-channel-analog/)  

![USB Interface Expander](docu/img/expander2_narrow.png)
*Picture of the USB to I²C Converter*

### 📦 Installation

```bash
pip install interface-expander
```

### 💻 Examples

Please checkout this [**folder**](https://github.com/AlmCoding/expander-py/tree/main/examples) for lots of I²C and Analog Output code examples.
