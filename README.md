## ***microPy-IDE***

## STATUS: Beta release version 0.0.1 04/02/2022.

The *microPy-IDE* is a development environment for the [microPython language](https://micropython.org/) which is a subset of Python 3 and is optimised to run on microcontrollers and in constrained environments. 

Using the familiar Python programming language you can interact with development hardware and control it, much like controlling hardware with an Arduino using C/C++. The Abbykus QDEV family of boards makes it easy to get started using MicroPython and thanks to recent contributions to MicroPython, you can turn a QDEV board into a MicroPython device.


![](https://github.com/Abbykus/microPy-IDE/blob/3a2bbbc565d9bde55c800ac3cb0ba72c25d3f430/photos/microPy-IDE.png)

The *microPy-IDE* runs on a host PC and connects to a target device (QDEV board) via a serial port (USB-serial) or over WiFi. The target device must be running the correct version of the microPython interpreter for the target's specific microcontroller. See [microPython downloads](https://micropython.org/download/).

The *microPy-IDE* allows the user to create, test, and deploy microPython scripts. *microPy-IDE* features include:
- Written in Python 3 using PYQT5 GUI library.
- Runs under Linux, MacOS, and Windows.
- Full featured tabbed text editor with microPython syntax highlighting and 
- Interactive shell to communicate with the Target REPL.
- File viewers for both current project and the file directory on the target.
- Python help using the open source Zeal offline developer help tool.
- Find & replace, bookmarks, Auto-indent, comment/uncomment, etc.
- Templates add common code constructs (user can easily modify).
- microPython control:
  - Reset target.
  - Run a python script from host.
  - Stop a running script.
  - Download files to target file directory.
  - Upload files from target directory.
  - Remove files from target directory.
  - Create new directory on target.
  - Delete target directory.

## DEPENDENCIES
As a prerequisite, the host PC must have Python 3.x and PIP3 installed. 
Your OS likely has Python 3.x installed. If not please google for installation on your OS.

### Install PIP3

- *Linux / MacOS*
  - Launch terminal and type **sudo apt install python3-pip**

- *Windows*
  - See [here](https://stackoverflow.com/questions/70727436/how-to-install-pip3-on-windows-10) for details on Windows installation.

### Install PYQT5
Open a terminal and type **pip3 install PyQt5**

### Install Adafruit Ampy
The 'ampy' application provides communication with and control of the microPython target device (QDEV board). See [MicroPython Basics](https://cdn-learn.adafruit.com/downloads/pdf/micropython-basics-load-files-and-run-code.pdf) for installation instructions.

### Install Zeal (optional)

- *Linux / MacOS*
  - Launch terminal and type **sudo apt install zeal**

- *Windows*

## MicroPython Firmware for the QDEV Boards
All versions of the Abbykus QDEV boards are capable of running the MicroPython interpreted language. 
Please see [MicroPython-python for Microcontrollers](https://micropython.org/) for more information.

To install MicroPython firmware on the QDEV board see [Getting Started with the ESP8266](https://docs.micropython.org/en/latest/esp8266/tutorial/intro.html#intro) ***or*** [Getting Started with the ESP32](https://docs.micropython.org/en/latest/esp32/tutorial/intro.html#esp32-intro).

See also [MicroPython Downloads](https://micropython.org/download/) for the latest firmware releases.

Once you have installed MicroPython on the QDEV board you can connect to the board with the microPy-IDE. You should expect to see a '>>>' prompt in the interactive shell terminal indicating the interactive mode. You can enter MicroPython commands or scripts manually.
If the board fails to connect you may need to set the serial port name and baud rate on the microPython toolbar at the bottom of the microPy-IDE window.






