from PyQt5.QtCore import (QSettings, QFile, QFileInfo, QCoreApplication)
import sys
import os

class Settings:
    def __init__(self):
        self.settings = QSettings("Abbykus", "microPy")
        # set current application path
        self.settings.setValue('APP_PATH', QFileInfo.path(QFileInfo(QCoreApplication.arguments()[0])))
        # set OS type (linux, windoze, MacOS, etc.)
        self.settings.setValue('OS_TYPE', sys.platform)     # OS type (Linux, windoze, etc.)
        # set project path default if not already defined
        if len(self.settings.value('CUR_PROJECT_PATH', '')) == 0:
            self.settings.setValue('CUR_PROJECT_PATH', self.settings.value('APP_PATH', '') + '/projects')

        self.settings.setValue('MAX_RECENT_FILES', '15')

    def setCurProject(self, full_path):      # name str can be name only or with path included
        self.settings.setValue(('CUR_PROJECT_FULL_PATH', full_path))
        dir, filename = os.path.split(full_path)
        self.settings.setValue('CUR_PROJECT_PATH', dir)
        self.settings.setValue('CUR_PROJECT_NAME', filename)

    def getCurProjectPath(self):
        return self.settings.value('CUR_PROJECT_PATH', '')

    def getCurProjectName(self):
            return self.settings.value('CUR_PROJECT_NAME', '')

    def getFullProjectPath(self):
        return self.settings.value('CUR_PROJECT_FULL_PATH', '')

    # return path to the microPy app (where app was launched from)
    def getAppPath(self):
        return self.settings.value('APP_PATH', '')

    def getOS(self):
        return self.settings.value('OS_TYPE', 'OS Unknown')

    def getSerialPort(self):
        os = self.settings.value('OS_TYPE', '').lower()
        if os == 'linux':
            return self.settings.value('SERIAL_PORT', '/dev/ttyUSB0')
        elif os == 'windows':
            return self.settings.value('SERIAL_PORT', 'COM1')

    def setSerialPort(self, serial_port_name):
        self.settings.setValue('SERIAL_PORT', serial_port_name)

    def getBaudRate(self):
        return self.settings.value('BAUD_RATE', 115200)

    def setBaudRate(self, baud):
        return self.settings.setValue('BAUD_RATE', baud)

    def getCurTargetScript(self):
        return self.settings.value('CUR_TARGET_SCRIPT', '')

    def setCurTargetScript(self, _bool):
        if _bool:
            self.settings.setValue('CUR_TARGET_SCRIPT', 'True')
        else:
            self.settings.setValue('CUR_TARGET_SCRIPT', 'False')

    def getCurProjectScript(self):
        return self.settings.value('CUR_TARGET_SCRIPT', '')

    def setCurProjectScript(self, proj_script):
        self.settings.setValue('CUR_TARGET_SCRIPT', proj_script)

    def getWinPos(self):
        return self.settings.value('WINPOS', '')

    def setWinPos(self, winpos):
        self.settings.setValue('WINPOS', winpos)

    def getWinSize(self):
        return self.settings.value('WINSIZE', '')

    def setWinSize(self, winsize):
        self.settings.setValue('WINSIZE', winsize)

    def getRecentFileList(self):
        return self.settings.value('RECENT_FILES_LIST', '')

    def setRecentFileList(self, recentfiles):
        self.settings.setValue('RECENT_FILES_LIST', recentfiles)

    def getMaxRecentFiles(self):
        val = self.settings.value('MAX_RECENT_FILES', '15')
        return int(val)

    def getFlagStr(self, key):
        return self.settings.value(key, '')

    def setFlagStr(self, key, strval):
        self.settings.setValue(key, strval)



