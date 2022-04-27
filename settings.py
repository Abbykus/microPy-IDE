from PyQt5.QtCore import (QSettings, QFile, QFileInfo, QCoreApplication, Qt)
from PyQt5.QtWidgets import (QWidget, QTabWidget, QVBoxLayout, QHBoxLayout, QPushButton)
import sys
import os

class Settings(QWidget):
    def __init__(self):
        super().__init__()

        self.setDefaults()
        self.createUi()

    # -----------------------------------------------------------
    # DEFAULT Settings
    # -----------------------------------------------------------
    def setDefaults(self):
        self.settings = QSettings("Abbykus", "microPy")
        # set current application path
        self.settings.setValue('APP_PATH', os.getcwd())
        # set OS type (linux, windoze, MacOS, etc.)
        self.settings.setValue('OS_TYPE', sys.platform)     # OS type (Linux, windoze, etc.)
        # set project path default if not already defined
        if len(self.settings.value('CUR_PROJECT_PATH', '')) == 0:
            self.settings.setValue('CUR_PROJECT_PATH', self.settings.value('APP_PATH', '') + '/projects')
        self.settings.setValue('MAX_RECENT_FILES', '15')

    # -----------------------------------------------------------
    # Create the settings dialog window
    # -----------------------------------------------------------
    def createUi(self):
        self.setAccessibleName('setwin')
        self.setWindowTitle('microPy-IDE Settings')
        self.tab_box = QVBoxLayout()
        self.btn_box = QVBoxLayout()
        self.closebtn = QPushButton(' Close ')
        self.closebtn.setObjectName("closebtn")
        self.closebtn.setStyleSheet(
            "QPushButton { background-color: #dedede; color: #0a0a0a; border-style: outset; padding: 2px;"
            "font: 16px; border-width: 2px; border-radius: 6px; border-color: #1a1a1a; }"
            "QPushButton#closebtn:hover { background-color: #646464; color: #dedede; }")
        self.closebtn.clicked.connect(self.setWinClose)
        self.btn_box.addWidget(self.closebtn, 1)
        self.btn_box.setAlignment(Qt.AlignRight)

        # Create group tabs
        self.tabsList = QTabWidget()
        self.tabsList.setTabsClosable(False)
        self.tabsList.setTabVisible(0, True)
        self.tabsList.currentChanged.connect(self.tabChanged)
        self.tabsList.tabBar().setUsesScrollButtons(False)

        # General settings tab
        self.gen_tab = QWidget()
        self.gen_tab.layout = QHBoxLayout()
        # TODO - add settings widgets
        self.gen_tab.setLayout(self.gen_tab.layout)
        self.tabsList.addTab(self.gen_tab, 'General')

        # Editor tab
        self.edit_tab = QWidget()
        self.edit_tab.layout = QHBoxLayout()
        # TODO - add settings widgets
        self.edit_tab.setLayout(self.edit_tab.layout)
        self.tabsList.addTab(self.edit_tab, 'Editor')

        # micropython tab
        self.mpy_tab = QWidget()
        self.mpy_tab.layout = QHBoxLayout()
        # TODO - add settings widgets
        self.mpy_tab.setLayout(self.mpy_tab.layout)
        self.tabsList.addTab(self.mpy_tab, 'MicroPython')

        self.tab_box.addWidget(self.tabsList, 1)
        self.main_layout = QVBoxLayout()
        self.main_layout.addLayout(self.tab_box)
        self.main_layout.addLayout(self.btn_box)
        self.setLayout(self.main_layout)
        self.resize(800, 600)

    # settings window is closing
    def closeEvent(self, event):
        # TODO - save settings to
        print('set win closing')
        return

    def openSettingsWindow(self):
        self.show()

    def tabChanged(self):
        return

    def setWinClose(self):
        self.close()


    def setCurProject(self, full_path):      # name str can be name only or with path included
        self.settings.setValue(('CUR_PROJECT_FULL_PATH', full_path))
        _dir, _filename = os.path.split(full_path)
        self.settings.setValue('CUR_PROJECT_PATH', _dir)
        self.settings.setValue('CUR_PROJECT_NAME', _filename)

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



