## ***microPy-IDE***

The *microPy-IDE* is a development environment for the [microPython language](https://micropython.org/) which is a subset of Python 3 and is optimised to run on microcontrollers and in constrained environments. 

![](https://github.com/Abbykus/microPy-IDE/blob/3a2bbbc565d9bde55c800ac3cb0ba72c25d3f430/photos/microPy-IDE.png)

*microPy* runs on a host PC and connects to a target device (QDEV board) via a serial port. The target device must be running the correct version of the microPython interpreter for the targets specific microcontroller, see [microPython download](https://micropython.org/download/).

*microPy* allows the user to create, test, and deploy microPython scripts. *microPy* features:
- Written in Python 3 using PYQT5 GUI library.
- Runs under Linux, MacOS, and Windows.
- Full featured tabbed text editor with microPython syntax highlighting.
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



