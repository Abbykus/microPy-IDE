#!/usr/bin/env python
"""
-------------------------------------------------------------------------------
Copyright (c) 2016 Adafruit Industries

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
-------------------------------------------------------------------------------
pyboard interface

This module provides the Pyboard class, used to communicate with and
control the pyboard over a serial USB connection.

Example usage:

    import pyboard
    pyb = pyboard.Pyboard('/dev/ttyACM0')

Or:

    pyb = pyboard.Pyboard('192.168.1.1')

Then:

    pyb.enter_raw_repl()
    pyb.exec('pyb.LED(1).on()')
    pyb.exit_raw_repl()

Note: if using Python2 then pyb.exec must be written as pyb.exec_.
To run a script from the local machine on the board and print out the results:

    import pyboard
    pyboard.execfile('test.py', device='/dev/ttyACM0')

This script can also be run directly.  To execute a local script, use:

    ./pyboard.py test.py

Or:

    python pyboard.py test.py

Abbykus: Note that this software has been modified to incorporate it into the microPy-IDE application.
Modifications include:
* Supported only by Python 3.x
* Removed CLI support

J. Hoeppner@Abbykus 2022

"""
import sys
import time
from PyQt5.QtSerialPort import QSerialPort, QSerialPortInfo
from PyQt5.QtCore import QIODevice, QBuffer, QByteArray
from PyQt5.QtGui import QTextCursor
import serial
import binascii
# import settings
# import mpconfig
# from threading import Thread
# stdout = sys.stdout.buffer


class PyboardError(BaseException):
    pass

class TelnetToSerial:
    def __init__(self, ip, user, password, read_timeout=None):
        import telnetlib
        self.tn = telnetlib.Telnet(ip, timeout=15)
        self.read_timeout = read_timeout
        if b'Login as:' in self.tn.read_until(b'Login as:', timeout=read_timeout):
            self.tn.write(bytes(user, 'ascii') + b"\r\n")

            if b'Password:' in self.tn.read_until(b'Password:', timeout=read_timeout):
                # needed because of internal implementation details of the telnet server
                time.sleep(0.2)
                self.tn.write(bytes(password, 'ascii') + b"\r\n")

                if b'for more information.' in self.tn.read_until(b'Type "help()" for more information.', timeout=read_timeout):
                    # login succesful
                    from collections import deque
                    self.fifo = deque()
                    return

        raise PyboardError('Failed to establish a telnet connection with the board')

    def __del__(self):
        self.close()

    def close(self):
        try:
            self.tn.close()
        except:
            # the telnet object might not exist yet, so ignore this one
            pass

    def read(self, size=1):
        while len(self.fifo) < size:
            timeout_count = 0
            data = self.tn.read_eager()
            if len(data):
                self.fifo.extend(data)
                timeout_count = 0
            else:
                time.sleep(0.25)
                if self.read_timeout is not None and timeout_count > 4 * self.read_timeout:
                    break
                timeout_count += 1

        data = b''
        while len(data) < size and len(self.fifo) > 0:
            data += bytes([self.fifo.popleft()])
        return data

    def write(self, data):
        self.tn.write(data)
        return len(data)

    def inWaiting(self):
        n_waiting = len(self.fifo)
        if not n_waiting:
            data = self.tn.read_eager()
            self.fifo.extend(data)
            return len(data)
        else:
            return n_waiting

class Pyboard:
    def __init__(self, shelltext, device, baud, user='micro', password='python', wait=0):

        self._device = device
        self._baudrate = baud
        self.shelltext = shelltext
        self.cursor = QTextCursor()

        # text flags
        self.ignoreSerial = False
        self.block_cr = False
        self.block_echo = False

        # device = '192.168.4.1'

        if device and device[0].isdigit() and device[-1].isdigit() and device.count('.') == 3:
            # device looks like an IP address
            self.serialport = TelnetToSerial(device, user, password, read_timeout=10)
        else:
            self.serialport = QSerialPort()
            self.setSerialPortName(device)
            self.setSerialPortBaudrate(baud)
            self.serialport.setFlowControl(QSerialPort.HardwareControl)
            self.serialport.readyRead.connect(self.serialReadyRead)
            if self.serialport.open(QIODevice.ReadWrite):
                self.shelltext.append('Serial port ' + device + ' is open.')
            else:
                self.shelltext.append('Error: Cannot open serial port ' + device)


    def stdout_write_bytes(self, b):
        b = b.replace(b"\x04", b"")
        self.shelltext.insertPlainText(b.decode('utf-8'))

    def serialWrite(self, databytes):
        self.serialport.write(databytes)

    def hardReset(self):
        data = b''
        if self.serialport.isOpen():
            self.ignoreSerial = True
            self.serialport.flush()
            if self.serialport.isDataTerminalReady():   # hack for windoze 10
                self.serialport.setDataTerminalReady(False)
                time.sleep(0.1)
                self.serialport.setDataTerminalReady(True)
            else:
                self.serialport.close()     # close pyqt5 serialport and open pyserial port
                ser = serial.Serial(self._device)   # use pyserial to hack dtr bug
                ser.setDTR(False)
                time.sleep(0.1)
                ser.setDTR(True)
                ser.close()
                self.serialport.open(QIODevice.ReadWrite)
            time.sleep(0.1)
            data = self.read_until(1, b'>>>', 2)
            # if data.endswith(b'>>>'):
            #     # data1 = self.read_until(1, b'>>>', 2)
            #     # if data1.endswith(b'>>>'):
            #     #     data += data1
            #     # begin = data.index(b'MicroPython')
            #     # data = data[begin:]
            # else:
            #     data = b''

        self.ignoreSerial = False
        return data

    def stopScript(self):
        if self.serialport.isOpen():
            # ctrl-C twice: interrupt any running program
            self.serialport.write(b'\r\x03')
            time.sleep(0.1)
            self.serialport.write(b'\x03')
            time.sleep(0.1)

    def isSerialOpen(self):
        return self.serialport.isOpen()

    def setSerialPortName(self, device):        # device is string name of system serial port
        self._device = device
        self.serialport.setPortName(device)     # serial port, example - 'COM1' or '/dev/ttyUSB0'

    def setSerialPortBaudrate(self, baud):      # baud is a string
        self._baudrate = baud
        self.serialport.setBaudRate(int(baud))  # must convert baudrate str to int

    def serialClose(self):
        self.serialport.close()

    def serialOpen(self):
        if self.serialport.isOpen():    # if it's open, close then reopen
            self.serialport.close()
        self.setSerialPortName(self._device)
        self.setSerialPortBaudrate(self._baudrate)
        return self.serialport.open(QIODevice.ReadWrite)    # return true on open success

    def serialReadyRead(self):
        if self.ignoreSerial:
            return
        backspc = False
        serialBytes = bytes(self.serialport.readAll())
        outstr = ''
        i = 0
        # strip non-ascii bytes from serial data
        while i < len(serialBytes):
            # print(hex(serialBytes[i]), end=',')
            # filter out leading cr/lf that echo user input
            if (serialBytes[i] == 10 or serialBytes[i] == 13) and not self.block_cr:
                outstr = outstr + chr(serialBytes[i])
                # print(hex(serialBytes[i]), end=',')

            if 31 < serialBytes[i] < 128:
                outstr = outstr + chr(serialBytes[i])
                self.block_cr = False
                # print(hex(serialBytes[i]), end=',')
            # special action for backspace
            else:
                if serialBytes[i] == 8:
                    backspc = True
            # print(binascii.hexlify(bytearray(serialBytes[i])))
            # print(hex(serialBytes[i]))
            i += 1

        # print('')

        if backspc:
            # new_content = self.shelltext.toPlainText()
            # prompt = new_content[-5:]
            # prev_cursor = self.shelltext.textCursor()
            # self.shelltext.moveCursor(QTextCursor.End)
            # # Use any backspaces that were left in input to delete text
            # self.shelltext.textCursor().deletePreviousChar()
            # self.shelltext.insertPlainText(new_content[1:])
            # self.shelltext.setTextCursor(prev_cursor)
            return

        self.block_cr = False

        if not self.block_echo:
            self.shelltext.moveCursor(self.cursor.End)
            self.shelltext.insertPlainText(outstr)
            self.shelltext.moveCursor(self.cursor.End)
            self.shelltext.ensureCursorVisible()

        self.block_echo = False

    # redirect serial readyread connect here to ignore incomming serial data
    def serialIgnore(self):
        print('serial ignore')
        # self.serialport.waitForReadyRead(50)

    # Read serialport until ending pattern is found or until timeout
    # If ending is None, any pattern is matched
    def read_until(self, min_num_bytes, ending, timeout=1):
        data = b''
        pattern_fnd = False
        if self.serialport.isOpen():
            start_timeout = time.time()
            while True:
                if time.time() - start_timeout > timeout or pattern_fnd:
                    break
                if self.serialport.waitForReadyRead(10):
                    while self.serialport.bytesAvailable() > 0:
                        data += self.serialport.read(min_num_bytes)
                        if data.endswith(ending) or time.time() - start_timeout > timeout:
                            pattern_fnd = True
                            break
        return data

    # Enter the microPython raw REPL mode to run a script on the target
    def enter_raw_repl(self):
        if not self.serialport.isOpen():
            return b'Failed - serialport not open'
        # ctrl-C twice: interrupt any running program
        self.serialport.write(b'\r\x03')
        time.sleep(0.1)
        self.serialport.write(b'\x03')
        time.sleep(0.1)

        # flush input (without relying on serial.flushInput())
        n = self.serialport.bytesAvailable()
        while n > 0:
            self.serialport.read(n)
            n = self.serialport.bytesAvailable()

        for retry in range(0, 1):
            self.serialport.write(b'\r\x01')    # ctrl-A: enter raw REPL
            time.sleep(0.1)
            data = self.read_until(1, b'raw REPL; CTRL-B to exit\r\n>', 1)
            if data.endswith(b'raw REPL; CTRL-B to exit\r\n>'):
                break
        else:
            data = b'Failed to enter raw REPL'
            return data

        self.serialport.write(b'\x04')  # ctrl-D: soft reset
        data = self.read_until(1, b'soft reboot\r\n')
        if not data.endswith(b'soft reboot\r\n'):
            data = b'Failed to soft reboot'
        else:
            # By splitting this into 2 reads, it allows boot.py to print stuff,
            # which will show up after the soft reboot and before the raw REPL.
            # Modification from original pyboard.py below:
            #   Add a small delay and send Ctrl-C twice after soft reboot to ensure
            #   any main program loop in main.py is interrupted.
            time.sleep(0.1)
            self.serialport.write(b'\x03')
            time.sleep(0.1)           # (slight delay before second interrupt
            self.serialport.write(b'\x03')
            # End modification above.
            data = self.read_until(1, b'raw REPL; CTRL-B to exit\r\n>')
            if not data.endswith(b'raw REPL; CTRL-B to exit\r\n>'):
                data = b'Failed to complete raw REPL'

        return data

    def exit_raw_repl(self):
        if self.serialport.isOpen():
            self.serialport.write(b'\r\x02')    # ctrl-B: enter friendly REPL

    def follow(self, timeout, data_consumer=None):
        # wait for normal output
        data = self.read_until(1, b'\x04', timeout=timeout)
        if not data.endswith(b'\x04'):
            print('Failed: Timeout in first command EOF!')
            data_err = b'Failed: Timeout in first command EOF!\n'
            data = b''
        else:
            data = data[:-1]    # remove trailing '\x04'
            # wait to see if any error output
            data_err = self.read_until(1, b'\x04', 0.1)
            if data_err and data_err.endswith(b'\x04'):
                data_err = data_err[:-1]
        # return normal and error output
        return data, data_err

    def exec_raw_no_follow(self, command):
        if not self.serialport.isOpen():
            return b''
        if isinstance(command, bytes):
            command_bytes = command
        else:
            command_bytes = bytes(command, encoding='utf8')

        # write command script to target
        for i in range(0, len(command_bytes), 256):
            self.serialport.write(command_bytes[i:min(i + 256, len(command_bytes))])
            time.sleep(0.01)
        self.serialport.write(b'\x04')      # Ctrl-D ends the transmit

        # check if command was accepted
        data = self.read_until(1, b'OK')
        if not data.endswith(b'OK'):
            print('could not exec command')

    def exec_raw(self, command, timeout=1, data_consumer=None):
        self.exec_raw_no_follow(command)
        return self.follow(timeout, data_consumer)

    def exec_(self, command, stream_output=False):
        if not self.serialport.isOpen():
            return b'Failed - serialport not open'
        data_consumer = None
        if stream_output:
            data_consumer = self.stdout_write_bytes
        ret, ret_err = self.exec_raw(command, data_consumer=data_consumer)
        if ret_err:
            self.shelltext.insertPlainText(ret_err.decode('utf-8'))
        return ret

    def execfile(self, filename, stream_output=False):
        with open(filename, 'rb') as f:
            pyfile = f.read()
        return self.exec_(pyfile, stream_output=stream_output)

    def eval(self, expression):
        ret = self.exec_('print({})'.format(expression))
        ret = ret.strip()
        return ret

    def get_time(self):
        t = str(self.eval('pyb.RTC().datetime()'), encoding='utf8')[1:-1].split(', ')
        return int(t[4]) * 3600 + int(t[5]) * 60 + int(t[6])

    # serialport callback when serial chars are received
    # def serial_read_bytes(self):
    #     serialBytes = bytes(self.serialport.readAll())
    #     print(serialBytes)
    #     return
    #     outstr = ""
    #     i = 0
    #     # strip binary crap from serial data
    #     bstr = _setx.getFlagStr('BLOCK_CR')
    #     while i < len(serialBytes):
    #         if (serialBytes[i] == 10 or serialBytes[i] == 13) and bstr == 'False':    # LF, CR are OK
    #             outstr = outstr + chr(serialBytes[i])
    #         elif 31 < serialBytes[i] < 128:
    #             outstr = outstr + chr(serialBytes[i])
    #         i += 1
    #
    #     _setx.setFlagStr('BLOCK_CR', 'False')
    #
    #     # put received chars into the shellText widget
    #     if _setx.getFlagStr('BLOCK_ECHO') == 'False':
    #         if _setx.getFlagStr('IGNORE_SERIAL_AFTER_RESET') == 'True':
    #             word_offset = outstr.find('Micro')
    #             if word_offset < 0:
    #                 outstr = ''
    #             else:
    #                 _setx.setFlagStr('IGNORE_SERIAL_AFTER_RESET', 'False')
    #                 outstr = '\n' + outstr[word_offset:]
    #         self.shellText.moveCursor(self.cursor.End)
    #         self.shellText.insertPlainText(outstr)
    #         self.shellText.moveCursor(self.cursor.End)
    #         self.shellText.ensureCursorVisible()
    #     else:
    #         _setx.setFlagStr('BLOCK_ECHO', 'False')


# in Python2 exec is a keyword so one must use "exec_"
# but for Python3 we want to provide the nicer version "exec"
setattr(Pyboard, "exec", Pyboard.exec_)

def execfile(filename, device='/dev/ttyUSB0', baudrate=115200, user='micro', password='python'):
    pyb = Pyboard(device, baudrate, user, password)
    pyb.enter_raw_repl()
    output = pyb.execfile(filename)
    pyb.stdout_write_bytes(output)
    pyb.exit_raw_repl()
    pyb.close()

def main():
    import argparse
    cmd_parser = argparse.ArgumentParser(description='Run scripts on the pyboard.')
    cmd_parser.add_argument('--device', default='/dev/ttyACM0', help='the serial device or the IP address of the pyboard')
    cmd_parser.add_argument('-b', '--baudrate', default=115200, help='the baud rate of the serial device')
    cmd_parser.add_argument('-u', '--user', default='micro', help='the telnet login username')
    cmd_parser.add_argument('-p', '--password', default='python', help='the telnet login password')
    cmd_parser.add_argument('-c', '--command', help='program passed in as string')
    cmd_parser.add_argument('-w', '--wait', default=0, type=int, help='seconds to wait for USB connected board to become available')
    cmd_parser.add_argument('--follow', action='store_true', help='follow the output after running the scripts [default if no scripts given]')
    cmd_parser.add_argument('files', nargs='*', help='input files')
    args = cmd_parser.parse_args()

    def execbuffer(buf):
        #try:
        pyb = Pyboard(args.device, args.baudrate, args.user, args.password, args.wait)
        pyb.enter_raw_repl()
        ret, ret_err = pyb.exec_raw(buf, timeout=None, data_consumer=pyb.stdout_write_bytes)
        pyb.exit_raw_repl()
        pyb.close()
        # except PyboardError as er:
        #     print(er)
        #     sys.exit(1)
        # except KeyboardInterrupt:
        #     sys.exit(1)
        # if ret_err:
        #     stdout_write_bytes(ret_err)
        #     sys.exit(1)

    if args.command is not None:
        execbuffer(args.command.encode('utf-8'))

    for filename in args.files:
        with open(filename, 'rb') as f:
            pyfile = f.read()
            execbuffer(pyfile)

    if args.follow or (args.command is None and len(args.files) == 0):
        #try:
        pyb = Pyboard(args.device, args.baudrate, args.user, args.password, args.wait)
        ret, ret_err = pyb.follow(timeout=None, data_consumer=pyb.stdout_write_bytes)
        pyb.close()
        # except PyboardError as er:
        #     print(er)
        #     sys.exit(1)
        # except KeyboardInterrupt:
        #     sys.exit(1)
        # if ret_err:
        #     stdout_write_bytes(ret_err)
        #     sys.exit(1)

# if __name__ == "__main__":
#     main()
