# ***microPy-IDE***

## STATUS: Beta release version 0.1.0 04/17/2022.

The *microPy-IDE* is a development environment for the [microPython language](https://micropython.org/) which is a subset of Python 3 and is optimised to run on microcontrollers and in constrained environments. 

Using the familiar Python programming language you can interact with development hardware and control it, much the same as controlling hardware with the Arduino IDE using C/C++. The Abbykus QDEV family of boards makes it easy to get started using MicroPython and thanks to recent contributions to MicroPython, you can turn any QDEV board into a MicroPython device.


![](https://github.com/Abbykus/microPy-IDE/blob/3a2bbbc565d9bde55c800ac3cb0ba72c25d3f430/photos/microPy-IDE.png)

The *microPy-IDE* runs on a host PC and connects to a target device (QDEV board) via a serial port (USB-serial) or over WiFi. The target device must be running the correct version of the microPython interpreter for the target's specific microcontroller. See [microPython downloads](https://micropython.org/download/).

The *microPy-IDE* allows the user to create, test, and deploy microPython scripts. *microPy-IDE* features include:
- Written in Python 3 using PYQT5 GUI library.
- Runs under Linux, MacOS, and Windows.
- Full featured tabbed text editor with microPython syntax highlighting and intuitive keyword look-ahead.
- Interactive shell to communicate with the Target REPL.
- File viewers for both current project and the file directory on the target.
- Python help using the open source Zeal offline developer reference tool.
- Find & replace, bookmarks, Auto-indent, comment/uncomment, etc.
- Templates add common code constructs (user can easily add/modify).
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
As a prerequisite, the host PC must have at least Python 3.6 and PIP3 installed. 
Your OS likely has Python 3.x installed. If not please google for installation on your OS.
If the version of Python is lower than 3.6 please consider upgrading to the latest release.

### Install PIP3
- *Linux / MacOS*
  - Launch terminal and type **sudo apt install python3-pip**

- *Windows*
  - See [here](https://stackoverflow.com/questions/70727436/how-to-install-pip3-on-windows-10) for details on Windows installation.

### Install PYQT5 GUI Widgets Toolkit
Open a terminal and type **pip3 install pyqt5 pyqt5-tools**

### Install Zeal Offline Language Reference (optional)
- *Linux / MacOS*
  - Launch terminal and type **sudo apt install zeal**

- *Windows*

After installing *zeal*, launch it and goto ***tools->docsets*** and add Python language support.

## MicroPython Firmware for the QDEV Boards
All versions of the Abbykus QDEV boards are capable of running the MicroPython language. 
Please see [MicroPython-python for Microcontrollers](https://micropython.org/) for more information.

To install MicroPython firmware on the QDEV board see [Getting Started with the ESP8266](https://docs.micropython.org/en/latest/esp8266/tutorial/intro.html#intro) ***or*** [Getting Started with the ESP32](https://docs.micropython.org/en/latest/esp32/tutorial/intro.html#esp32-intro).

See also [MicroPython Downloads](https://micropython.org/download/) for the latest firmware releases.

Once you have installed MicroPython on the QDEV board you can connect to the board with the microPy-IDE. 
First set the serial port name, on Linux typically /dev/ttyUSB0. Also set the baudrate to 115200.
Reset the target board and you should expect to see a '>>>' prompt in the interactive shell terminal indicating the interactive mode. You can enter MicroPython commands or scripts manually.







