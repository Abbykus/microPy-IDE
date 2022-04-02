## ***microPy-IDE***

## STATUS: Beta release version 0.0.1 04/02/2022.

The *microPy-IDE* is a development environment for the [microPython language](https://micropython.org/) which is a subset of Python 3 and is optimised to run on microcontrollers and in constrained environments. 

Using the familiar Python programming language you can interact with development hardware and control it, much like controlling hardware with an Arduino using C/C++. The QDEV family of boards makes it easy to get started using MicroPython and thanks to recent contributions to MicroPython, you can turn a QDEV board into a MicroPython device.

![](https://github.com/Abbykus/microPy-IDE/blob/3a2bbbc565d9bde55c800ac3cb0ba72c25d3f430/photos/microPy-IDE.png)

The *microPy-IDE* runs on a host PC and connects to a target device (QDEV board) via a serial port (USB-serial) or over WiFi. The target device must be running the correct version of the microPython interpreter for the targets specific microcontroller. See [microPython downloads](https://micropython.org/download/).

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
As a prerequisite, the host PC must have Python 3 and PIP3 installed. 
Your OS likely has Python 3.x installed. See the following to install **PIP3:**

  #### *Linux / MacOS*
    Launch terminal and type **sudo apt install python3-pip**

  #### *Windows*
  See [here](https://stackoverflow.com/questions/70727436/how-to-install-pip3-on-windows-10) for details on Windows installation.

### Install PYQT5
Open a terminal and type **pip3 install PyQt5**

### Install Adafruit Ampy
This application provides communication with the target device. See [MicroPython Basics](https://cdn-learn.adafruit.com/downloads/pdf/micropython-basics-load-files-and-run-code.pdf) for installation instructions.

### Install Zeal (optional)


## MicroPython ON THE QDEV Boards
All versions of the Abbykus QDEV boards are capable of running the MicroPython interpreted language. MicroPython is a compact Python interpreter that can run on embedded platforms. Using the familiar Python programming language you can talk to hardware and control it, much like controlling hardware with an Arduino or other embedded boards. The QDEV ESP8266 board makes it easy to get started using MicroPython and thanks to recent contributions to MicroPython, you can turn a QDEV-ESP8266 into a MicroPython device.

Please read MicroPython language and implementation for more information.

INSTALL MICROPYTHON
To install MicroPython firmware on the QDEV-ESP8266 board see Quick reference for the ESP8266.

Also see MicroPython for the ESP8266 for the latest firmware release.

Once you have installed MicroPython on the QDEV ESP8266 board you can connect to the board via the Serial monitor in your development environment or a serial terminal emulator such as screen for Linux. You should expect to see a '>>>' prompt indicating the interactive mode where you can enter MicroPython commands or entire scripts manually.





