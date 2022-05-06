# !/usr/bin/python3
# -- coding: utf-8 --
# microPy.py - microPython IDE for microcontrollers.
#
from __future__ import print_function

from PyQt5.QtWidgets import (QPlainTextEdit, QWidget, QVBoxLayout, QApplication, QFileDialog, QMessageBox, QLabel,
                             QCompleter, QHBoxLayout, QTextEdit, QToolBar, QComboBox, QAction, QLineEdit, QDialog,
                             QPushButton, QToolButton, QMenu, QMainWindow, QInputDialog, QColorDialog, QStatusBar,
                             QSystemTrayIcon, QSplitter, QTreeWidget, QTreeWidgetItem, QTabWidget, QDialogButtonBox,
                             QScrollBar, QSpacerItem, QSizePolicy, QLayout, QStyle, QFrame, QHeaderView, QShortcut)
from PyQt5.QtGui import (QIcon, QPainter, QTextFormat, QColor, QTextCursor, QKeySequence, QClipboard, QTextDocument,
                         QPixmap, QStandardItemModel, QStandardItem, QCursor, QPalette, QFont)
from PyQt5.QtCore import (Qt, QVariant, QRect, QDir, QFile, QFileInfo, QTextStream, QSettings, QTranslator, QLocale,
                          QProcess, QPoint, QSize, QCoreApplication, QStringListModel, QLibraryInfo, QIODevice, QEvent,
                          pyqtSlot, QModelIndex, QThread)

from PyQt5.QtPrintSupport import QPrintDialog, QPrinter, QPrintPreviewDialog
from PyQt5.QtSerialPort import QSerialPort, QSerialPortInfo

from sys import argv
import inspect

# from syntax_py import *
import syntax_py
import os
import sys
import re
import time
import codecs
import mpconfig
import ntpath
import settings
import pyboard
import files
import asyncio


'''
COMMON COLOR VALUES 

Python (apparently) has no way of changing stylesheet colors at run time. Python also has no
text substitution feature (like #define in C/C++). So it is necessary to keep track of common
color values here.

POWDER BLUE:    #84aff4     Borders, etc.
DARK GREY:      #2b2b2b
MEDIUM GREY:    #484848
LIGHT GREY:     #a0a0a0
'''

# GLOBAL CONSTANTS
num_bar_bgcolor = QColor("#84aff4")
textline_highlight_color = QColor("#303030")  #QColor("#232323")        # shade of black

tab = chr(9)
tab_indent = 4
eof = "\n"
iconsize = QSize(24, 24)


#####################################################################
# pyTextEditor widget - the python script editor
#####################################################################
class PyTextEdit(QPlainTextEdit):
    def __init__(self, parent=None):
        super(PyTextEdit, self).__init__(parent)

        self.textHasChanged = False
        self.installEventFilter(self)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self._completer = None
        self.completer = QCompleter(self)
        root = QFileInfo.path(QFileInfo(QCoreApplication.arguments()[0]))
        self.completer.setModel(self.modelFromFile(root + '/resources/keywords.txt'))
        self.completer.setModelSorting(QCompleter.CaseInsensitivelySortedModel)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setWrapAround(False)
        self.completer.setCompletionRole(Qt.EditRole)
        self.completer.setMaxVisibleItems(10)
        self.setCompleter(self.completer)

        self.ctrl_f = QShortcut(QKeySequence('Ctrl+F'), self)

    def setCompleter(self, c):
        if self._completer is not None:
            self._completer.activated.disconnect()

        self._completer = c
        #        c.popup().verticalScrollBar().hide()
        c.popup().setStyleSheet(
            "background-color: #555753; color: #eeeeec; font-size: 8pt; selection-background-color: #4e9a06;")

        c.setWidget(self)
        c.setCompletionMode(QCompleter.PopupCompletion)
        c.activated.connect(self.insertCompletion)

    def completer(self):
        return self._completer

    def insertCompletion(self, completion):
        if self._completer.widget() is not self:
            return

        tc = self.textCursor()
        extra = len(completion) - len(self._completer.completionPrefix())
        tc.movePosition(QTextCursor.Left)
        tc.movePosition(QTextCursor.EndOfWord)
        tc.insertText(completion[-extra:])
        self.setTextCursor(tc)

    def textUnderCursor(self):
        tc = self.textCursor()
        tc.select(QTextCursor.WordUnderCursor)

        return tc.selectedText()

    def focusInEvent(self, e):
        if self._completer is not None:
            self._completer.setWidget(self)

        super(PyTextEdit, self).focusInEvent(e)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Tab:
            self.textCursor().insertText("    ")
            return
        if self._completer is not None and self._completer.popup().isVisible():
            # The following keys are forwarded by the completer to the widget.
            if e.key() in (Qt.Key_Enter, Qt.Key_Return):
                e.ignore()
                # Let the completer do default behavior.
                return

        isShortcut = ((e.modifiers() & Qt.ControlModifier) != 0 and e.key() == Qt.Key_Escape)
        if self._completer is None or not isShortcut:
            # Do not process the shortcut when we have a completer.
            super(PyTextEdit, self).keyPressEvent(e)

        ctrlOrShift = e.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier)
        if self._completer is None or (ctrlOrShift and len(e.text()) == 0):
            return

        eow = "~!@#$%^&*()_+{}|:\"<>?,./;'[]\\-="
        hasModifier = (e.modifiers() != Qt.NoModifier) and not ctrlOrShift
        completionPrefix = self.textUnderCursor()

        if not isShortcut and (hasModifier or len(e.text()) == 0 or len(completionPrefix) < 2 or e.text()[-1] in eow):
            self._completer.popup().hide()
            return

        if completionPrefix != self._completer.completionPrefix():
            self._completer.setCompletionPrefix(completionPrefix)
            self._completer.popup().setCurrentIndex(
                self._completer.completionModel().index(0, 0))

        cr = self.cursorRect()
        cr.setWidth(self._completer.popup().sizeHintForColumn(
            0) + self._completer.popup().verticalScrollBar().sizeHint().width())
        self._completer.complete(cr)

    def modelFromFile(self, fileName):
        f = QFile(fileName)
        if not f.open(QFile.ReadOnly):
            return QStringListModel(self.completer)

        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))

        self.words = []
        while not f.atEnd():
            line = f.readLine().trimmed()
            if line.length() != 0:
                try:
                    line = str(line, encoding='ascii')
                except TypeError:
                    line = str(line)

                self.words.append(line)

        QApplication.restoreOverrideCursor()
        return QStringListModel(self.words, self.completer)

#####################################################################
# NumberBar widget - displays script line numbers in a column left of
# the pyTextEditor window.
#####################################################################
class NumberBar(QWidget):
    def __init__(self, parent=None):
        super(NumberBar, self).__init__(parent)
        #PyTextEdit = parent

        editor = mpconfig.editorList[mpconfig.currentTabIndex]
        editor.blockCountChanged.connect(self.update_width)
        editor.updateRequest.connect(self.update_on_scroll)
        self.update_width('1')

    def update_on_scroll(self, rect, scroll):
        if self.isVisible():
            if scroll:
                self.scroll(0, scroll)
            else:
                self.update()

    def update_width(self, string):
        width = self.fontMetrics().width(str(string)) + 8
        if self.width() != width:
            self.setFixedWidth(width)

    def paintEvent(self, event):
        if self.isVisible():
            editor = mpconfig.editorList[mpconfig.currentTabIndex]
            num_bar = mpconfig.numberbarList[mpconfig.currentTabIndex]
            block = editor.firstVisibleBlock()
            height = num_bar.fontMetrics().height()
            number = block.blockNumber()
            painter = QPainter(num_bar)
            painter.fillRect(event.rect(), num_bar_bgcolor)
            painter.drawRect(0, 0, event.rect().width() - 1, event.rect().height() - 1)
            font = painter.font()
            current_block = editor.textCursor().block().blockNumber() + 1
            while block.isValid():  # and condition:
                block_geometry = editor.blockBoundingGeometry(block)
                offset = editor.contentOffset()
                block_top = block_geometry.translated(offset).top()
                number += 1
                rect = QRect(0, int(block_top) + 2, num_bar.width() - 5, height)
                # highlight current line number
                if number == current_block:
                    painter.setPen(Qt.white)
                else:
                    painter.setPen(Qt.black)

                font.setWeight(QFont.Black)
                painter.drawText(rect, Qt.AlignRight, '%i' % number)

                if block_top > event.rect().bottom():
                    break
                block = block.next()
            painter.end()


#####################################################################
class fileViewer(QTreeWidget):
    def __init__(self, parent=None):
        super(fileViewer, self).__init__(parent)


#####################################################################
class pyEditor(QMainWindow):
    def __init__(self, parent=None):
        super(pyEditor, self).__init__(parent)

        class Vseparator(QFrame):
            # a simple separator, like the one you get from designer
            def __init__(self):
                super(Vseparator, self).__init__()
                self.setFrameShape(self.VLine | self.Box)  #self.Sunken)

        self.extProc = QProcess()       # used to start external programs (processes)

        # Create the target REPL shell
        self.shellText = QTextEdit()
        self.shellText.setObjectName("shellText")
        self.shellText.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.shellText.setReadOnly(False)
        self.shellText.installEventFilter(self)
        self.shellText.setMinimumHeight(28)
        self.shellText.setStyleSheet(stylesheet2(self))
        self.shellText.setContextMenuPolicy(Qt.PreventContextMenu)
        # self.shellText.customContextMenuRequested.connect(self.targetViewerContextMenu)

        # Instantiate settings class
        self.setx = settings.Settings()
        _device = self.setx.getSerialPort()
        _baud = self.setx.getBaudRate()
        self.mpBoard = pyboard.Pyboard(self.shellText, _device, _baud)
        self.mpCmds = files.Files(self.mpBoard)

        self.TargetFileList = []

        # create tabbed editor list
        self.tabsList = QTabWidget()
        self.tabsList.setTabsClosable(True)
        self.tabsList.setTabVisible(0, True)
        self.tabsList.currentChanged.connect(self.change_editor_tab)
        self.tabsList.tabCloseRequested.connect(self.remove_tab)

        self.cursor = QTextCursor()

        # statusbar
        self.statusBar().setStyleSheet(stylesheet2(self))
        self.statusBar().showMessage(self.setx.getAppPath())
        self.lineLabel = QLabel(" Ln:1 | Col:0")
        self.statusBar().addPermanentWidget(self.lineLabel)
        self.recentFileActs = []

        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowIcon(QIcon.fromTheme("applications-python"))

        # Create the project files viewer derived from QTreeWidget
        self.projectFileViewer = fileViewer()
        self.projectFileViewer.setStyleSheet(stylesheet2(self))
        proj_name = self.setx.getCurProjectName()
        proj_path = self.setx.getProjectPath() + '/' + self.setx.getCurProjectName()
        if self.isProjectValid(proj_name) and os.path.isdir(proj_path):
            proj_name = 'Project: ' + proj_name
        else:
            proj_name = 'Project: None'

        self.projectFileViewer.setColumnCount(2)
        self.projectFileViewer.setHeaderItem(QTreeWidgetItem([proj_name, 'Size']))
        self.projectFileViewer.setColumnWidth(0, 180)
        self.projectFileViewer.itemDoubleClicked.connect(self.projectFileViewerDblClicked)
        self.projectFileViewer.setContextMenuPolicy(Qt.CustomContextMenu)
        self.projectFileViewer.customContextMenuRequested.connect(self.projectViewerContextMenu)
        self.projectFileViewer.setUniformRowHeights(False)

        # Populate the Project file viewer
        self.viewProjectFiles(proj_path)
        self.projectFileViewer.expandAll()

        # Create the Target file viewer
        self.targetFileViewer = fileViewer()
        self.targetFileViewer.setStyleSheet(stylesheet2(self))
        self.targetFileViewer.setHeaderItem(QTreeWidgetItem(["Target Files", "Size"]))
        self.targetFileViewer.setColumnCount(2)

        targ1 = QTreeWidgetItem([self.setx.getSerialPort()])
        self.targetFileViewer.addTopLevelItem(targ1)
        self.targetFileViewer.expandAll()
        self.targetFileViewer.itemDoubleClicked.connect(self.targetFileViewerDblClicked)
        self.targetFileViewer.setContextMenuPolicy(Qt.PreventContextMenu)   #Qt.CustomContextMenu)
        # self.targetFileViewer.customContextMenuRequested.connect(self.targetViewerContextMenu)

        ### begin toolbar
        tb = self.addToolBar("File")
        tb.setStyleSheet(stylesheet2(self))
        tb.setContextMenuPolicy(Qt.PreventContextMenu)
        tb.setIconSize(QSize(iconsize))
        tb.setMovable(False)
        tb.setAllowedAreas(Qt.AllToolBarAreas)
        tb.setFloatable(False)

        # Create action button objects used by menus and toolbars
        self.newProjectAct = QAction("&Create New Project", self, shortcut=QKeySequence.New, triggered=self.createNewProject)
        self.newProjectAct.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/new_project"))

        self.openProjectAct = QAction("&Open Existing Project", self, shortcut=QKeySequence.New, triggered=self.openExistingProject)
        self.openProjectAct.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/open_project"))

        self.closeProjectAct = QAction("&Close Current Project", self, shortcut=QKeySequence.New, triggered=self.closeCurrentProject)
        self.closeProjectAct.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/close_project"))

        self.newFileAct = QAction("&New File", self, shortcut=QKeySequence.New, triggered=self.newFile)
        self.newFileAct.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/newfile"))

        self.openFileAct = QAction("&Open File", self, shortcut=QKeySequence.Open,  triggered=self.openFile)
        self.openFileAct.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/openfile"))

        self.saveFileAct = QAction("&Save File", self, shortcut=QKeySequence.Save, triggered=self.fileSave)
        self.saveFileAct.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/savefile"))

        self.saveFileAsAct = QAction("&Save File as...", self, shortcut=QKeySequence.SaveAs, triggered=self.fileSaveAs)
        self.saveFileAsAct.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/savefileas"))

        self.renameFileAct = QAction("&Rename File", self, shortcut=QKeySequence.SaveAs, triggered=self.renameFile)
        self.renameFileAct.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/rename"))

        self.deleteFileAct = QAction("&Delete File", self, shortcut="Ctrl+Shift+D", triggered=self.deleteFile)
        self.deleteFileAct.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/delete"))

        self.jumpToAct = QAction("Go to Definition (F12)", self, shortcut="F12", triggered=self.gotoBookmarkFromMenu)
        self.jumpToAct.setIcon(QIcon.fromTheme("go-next"))

        self.commentAct = QAction("#Comment Line (F2)", self, shortcut="F2", triggered=self.commentLine)
        self.commentAct.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/comment"))

        self.uncommentAct = QAction("Uncomment Line (F3)", self, shortcut="F3", triggered=self.uncommentLine)
        self.uncommentAct.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/uncomment"))

        self.commentBlockAct = QAction("Comment Block (F6)", self, shortcut="F6", triggered=self.commentBlock)
        self.commentBlockAct.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/commentBlock"))

        self.uncommentBlockAct = QAction("Uncomment Block (F7)", self, shortcut="F7", triggered=self.uncommentBlock)
        self.uncommentBlockAct.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/uncommentBlock"))

        self.printPreviewAct = QAction("Print Preview (Ctl+Shft+P)", self, shortcut="Ctrl+Shift+P", triggered=self.handlePrintPreview)
        self.printPreviewAct.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/print_preview"))

        self.printAct = QAction("Print", self, shortcut=QKeySequence.Print, triggered=self.handlePrint)
        self.printAct.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/printer"))

        self.exitAct = QAction("Exit", self, shortcut=QKeySequence.Quit, triggered=self.handleQuit)
        self.exitAct.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/quit"))

        self.indentAct = QAction(QIcon.fromTheme(self.setx.getAppPath() + "/icons/indent"), "Indent more", self,
                                 triggered=self.indentLine, shortcut="F8")

        self.indentLessAct = QAction(QIcon.fromTheme(self.setx.getAppPath() + "/icons/unindent"), "Indent less", self,
                                     triggered=self.unindentLine, shortcut="F9")

        self.bookAct = QAction("Add Bookmark", self, triggered=self.addBookmark)
        self.bookAct.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/bookmark"))

        self.bookrefresh = QAction("Clear Bookmarks", self, triggered=self.clearBookmarks)
        self.bookrefresh.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/clear_bookmarks"))

        self.clearRecentAct = QAction("clear Recent Files List", self, triggered=self.clearRecentFiles)
        self.clearRecentAct.setIcon(QIcon.fromTheme("edit-clear"))

        self.zealAct = QAction("&Zeal Developer Help", self, shortcut='ctrl+h', triggered=self.showZeal)
        self.zealAct.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/zeal"))

        self.resetTargetAct = QAction("&Reset Target", self, shortcut='', triggered=self.resetTargetDevice)
        self.resetTargetAct.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/restart"))

        self.runScriptAct = QAction("&Run Script on Target", self, shortcut='', triggered=self.runTargetScript)
        self.runScriptAct.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/run"))

        self.stopScriptAct = QAction("&Stop Target Script", self, shortcut='', triggered=self.stopTargetScript)
        self.stopScriptAct.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/stop"))

        self.downloadScriptAct = QAction("&Download File to Target", self, shortcut='', triggered=self.downloadScript)
        self.downloadScriptAct.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/download"))

        self.uploadScriptAct = QAction("&Upload File from Target", self, shortcut='', triggered=self.uploadScript)
        self.uploadScriptAct.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/upload"))

        self.removeScriptAct = QAction("&Remove File from Target", self, shortcut='', triggered=self.removeScript)
        self.removeScriptAct.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/delete"))

        self.newFolderAct = QAction("&New Target Folder", self, shortcut='', triggered=self.newTargetFolder)
        self.newFolderAct.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/folder_add"))

        self.delFolderAct = QAction("&Remove Target Folder", self, shortcut='', triggered=self.rmTargetFolder)
        self.delFolderAct.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/folder_del"))

        self.eraseTargetAct = QAction("&Erase Target Memory", self, shortcut='', triggered=self.eraseTargetFlash)
        self.eraseTargetAct.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/burn"))

        self.programTargetAct = QAction("&Flash Target Firmware", self, shortcut='', triggered=self.flashTargetFirmware)
        self.programTargetAct.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/python"))

        # project & files toolbar buttons
        tb.addAction(self.newProjectAct)
        tb.addAction(self.openProjectAct)
        tb.addAction(self.closeProjectAct)
        tb.addSeparator()
        tb.addSeparator()
        tb.addWidget(Vseparator())      # visual vertical line seperator
        tb.addSeparator()
        tb.addSeparator()
        tb.addAction(self.newFileAct)
        tb.addAction(self.openFileAct)
        tb.addAction(self.saveFileAct)
        tb.addAction(self.saveFileAsAct)
        tb.addAction(self.renameFileAct)
        tb.addAction(self.deleteFileAct)
        tb.addSeparator()
        tb.addSeparator()
        tb.addWidget(Vseparator())
        tb.addSeparator()
        tb.addSeparator()

        ### comment buttons
        tb.addAction(self.commentAct)
        tb.addAction(self.uncommentAct)
        tb.addAction(self.commentBlockAct)
        tb.addAction(self.uncommentBlockAct)

        ### color chooser
        tb.addSeparator()
        tb.addSeparator()
        tb.addWidget(Vseparator())
        tb.addSeparator()
        tb.addSeparator()
        tb.addAction(QIcon.fromTheme(self.setx.getAppPath() + "/icons/color1"), "insert QColor", self.insertColor)
        tb.addSeparator()
        tb.addAction(QIcon.fromTheme("preferences-color"), "Insert Color Hex Value", self.changeColor)

        ### Insert templates
        tb.addSeparator()
        tb.addSeparator()
        tb.addWidget(Vseparator())
        tb.addSeparator()
        tb.addSeparator()
        self.templates = QComboBox()
        self.templates.setStyleSheet(stylesheet2(self))
        self.templates.setFixedWidth(120)
        self.templates.setToolTip("insert template")
        self.templates.activated[str].connect(self.insertTemplate)
        tb.addWidget(self.templates)

        tb.addSeparator()
        tb.addSeparator()
        tb.addWidget(Vseparator())
        tb.addSeparator()
        tb.addSeparator()

        ### print preview & print buttons
        tb.addAction(self.printPreviewAct)
        tb.addSeparator()
        tb.addAction(self.printAct)

        ### Help (Zeal) button
        tb.addSeparator()
        tb.addSeparator()
        tb.addWidget(Vseparator())
        tb.addSeparator()
        tb.addSeparator()
        tb.addAction(QIcon.fromTheme(self.setx.getAppPath() + "/icons/zeal"), "&Zeal Developer Help", self.showZeal)
        tb.addSeparator()
        tb.addSeparator()
        tb.addWidget(Vseparator())
        tb.addSeparator()
        tb.addSeparator()

        ### about buttons
        tb.addAction(QIcon.fromTheme(self.setx.getAppPath() + "/icons/about"), "&About microPy", self.about)
        tb.addSeparator()
        tb.addSeparator()
        tb.addWidget(Vseparator())
        tb.addSeparator()
        tb.addSeparator()

        ### exit button
        tb.addAction(self.exitAct)

        ### find / replace toolbar
        self.addToolBarBreak()
        tbf = self.addToolBar("Find")
        tbf.setStyleSheet(stylesheet2(self))
        tbf.setContextMenuPolicy(Qt.PreventContextMenu)
        tbf.setIconSize(QSize(iconsize))
        tbf.setMovable(False)
        tbf.setFloatable(False)

        tbf.addSeparator()
        self.findPrevAct = QPushButton("Prev")
        self.findPrevAct.setToolTip('Find Previous Text')
        self.findPrevAct.setFixedWidth(50)
        self.findPrevAct.setStyleSheet(stylesheet2(self))
        self.findPrevAct.setIconSize(QSize(24, 24))
        self.findPrevAct.setLayoutDirection(Qt.RightToLeft)
        self.findPrevAct.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/previous"))
        self.findPrevAct.clicked.connect(self.findTextPrev)
        tbf.addWidget(self.findPrevAct)

        self.findfield = QLineEdit()
        self.findfield.setStyleSheet(stylesheet2(self))
        self.findfield.addAction(QIcon.fromTheme("edit-find"), QLineEdit.LeadingPosition)
        self.findfield.setClearButtonEnabled(False)
        self.findfield.setFixedWidth(150)
        self.findfield.setPlaceholderText("find")
        self.findfield.setToolTip("press RETURN to find")
        self.findfield.setText("")
        # ft = self.findfield.text()
        self.findfield.textChanged.connect(self.findTextChanged)
        self.findfield.returnPressed.connect(self.findText)
        tbf.addWidget(self.findfield)

        self.findNextAct = QPushButton("Next")
        self.findNextAct.setToolTip('Find Next Text')
        self.findNextAct.setFixedWidth(50)
        self.findNextAct.setStyleSheet(stylesheet2(self))
        self.findNextAct.setIconSize(QSize(24, 24))
        self.findNextAct.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/next"))
        self.findNextAct.clicked.connect(self.findTextNext)
        tbf.addWidget(self.findNextAct)
        tbf.addSeparator()

        self.replacefield = QLineEdit()
        self.replacefield.setStyleSheet(stylesheet2(self))
        self.replacefield.addAction(QIcon.fromTheme("edit-find-and-replace"), QLineEdit.LeadingPosition)
        self.replacefield.setClearButtonEnabled(False)
        self.replacefield.setFixedWidth(150)
        self.replacefield.setPlaceholderText("replace with")
        self.replacefield.setToolTip("Press RETURN to replace current match")
        self.replacefield.returnPressed.connect(self.replaceOne)
        tbf.addSeparator()
        tbf.addWidget(self.replacefield)
        tbf.addSeparator()

        self.repAllAct = QPushButton("Replace ALL")
        self.repAllAct.setToolTip('Replace All Occurances')
        self.repAllAct.setFixedWidth(80)
        self.repAllAct.setStyleSheet(stylesheet2(self))
        self.repAllAct.clicked.connect(self.replaceAll)
        tbf.addWidget(self.repAllAct)
        tbf.addSeparator()
        tbf.addSeparator()
        tbf.addWidget(Vseparator())
        tbf.addSeparator()
        tbf.addSeparator()
        tbf.addAction(self.indentAct)
        tbf.addAction(self.indentLessAct)
        tbf.addSeparator()
        tbf.addSeparator()
        tbf.addWidget(Vseparator())
        tbf.addSeparator()
        tbf.addSeparator()
        self.gotofield = QLineEdit()
        self.gotofield.setStyleSheet(stylesheet2(self))
        # self.gotofield.addAction(QIcon.fromTheme("next"), QLineEdit.LeadingPosition)
        self.gotofield.setClearButtonEnabled(True)
        self.gotofield.setFixedWidth(70)
        self.gotofield.setPlaceholderText("go to line")
        self.gotofield.setToolTip("press RETURN to go to line")
        self.gotofield.returnPressed.connect(self.gotoLine)
        tbf.addWidget(self.gotofield)

        tbf.addSeparator()
        self.bookmarks = QComboBox()
        self.bookmarks.setStyleSheet(stylesheet2(self))
        self.bookmarks.setFixedWidth(200)
        self.bookmarks.setToolTip("Goto Bookmark")
        self.bookmarks.activated[str].connect(self.gotoBookmark)
        tbf.addWidget(self.bookmarks)
        tbf.addAction(self.bookAct)
        tbf.addSeparator()
        tbf.addAction(self.bookrefresh)

        tbf.addSeparator()
        tbf.addSeparator()
        tbf.addWidget(Vseparator())
        tbf.addSeparator()
        tbf.addSeparator()
        tbf.addAction(QAction(QIcon.fromTheme("document-properties"), "Check && Reindent Text", self,
                              triggered=self.reindentText))

        # 'File' dropdown menu
        menu_bar = self.menuBar()
        menu_bar.setStyleSheet(stylesheet2(self))
        self.filemenu = menu_bar.addMenu("File")
        self.filemenu.setStyleSheet(stylesheet2(self))
        self.separatorAct = self.filemenu.addSeparator()
        self.filemenu.addSeparator()
        self.filemenu.addAction(self.newProjectAct)
        self.filemenu.addAction(self.openProjectAct)
        self.filemenu.addAction(self.closeProjectAct)
        self.filemenu.addSeparator()
        self.filemenu.addSeparator()


        #self.filemenu.insertSeparator(self.separatorAct)
        self.filemenu.addAction(self.newFileAct)
        self.filemenu.addAction(self.openFileAct)
        self.filemenu.addAction(self.saveFileAct)
        self.filemenu.addAction(self.saveFileAsAct)
        self.filemenu.addAction(self.renameFileAct)
        self.filemenu.addAction(self.deleteFileAct)
        self.filemenu.addSeparator()
        # for i in range(self.rt_settings['max_recent_files']):
        #    self.filemenu.addAction(self.recentFileActs[i])
        self.updateRecentFileActions()
        self.filemenu.addSeparator()
        self.filemenu.addAction(self.clearRecentAct)
        self.filemenu.addAction(self.exitAct)

        ### Top level menu bar 'Edit'
        editmenu = menu_bar.addMenu("Edit")
        editmenu.setStyleSheet(stylesheet2(self))
        editmenu.addAction(
            QAction(QIcon.fromTheme('edit-undo'), "Undo", self, triggered=self.textUndo, shortcut="Ctrl+z"))
        editmenu.addAction(
            QAction(QIcon.fromTheme('edit-redo'), "Redo", self, triggered=self.textRedo, shortcut="Shift+Ctrl+u"))
        editmenu.addSeparator()
        editmenu.addAction(
            QAction(QIcon.fromTheme('edit-copy'), "Copy", self, triggered=self.textCopy, shortcut="Ctrl+c"))
        editmenu.addAction(
            QAction(QIcon.fromTheme('edit-cut'), "Cut", self, triggered=self.textCut, shortcut="Ctrl+x"))
        editmenu.addAction(
            QAction(QIcon.fromTheme('edit-paste'), "Paste", self, triggered=self.textPaste, shortcut="Ctrl+v"))
        editmenu.addAction(
            QAction(QIcon.fromTheme('edit-delete'), "Delete", self, triggered=self.textCut, shortcut="Del"))
        editmenu.addSeparator()
        editmenu.addAction(
            QAction(QIcon.fromTheme('edit-select-all'), "Select All", self, triggered=self.textSelectAll,
                    shortcut="Ctrl+a"))
        editmenu.addSeparator()
        editmenu.addAction(self.commentAct)
        editmenu.addAction(self.uncommentAct)
        editmenu.addSeparator()
        editmenu.addAction(self.commentBlockAct)
        editmenu.addAction(self.uncommentBlockAct)
        editmenu.addSeparator()
        editmenu.addSeparator()
        editmenu.addAction(self.jumpToAct)
        editmenu.addSeparator()
        editmenu.addAction(self.indentAct)
        editmenu.addAction(self.indentLessAct)

        self.settings_menu = menu_bar.addMenu("Settings")
        self.settings_menu.setStyleSheet(stylesheet2(self))
        self.settings_menu.addAction(QIcon.fromTheme(self.setx.getAppPath() + "/icons/settings"), "&Settings Menu", self.settingsmenu)
        self.settings_menu.addSeparator()

        ### Top level menu bar 'Help'
        self.helpmenu = menu_bar.addMenu("Help")
        self.helpmenu.setStyleSheet(stylesheet2(self))
        self.separatorAct = self.helpmenu.addSeparator()

        ### About button
        self.helpmenu.addAction(QIcon.fromTheme(self.setx.getAppPath() + "/icons/about"), "&About microPy", self.about)
        self.helpmenu.addSeparator()

        ### Zeal button
        self.helpmenu.addAction(self.zealAct)
        self.helpmenu.addSeparator()

        ### Micropython toolbar
        mptb = self.addToolBar("Run")
        mptb.setStyleSheet(stylesheet2(self))
        mptb.setContextMenuPolicy(Qt.PreventContextMenu)
        mptb.setIconSize(QSize(iconsize))
        mptb.setMovable(False)
        mptb.setAllowedAreas(Qt.AllToolBarAreas)
        mptb.setFloatable(False)

        ### Serial Port line editor widget
        self.comportfield = QComboBox()
        self.comportfield.setStyleSheet(stylesheet2(self))
        self.comportfield.setFixedWidth(150)

        available_ports = QSerialPortInfo.availablePorts()
        com_list = []
        for port in available_ports:
            port_name = port.portName()
            if sys.platform.lower() == 'linux':
                port_name = '/dev/' + port_name
            com_list.append(port_name)

        if not com_list:
            self.comportfield.setPlaceholderText("No serial ports found!")
        else:
            self.comportfield.addItems(com_list)

        self.comportfield.setToolTip("Serial Port Name")
        self.comportfield.activated[str].connect(self.saveComPort)
        mptb.addWidget(self.comportfield)
        mptb.addSeparator()

        ### Baudrate dropdown editbox
        self.baudrates = QComboBox()
        self.baudrates.setStyleSheet(stylesheet2(self))
        self.baudrates.setFixedWidth(90)
        self.baudrates.setToolTip("Serial Baudrate")
        self.baudrates.activated[str].connect(self.setBaudrate)
        baud_list = ["9600", "19200", "38400", "57600", "115200", "250000"]
        self.baudrates.addItems(baud_list)
        mptb.addWidget(self.baudrates)

        mptb.addSeparator()
        mptb.addSeparator()
        mptb.addWidget(Vseparator())

        ### RESET Target Button
        mptb.addSeparator()
        mptb.addAction(self.resetTargetAct)

        ### Run Script Button
        mptb.addSeparator()
        mptb.addAction(self.runScriptAct)
        
        ### Stop Script Button
        mptb.addSeparator()
        mptb.addAction(self.stopScriptAct)

        ### Download File to Target Button
        mptb.addSeparator()
        mptb.addAction(self.downloadScriptAct)

        ### Upload File from Target Button
        mptb.addSeparator()
        mptb.addAction(self.uploadScriptAct)

        ### Remove Target File Button
        mptb.addSeparator()
        mptb.addAction(self.removeScriptAct)

        ### New Target Folder Button
        mptb.addSeparator()
        mptb.addAction(self.newFolderAct)

        ### Delete Target Folder Button
        mptb.addSeparator()
        mptb.addAction(self.delFolderAct)

        ### Clear shell terminal output
        mptb.addSeparator()
        mptb.addSeparator()
        mptb.addWidget(Vseparator())
        mptb.addSeparator()
        mptb.addSeparator()
        mptb.addAction(QIcon.fromTheme(self.setx.getAppPath() + "/icons/terminal"), "Clear Shell Terminal", self.clearShellTerminal)

        ### Erase & program firmware buttons
        mptb.addSeparator()
        mptb.addSeparator()
        mptb.addWidget(Vseparator())
        mptb.addSeparator()
        mptb.addSeparator()
        mptb.addAction(self.eraseTargetAct)
        mptb.addSeparator()
        mptb.addAction(self.programTargetAct)

        #*** Layout widgets on the main page ***#
        #*** LEFT Horiz Layout - Fileviewer's
        self.lvSplitter = QSplitter(Qt.Vertical)
        self.lvSplitter.addWidget(self.projectFileViewer)
        self.lvSplitter.addWidget(self.targetFileViewer)
        self.lvSplitter.setStretchFactor(0, 2)
        self.lvSplitter.setStretchFactor(1, 1)
        self.lvSplitter.setHandleWidth(10);
        self.left_layout = QHBoxLayout()
        self.left_layout.setContentsMargins(0, 8, 2, 8)
        self.left_layout.addWidget(self.lvSplitter)
        self.left_widget = QWidget()
        self.left_widget.setLayout(self.left_layout)

        #*** TOP RIGHT Horiz Layout
        self.top_right_layout = QHBoxLayout()
        self.top_right_layout.setSpacing(2)
        self.create_new_tab('untitled')         # make first empty tab
        self.top_right_layout.addWidget(self.tabsList, 1)
        self.top_right_layout.setContentsMargins(0, 0, 0, 0)
        self.top_right_widget = QWidget()
        self.setCentralWidget(self.tabsList)
        self.top_right_widget.setLayout(self.top_right_layout)
        self.top_right_widget.setStyleSheet("background-color: #2b2b2b;\n"
                                            "color: #a0a0a0;\n"
                                            "border-style: solid;\n"
                                            "border-color: #84aff4;\n" 
                                            "border-width: 0px;\n"
                                            "border-radius: 4px;")

        #*** BOT RIGHT Horiz Layout
        self.bot_right_layout = QHBoxLayout()
        self.bot_right_layout.setContentsMargins(2, 2, 4, 2)
        self.bot_right_layout.addWidget(self.shellText)
        self.bot_right_widget = QWidget()
        self.bot_right_widget.setLayout(self.bot_right_layout)
        self.bot_right_widget.setStyleSheet("background-color: #2b2b2b;\n"
                                            "color: #a0a0a0;\n"  
                                            "border-style: solid;\n"
                                            "border-color: #84aff4;\n"  
                                            "border-width: 2px;\n"
                                            "border-radius: 4px;")

        #*** VERTICAL Splitter
        self.vSplitter = QSplitter(Qt.Vertical)
        self.vSplitter.addWidget(self.top_right_widget)
        self.vSplitter.addWidget(self.bot_right_widget)
        self.vSplitter.setStretchFactor(0, 3)
        self.vSplitter.setStretchFactor(1, 1)
        self.vSplitter.setHandleWidth(10);

        #*** RIGHT Horiz Layout
        self.right_layout = QHBoxLayout()
        self.right_layout.setSpacing(0)
        self.right_layout.addWidget(self.vSplitter)
        self.right_widget = QWidget()
        self.right_widget.setLayout(self.right_layout)

        #*** HORIZONTAL Splitter
        self.hSplitter = QSplitter(Qt.Horizontal)
        self.hSplitter.addWidget(self.left_widget)
        self.hSplitter.addWidget(self.right_widget)
        self.hSplitter.setStretchFactor(0, 10)
        self.hSplitter.setStretchFactor(1, 35)
        self.hSplitter.setHandleWidth(5);

        #*** Combine All Widgets into a Vertical BoxLayout
        self.all_layout = QVBoxLayout()
        self.all_layout.setSpacing(0)
        self.all_layout.addWidget(self.hSplitter)
        self.all_layout.addWidget(mptb)

        #*** main window
        mq = QWidget(self)
        mq.setLayout(self.all_layout)
        self.setCentralWidget(mq)
        mpconfig.editorList[mpconfig.currentTabIndex].setFocus()

        #*** Brackets ExtraSelection ...
        self.left_selected_bracket = QTextEdit.ExtraSelection()
        self.right_selected_bracket = QTextEdit.ExtraSelection()

        self.loadTemplates()
        self.readSettings()
        self.statusBar().showMessage("Application Path: " + self.setx.getAppPath(), 0)

        baud = self.setx.getBaudRate()
        if baud:
            indx = self.baudrates.findText(baud)
            self.baudrates.setCurrentIndex(indx)
            self.mpBoard.setSerialPortBaudrate(baud)

        comport = self.setx.getSerialPort()
        if comport:
            indx = self.comportfield.findText(comport)
            if indx == -1:
                self.comportfield.addItem(comport)
                indx = self.comportfield.count() -1
            self.comportfield.setCurrentIndex(indx)
            self.mpBoard.setSerialPortName(comport)

    def textSelectAll(self):
        mpconfig.editorList[mpconfig.currentTabIndex].selectAll()

    def textUndo(self):
        mpconfig.editorList[mpconfig.currentTabIndex].undo()

    def textRedo(self):
        mpconfig.editorList[mpconfig.currentTabIndex].redo()

    def textCopy(self):
        mpconfig.editorList[mpconfig.currentTabIndex].copy()

    def textCut(self):
        mpconfig.editorList[mpconfig.currentTabIndex].cut()

    def textPaste(self):
        mpconfig.editorList[mpconfig.currentTabIndex].paste()

    def isProjectValid(self, proj_name):
        if len(proj_name) == 0:
            return False
        path = self.setx.getProjectPath()
        return os.path.isdir(path)

    # View folders & files in the 'path' directory to the projectFileViewer tree widget
    def viewProjectFiles(self, curpath=''):
        if not curpath:
            curpath = self.setx.getProjectPath() + '/' + self.setx.getCurProjectName()
        self.projectFileViewer.clear()
        if len(self.setx.getCurProjectName()) == 0 or not os.path.isdir(curpath):     # exit if no current project
            return

        self.proj_itm = QTreeWidgetItem(self.projectFileViewer, [self.setx.getCurProjectName()])
        ffont = self.proj_itm.font(0)
        ffont.setPointSize(12)
        ffont.setBold(True)
        # ffont.setItalic(True)
        self.proj_itm.setFont(0, ffont)
        self.proj_itm.setIcon(0, QIcon(self.setx.getAppPath() + '/icons/project'))

        self.load_project_tree(curpath, self.projectFileViewer)
        self.projectFileViewer.setItemsExpandable(True)
        self.projectFileViewer.expandAll()

        proj_name = 'Project: ' + self.setx.getCurProjectName()
        self.projectFileViewer.setHeaderItem(QTreeWidgetItem(['Project Files', 'Size']))
        self.projectFileViewer.setColumnWidth(0, 170)     # set col 0 size so file names aren't truncated

    # recursive function to display directory contents in projectFileViewer
    def load_project_tree(self, startpath, tree):
        for element in os.listdir(startpath):
            path_info = os.path.join(startpath, element)
            file_stats = os.stat(path_info)
            if not element.lower() == self.setx.getCurProjectName().lower() and os.path.isfile(path_info):
                child_itm = QTreeWidgetItem([os.path.basename(element), str(file_stats.st_size)])
                child_itm.setData(0, Qt.UserRole, path_info)
                child_itm.setIcon(0, QIcon(self.setx.getAppPath() + '/icons/file'))
                self.proj_itm.addChild(child_itm)
                
    # return a list of open files that have been modified
    def getChangedFiles(self):
        mod_files = []
        for i in range(self.tabsList.count()):
            tabtxt = self.tabsList.tabText(i)
            if tabtxt.endswith('*'):
                mod_files.append(i)
        return mod_files

    def createNewProject(self):
        mod_files = self.getChangedFiles()
        if mod_files:
            QMessageBox.warning(self, 'Create New Project', 'Some current project files have been modified.\n'
                                + 'Save or Discard modified files before continuing.',
                                QMessageBox.Ok, QMessageBox.Ok)
            return
        self.new_proj = ''
        self.np_dialog = QDialog()
        self.np_dialog.setWindowTitle('Enter New Project Name')
        QBtn = QDialogButtonBox.Ok | QDialogButtonBox.Cancel

        buttonBox = QDialogButtonBox(QBtn)
        buttonBox.accepted.connect(self.new_proj_accept)
        buttonBox.rejected.connect(self.new_proj_reject)

        self.np_dialog.layout = QVBoxLayout()
        self.projedit = QLineEdit()
        self.projedit.setPlaceholderText('new project name')
        self.np_dialog.layout.addWidget(self.projedit)
        self.np_dialog.layout.addWidget(buttonBox)
        self.np_dialog.setLayout(self.np_dialog.layout)
        self.np_dialog.setFixedWidth(400)
        self.np_dialog.exec()

        # new project name accepted?
        if self.new_proj == '':   # exit if project rejected
            return
        # check if the project name already exists
        dup_proj_name = False
        proj_path = self.setx.getProjectPath()
        for folder in os.listdir(proj_path):
            if os.path.isdir(proj_path):
                if folder.lower() == self.new_proj.lower():
                    dup_proj_name = True
                    break

        if not dup_proj_name:
            self.setx.setCurProjectName(self.new_proj)
            os.mkdir(self.setx.getProjectPath() + '/' + self.new_proj)
            os.chdir(self.setx.getProjectPath() + '/' + self.new_proj)
            self.statusBar().showMessage("New Project (" + self.new_proj + ") created.")
            self.viewProjectFiles(self.setx.getProjectPath() + '/' + self.new_proj)

    def new_proj_accept(self):
        self.new_proj = self.projedit.text()
        self.np_dialog.close()

    def new_proj_reject(self):
        self.new_proj = ''
        self.np_dialog.close()

    def openExistingProject(self):
        mod_files = self.getChangedFiles()
        if mod_files:
            QMessageBox.warning(self, 'Open Project', 'Some current project files have been modified.\n'
                                + 'Save or Discard modified files before continuing.',
                                QMessageBox.Ok, QMessageBox.Ok)
            return

        self.open_proj = ''
        self.open_proj_dialog = QDialog()
        self.open_proj_dialog.setWindowTitle('Open Existing Project')
        QBtn = QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        buttonBox = QDialogButtonBox(QBtn)
        buttonBox.accepted.connect(self.open_proj_accept)
        buttonBox.rejected.connect(self.open_proj_reject)

        self.open_proj_tree = QTreeWidget()
        self.open_proj_tree.setColumnCount(1)
        self.open_proj_tree.move(0, 0)
        self.open_proj_tree.setHeaderItem(QTreeWidgetItem(['Project List']))

        items = []
        dirpath = self.setx.getProjectPath()
        for file in os.listdir(dirpath):
            l1 = QTreeWidgetItem([file])
            items.append(l1)

        # for i in range(len(self.TargetFileList)):
        #     l1 = QTreeWidgetItem([self.TargetFileList[i]])
        #     tmp = l1.text(0).split(';')  # remove the file size string from filename
        #     l1.setText(0, tmp[0])
        #     if tmp[0].startswith('/') and tmp[0].find('.') == -1:  # file or folder?
        #         items.append(l1)

        self.open_proj_tree.addTopLevelItems(items)
        if len(items) > 0:
            self.open_proj_tree.setCurrentItem(items[0])  # highlight first item
        self.open_proj_tree.expandAll()
        self.open_proj_dialog.layout = QVBoxLayout()
        self.open_proj_dialog.layout.addWidget(self.open_proj_tree)
        self.open_proj_dialog.layout.addWidget(buttonBox)
        self.open_proj_dialog.setLayout(self.open_proj_dialog.layout)
        self.open_proj_dialog.setFixedWidth(400)
        self.open_proj_dialog.exec()
        if self.open_proj:
            self.setx.setCurProjectName(self.open_proj)
            self.newProjectAct.setEnabled(True)
            for i in range(self.tabsList.count() - 1, -1, -1):
                self.remove_tab(i)
            self.viewProjectFiles(dirpath + '/' + self.open_proj)

    def open_proj_accept(self):
        self.open_proj = self.open_proj_tree.currentItem().text(0)
        self.open_proj_dialog.close()

    def open_proj_reject(self):
        self.open_proj = ''
        self.open_proj_dialog.close()

    def closeCurrentProject(self):
        mod_files = self.getChangedFiles()
        if mod_files:
            QMessageBox.warning(self, 'Close Current Project', 'Some current project files have been modified.\n'
                                + 'Save or Discard modified files before continuing.',
                                QMessageBox.Ok, QMessageBox.Ok)
            return
        reply = QMessageBox.question(self, 'Close Project', 'Are you sure you want to CLOSE the current Project\n'
                                     + '"' + self.setx.getCurProjectName() + '" ?',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.No:
            return
        for i in range(self.tabsList.count()-1, -1, -1):
            self.remove_tab(i)
        self.setx.setCurProjectName('')
        self.viewProjectFiles(self.setx.getProjectPath())


    # Function to display context menu on the project file viewer
    def projectViewerContextMenu(self, position):
        pv_menu = QMenu(self.projectFileViewer)
        pv_menu.addSection('PROJECT FILE ACTIONS:')

        pv_act1 = QAction("New File")
        pv_act1.setIcon(QIcon(self.setx.getAppPath() + "/icons/newfile"))
        pv_act1.setIconVisibleInMenu(True)
        pv_act1.triggered.connect(self.newFile)
        pv_menu.addAction(pv_act1)

        pv_act2 = QAction("Open File")
        pv_act2.setIcon(QIcon(self.setx.getAppPath() + "/icons/openfile"))
        pv_act2.setIconVisibleInMenu(True)
        pv_act2.triggered.connect(self.openFile)
        pv_menu.addAction(pv_act2)

        pv_act3 = QAction("Save File")
        pv_act3.setIcon(QIcon(self.setx.getAppPath() + "/icons/savefile"))
        pv_act3.setIconVisibleInMenu(True)
        pv_act3.triggered.connect(self.fileSave)
        pv_menu.addAction(pv_act3)

        pv_act4 = QAction("Save File As...")
        pv_act4.setIcon(QIcon(self.setx.getAppPath() + "/icons/savefileas"))
        pv_act4.setIconVisibleInMenu(True)
        pv_act4.triggered.connect(self.fileSaveAs)
        pv_menu.addAction(pv_act4)

        pv_act5 = QAction("Rename File")
        pv_act5.setIcon(QIcon(self.setx.getAppPath() + "/icons/rename"))
        pv_act5.setIconVisibleInMenu(True)
        pv_act5.triggered.connect(self.renameFile)
        pv_menu.addAction(pv_act5)

        pv_act6 = QAction("Delete File")
        pv_act6.setIcon(QIcon(self.setx.getAppPath() + "/icons/delete"))
        pv_act6.setIconVisibleInMenu(True)
        pv_act6.triggered.connect(self.deleteFile)
        pv_menu.addAction(pv_act6)

        position.setY(position.y() + 50)
        pv_menu.exec(self.projectFileViewer.mapToGlobal(position))


    # delete editor and its associated tab
    def remove_tab(self, index):
        if index != self.tabsList.currentIndex():
            self.tabsList.setCurrentIndex(index)
            self.change_editor_tab(index)       # select & highlight tab to remove
        if not self.maybeSave():    # check if text in tab (editor) needs to be saved
            return
        # don't delete last tab
        if index < self.tabsList.count() and self.tabsList.count() > 1:
            self.tabsList.removeTab(index)
            del mpconfig.editorList[index]
            del mpconfig.highlighterList[index]
            del mpconfig.numberbarList[index]
            mpconfig.currentTabIndex = self.tabsList.currentIndex()
        elif self.tabsList.count() == 1:
            mpconfig.currentTabIndex = 0
            mpconfig.editorList[0].clear()
            mpconfig.editorList[0].textHasChanged = False
            self.tabsList.tabBar().setTabText(0, 'untitled')
            self.tabsList.tabBar().setTabToolTip(0, 'untitled')

    def create_new_tab(self, tab_title):
        new_tab = QWidget()
        new_tab.setObjectName('new_tab')
        new_tab.layout = QHBoxLayout()

        text_editor = PyTextEdit()
        new_cursor = QTextCursor(text_editor.document())
        text_editor.setTextCursor(new_cursor)
        text_editor.setStyleSheet("background-color: #000000;\n"
                                  "color: #a0a0a0;\n"
                                  "border-style: solid;\n"
                                  "border-color: #84aff4;\n"
                                  "border-width: 0px;\n"
                                  "border-radius: 4px;")
        text_editor.setTabStopWidth(12)
        text_editor.setObjectName('editor')
        text_editor.textChanged.connect(self.onTextHasChanged)
        text_editor.cursorPositionChanged.connect(self.onCursorPositionChanged)
        # text_editor.setContextMenuPolicy(Qt.CustomContextMenu)
        text_editor.customContextMenuRequested.connect(self.editorContextMenu)
        text_editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        text_editor.ctrl_f.activated.connect(self.ctrl_F)

        horiz_sbar = QScrollBar()
        horiz_sbar.setOrientation(Qt.Horizontal)
        horiz_sbar.setStyleSheet("""
                         QScrollBar:horizontal { background-color: #84aff4 } """)
        text_editor.setHorizontalScrollBar(horiz_sbar)

        vert_sbar = QScrollBar()
        vert_sbar.setOrientation(Qt.Vertical)
        vert_sbar.setStyleSheet("""
                         QScrollBar:vertical { background-color: #84aff4 } """)
        text_editor.setVerticalScrollBar(vert_sbar)
        text_editor.moveCursor(new_cursor.Start)
        highlighter = syntax_py.Highlighter(text_editor.document())
        mpconfig.highlighterList.append(highlighter)
        mpconfig.editorList.append(text_editor)

        mpconfig.currentTabIndex = self.tabsList.count()  # index = end of list
        num_bar = NumberBar()
        num_bar.setStyleSheet("background-color: #000000;\n" 
                              "color: #a0a0a0;\n"
                              "border-style: solid;\n"
                              "border-color: #84aff4;\n"
                              "border-width: 0px;\n"
                              "border-radius: 4px;")
        num_bar.setObjectName('num_bar')
        mpconfig.numberbarList.append(num_bar)
        new_tab.layout.addWidget(num_bar)
        new_tab.layout.addWidget(text_editor)
        new_tab.setLayout(new_tab.layout)
        # set style properties for the new tab
        new_tab.setStyleSheet("background-color: #484848;\n"    # medium grey
                              "color: #a0a0a0;\n"               # light grey
                              "border-style: solid;\n"
                              "border-width: 0px;\n"
                              "border-radius: 4px;")
        ttip = tab_title
        self.tabsList.addTab(new_tab, tab_title)
        self.tabsList.tabBar().setTabToolTip(self.tabsList.currentIndex(), ttip)
        if self.tabsList.count() > 0:
            self.tabsList.setCurrentIndex(self.tabsList.count()-1)
        self.tabsList.tabBar().setUsesScrollButtons(False)
        return new_tab

    # Ctrl-F pressed in plain text editor - focus on find field
    def ctrl_F(self):
        stext = mpconfig.editorList[mpconfig.currentTabIndex].textCursor().selectedText()
        if stext:
            self.findfield.setText(stext)
        self.findfield.setFocus(True)

    # text in the current editor has changed
    def onTextHasChanged(self):
        mpconfig.editorList[mpconfig.currentTabIndex].textHasChanged = True
        tabtxt = self.tabsList.tabText(self.tabsList.currentIndex())
        if not tabtxt.endswith('*'):
            tabtxt += '*'
            self.tabsList.setTabText(self.tabsList.currentIndex(), tabtxt)
            self.tabsList.setTabToolTip(self.tabsList.currentIndex(), tabtxt)

    # tab selection has changed - show selected tab and tab text
    def change_editor_tab(self, index):
        self.tabsList.setAutoFillBackground(True)
        c = self.tabsList.currentIndex()
        for i in range(self.tabsList.count()):
            if i == c:
                self.tabsList.tabBar().setTabTextColor(i, QColor('#FFFFFF'))
            else:
                self.tabsList.tabBar().setTabTextColor(i, QColor('#111111'))
        mpconfig.currentTabIndex = index

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and obj is self.shellText:
            if self.shellText.hasFocus():
                if event.key() == Qt.Key_Return:
                    self.mpBoard.block_cr = True
                    self.mpBoard.serialWrite(b'\x0D')
                elif event.key() == Qt.Key_Backspace:
                    self.mpBoard.serialWrite(b'\x08')
                elif event.key() == Qt.Key_Up:
                    print(event.key())
                    self.mpBoard.serialWrite(b'\x2191')
                else:
                    self.mpBoard.block_echo = True
                    self.mpBoard.serialWrite(bytes(event.text(), 'utf-8'))
        return super().eventFilter(obj, event)

    # Project File Viewer was double clicked
    def projectFileViewerDblClicked(self, index):
        item_text = self.projectFileViewer.currentItem().text(0)
        if len(item_text) > 0:
            path = self.setx.getProjectPath() + '/' + self.setx.getCurProjectName() + '/' + item_text
            self.openFile(path)
            mpconfig.editorList[mpconfig.currentTabIndex].textHasChanged = False

    def targetFileViewerDblClicked(self, index):
        titem = self.targetFileViewer.currentItem().text(0)
        # ignore dbl click on serial port name
        if titem != self.setx.getSerialPort():
            self.uploadScript(titem)

    # Reset ESP32 target device by asserting DTR
    def resetTargetDevice(self):
        self.shellTextAppend('\n<Reset Target>\n', False)
        self.mpBoard.serialOpen()
        data = self.mpBoard.hardReset()
        if data == b'':
            return
        datastr = str(data, 'utf-8')
        self.shellTextAppend(datastr, True)     # show target response after reset
        time.sleep(0.1)
        self.shellTextAppend('\n<Display Target Files>\n', True)  # show target response after reset
        self.viewTargetFiles()

    def shellTextAppend(self, text='', focus=False):
        self.shellText.moveCursor(self.cursor.End)
        self.shellText.insertPlainText(text)
        self.shellText.moveCursor(self.cursor.End)
        if focus:
            self.shellText.setFocus()


    def viewTargetFiles(self):
        self.targetFileViewer.clear()
        self.TargetFileList.clear()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.TargetFileList = self.mpCmds.ls('/', True, False)
        if self.TargetFileList:
            if self.TargetFileList[0].startswith('Failed'):
                self.shellTextAppend('\nFailed to upload target files!\n', False)
                QApplication.restoreOverrideCursor()
                return

        targ1 = QTreeWidgetItem([self.setx.getSerialPort()])
        targ1.setIcon(0, QIcon(self.setx.getAppPath() + "/icons/connect"))
        # show files in target root directory
        for i in range(len(self.TargetFileList)):
            if self.TargetFileList[i] == '':        # exit if bogus file
                break

            fn = self.TargetFileList[i].split(';', 1)   # split filename & file size
            # if the target name starts with '/' it's assumed to be a folder
            if fn[0].startswith('/', 0, 1) and fn[0].find('.') == -1:
                targ1_child = QTreeWidgetItem([fn[0], ''])
                targ1_child.setIcon(0, QIcon(self.setx.getAppPath() + "/icons/folder"))
            else:
                fn[0] = fn[0].replace('/', '', 1)
                if len(fn) > 1:
                    targ1_child = QTreeWidgetItem([fn[0], fn[1]])
                else:
                    targ1_child = QTreeWidgetItem([fn[0], ''])
                targ1_child.setIcon(0, QIcon(self.setx.getAppPath() + "/icons/file"))
            targ1.addChild(targ1_child)

        self.targetFileViewer.addTopLevelItem(targ1)
        self.targetFileViewer.setColumnWidth(0, 170)  # set col 0 size so file names aren't cropped
        self.targetFileViewer.expandAll()
        QApplication.restoreOverrideCursor()

    # Run current script on target device (file not downloaded)
    def runTargetScript(self):
        dialog = QFileDialog(self)
        dialog.setWindowTitle('Run Script on Target Device')
        dialog.setNameFilter('(*.py)')
        # Use currently edited file
        sname = self.tabsList.tabBar().tabText(self.tabsList.currentIndex())
        sname = sname.replace('*', '')
        if sname != 'untitled':
            dialog.selectFile(sname)
        dialog.setDirectory(self.setx.getProjectPath() + '/' + self.setx.getCurProjectName())
        dialog.setFileMode(QFileDialog.ExistingFile)
        filename = None
        fname = ''
        if dialog.exec_() == QDialog.Accepted:
            filename = dialog.selectedFiles()
            fname = str(filename[0])
        else:
            return
        if len(fname) == 0:
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.setx.setCurTargetScript(fname)

        self.shellTextAppend('\nStarting script: ' + fname + '\n', False)
        self.mpCmds.run(fname, False, False)
        QApplication.restoreOverrideCursor()


    def stopTargetScript(self):
        self.shellTextAppend("Stopping current script " + self.setx.getCurTargetScript() + "\n", False)
        self.mpBoard.stopScript()

    def downloadScript(self):
        hl_file = ''
        if self.targetFileViewer.currentItem() != None:
            hl_file = self.targetFileViewer.currentItem().text(0)
        dialog = QFileDialog(self)
        dialog.setWindowTitle('Download File to Target Device')
        dialog.setNameFilter('(*.py)')
        dialog.setDirectory(self.setx.getProjectPath() + '/' + self.setx.getCurProjectName())
        if hl_file.endswith('.py'):
            dialog.selectFile(hl_file)
        dialog.setFileMode(QFileDialog.ExistingFile)
        filename = None
        fname = ''
        if dialog.exec_() == QDialog.Rejected:
            return
        filename = dialog.selectedFiles()
        fname = str(filename[0])

        QApplication.setOverrideCursor(Qt.WaitCursor)
        if len(fname) > 0:
            self.mpCmds.put(fname)
            self.viewTargetFiles()
        QApplication.restoreOverrideCursor()

    def uploadScript(self, filename):
        if not self.TargetFileList:
            QMessageBox.warning(self, 'Upload Target File', 'Target File Directory is Empty.',
                                         QMessageBox.Ok, QMessageBox.Ok)
            return
        self.shellTextAppend("\n<Upload Target File>\n", False)
        if not filename:
            vLayout = QVBoxLayout()
            self.upldDialog = QDialog()
            self.upldDialog.setWindowFlags(self.upldDialog.windowFlags() | Qt.Popup)
            self.upldDialog.setWindowFlags(self.upldDialog.windowFlags() & ~(Qt.WindowContextHelpButtonHint |
                                                                             Qt.WindowMinMaxButtonsHint))
            self.upldDialog.setWindowModality(Qt.ApplicationModal)
            self.upldDialog.setMinimumWidth(450)

            self.upldTree = QTreeWidget()
            self.upldTree.setColumnCount(1)
            self.upldTree.move(0, 0)
            self.upldDialog.setWindowTitle("Upload File from Target Device")

            self.upldTree.setHeaderItem(QTreeWidgetItem([self.setx.getSerialPort()]))
            items = []
            for i in range(len(self.TargetFileList)):
                l1 = QTreeWidgetItem([self.TargetFileList[i]])
                tmp = l1.text(0).split(';')     # remove the file size string from filename
                l1.setText(0, tmp[0])
                items.append(l1)

            self.upldTree.addTopLevelItems(items)
            if len(items) > 0:
                self.upldTree.setCurrentItem(items[0])  # highlight first item

            self.upldTree.expandAll()
            vLayout.addWidget(self.upldTree)

            hLayout = QHBoxLayout()
            hLayout.addStretch()
            btn_ok = QPushButton("OK")
            btn_ok.clicked.connect(self.upldDialogAccept)
            btn_ok.setToolTip('Accept File')
            btn_ok.setMaximumWidth(100)
            hLayout.addWidget(btn_ok, 1, Qt.AlignHCenter);
            self.upldTree.itemDoubleClicked.connect(self.upldDialogAccept)
            hLayout.addWidget(btn_ok)
            btn_cancel = QPushButton("Cancel")
            btn_cancel.clicked.connect(self.upldDialogCancel)
            btn_cancel.setToolTip('Cancel')
            btn_cancel.setMaximumWidth(100)
            btn_cancel.setContentsMargins(0, 0, 0, 0)
            hLayout.addWidget(btn_cancel, 1, Qt.AlignHCenter)
            hLayout.addStretch()
            hLayout.setSpacing(0)
            vLayout.addLayout(hLayout)
            self.upldDialog.setLayout(vLayout)
            self.upldTree.setFocus()
            self.upldDialog.exec_()

            # dialog has closed - check if the entry was accepted or rejected
            if self.upldDialog.result() == QDialog.Rejected:
                return

            filename = self.upldTree.currentItem().text(0)

        # check if file is already opened on current or another tab
        dup_fname = self.searchTabNames(filename, True)
        # check if destination tab already has text
        txt = mpconfig.editorList[mpconfig.currentTabIndex].toPlainText()
        if len(txt) > 0:
            if dup_fname == -1:
                self.create_new_tab(filename)
            else:
                reply = QMessageBox.question(self, 'Upload Target File', 'Do you want to overwrite existing text?',
                                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.No:
                    return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        data = self.mpCmds.get(filename)
        data = str(data, 'utf-8')  # convert bytes to string
        mpconfig.editorList[mpconfig.currentTabIndex].setPlainText(data.replace(tab, "    "))
        # uploaded file shown as modified.
        mpconfig.editorList[mpconfig.currentTabIndex].textHasChanged = True
        filename += '*'
        self.tabsList.tabBar().setTabText(self.tabsList.currentIndex(), filename)  # update editor tab text
        QApplication.restoreOverrideCursor()

    def upldDialogCancel(self):
        self.upldDialog.reject()  #  .setResult(0)
        self.upldDialog.close()

    def upldDialogAccept(self):
        self.upldDialog.accept()
        self.upldDialog.close()

    # Serach for duplicate file names in tab text
    # fname = filename string (case insensitive). if change_tab is True, dup tab will be selected
    # return - tab # or -1 if duplicate not found
    def searchTabNames(self, fname, change_tab=False):
        fnd = -1
        for i in range(self.tabsList.count()):
            tn = self.tabsList.tabBar().tabText(i)
            tn = tn.replace('*', '')
            if tn.lower() == fname.lower():
                if change_tab:      # change tab to matched name
                    self.tabsList.setCurrentIndex(i)
                    mpconfig.currentTabIndex = i
                fnd = i
                break
        return fnd

    # remove (delete) script file in target file system
    def removeScript(self):
        # Create a dialog to select the target file to be removed
        vLayout = QVBoxLayout()
        self.rmScriptDialog = QDialog()
        self.rmScriptDialog.setWindowFlags(self.rmScriptDialog.windowFlags() | Qt.Popup)
        self.rmScriptDialog.setWindowFlags(self.rmScriptDialog.windowFlags() & ~(Qt.WindowContextHelpButtonHint |
                                                                         Qt.WindowMinMaxButtonsHint))
        self.rmScriptDialog.setWindowModality(Qt.ApplicationModal)
        self.rmScriptDialog.setMinimumWidth(450)
        self.rmScriptDialog.setWindowTitle("Remove File from Target Device")

        self.rmTree = QTreeWidget()
        self.rmTree.setColumnCount(1)
        self.rmTree.move(0, 0)
        self.rmTree.setHeaderItem(QTreeWidgetItem([self.setx.getSerialPort()]))
        items = []
        for i in range(len(self.TargetFileList)):
            l1 = QTreeWidgetItem([self.TargetFileList[i]])
            tmp = l1.text(0).split(';')  # remove the file size string from filename
            l1.setText(0, tmp[0])
            items.append(l1)

        self.rmTree.addTopLevelItems(items)
        if len(items) > 0:
            self.rmTree.setCurrentItem(items[0])  # highlight first item

        self.rmTree.expandAll()
        vLayout.addWidget(self.rmTree)

        hLayout = QHBoxLayout()
        hLayout.addStretch()
        btn_ok = QPushButton("OK")
        btn_ok.clicked.connect(self.rm_dialog_accept)
        btn_ok.setToolTip('Accept File')
        btn_ok.setMaximumWidth(100)
        hLayout.addWidget(btn_ok, 1, Qt.AlignHCenter);
        self.rmTree.itemDoubleClicked.connect(self.rm_dialog_accept)
        hLayout.addWidget(btn_ok)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.rm_dialog_cancel)
        btn_cancel.setToolTip('Cancel')
        btn_cancel.setMaximumWidth(100)
        btn_cancel.setContentsMargins(0, 0, 0, 0)
        hLayout.addWidget(btn_cancel, 1, Qt.AlignHCenter)
        hLayout.addStretch()
        hLayout.setSpacing(0)
        vLayout.addLayout(hLayout)
        self.rmScriptDialog.setLayout(vLayout)
        self.rmTree.setFocus()
        self.rmScriptDialog.exec_()

        # dialog has closed - check if the entry was accepted or rejected
        if self.rmScriptDialog.result() == QDialog.Accepted:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            self.mpCmds.rm(self.rmTree.currentItem().text(0))
            self.viewTargetFiles()
            QApplication.restoreOverrideCursor()

    def rm_dialog_cancel(self):
        self.rmScriptDialog.reject()  #  .setResult(0)
        self.rmScriptDialog.close()

    def rm_dialog_accept(self):
        self.rmScriptDialog.accept()
        self.rmScriptDialog.close()

    def newTargetFolder(self):
        self.newdir = ''
        self.ntarg_dialog = QDialog()
        self.ntarg_dialog.setWindowTitle('Create New Target Folder')
        QBtn = QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        buttonBox = QDialogButtonBox(QBtn)
        buttonBox.accepted.connect(self.ntarg_accept)
        buttonBox.rejected.connect(self.ntarg_reject)

        self.ntarg_dialog.layout = QVBoxLayout()
        self.ntarg_edit = QLineEdit()
        self.ntarg_edit.setPlaceholderText('new folder name')
        self.ntarg_dialog.layout.addWidget(self.ntarg_edit)
        self.ntarg_dialog.layout.addWidget(buttonBox)
        self.ntarg_dialog.setLayout(self.ntarg_dialog.layout)
        self.ntarg_dialog.setFixedWidth(400)
        self.ntarg_dialog.exec()
        if self.newdir:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            self.mpCmds.mkdir(self.newdir)
            self.viewTargetFiles()
            QApplication.restoreOverrideCursor()

    def ntarg_accept(self):
        self.newdir = self.ntarg_edit.text()
        self.ntarg_dialog.close()

    def ntarg_reject(self):
        self.newdir = ''
        self.ntarg_dialog.close()

    def rmTargetFolder(self):
        self.rm_dir = ''
        self.rm_dir_dialog = QDialog()
        self.rm_dir_dialog.setWindowTitle('Remove Target Folder')
        QBtn = QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        buttonBox = QDialogButtonBox(QBtn)
        buttonBox.accepted.connect(self.rm_dir_accept)
        buttonBox.rejected.connect(self.rm_dir_reject)

        self.rm_dir_tree = QTreeWidget()
        self.rm_dir_tree.setColumnCount(1)
        self.rm_dir_tree.move(0, 0)
        self.rm_dir_tree.setHeaderItem(QTreeWidgetItem(['Target Folders']))

        items = []
        for i in range(len(self.TargetFileList)):
            l1 = QTreeWidgetItem([self.TargetFileList[i]])
            tmp = l1.text(0).split(';')  # remove the file size string from filename
            l1.setText(0, tmp[0])
            if tmp[0].startswith('/') and tmp[0].find('.') == -1:    # file or folder?
                items.append(l1)

        self.rm_dir_tree.addTopLevelItems(items)
        if len(items) > 0:
            self.rm_dir_tree.setCurrentItem(items[0])  # highlight first item
        self.rm_dir_tree.expandAll()
        self.rm_dir_dialog.layout = QVBoxLayout()
        self.rm_dir_dialog.layout.addWidget(self.rm_dir_tree)
        self.rm_dir_dialog.layout.addWidget(buttonBox)
        self.rm_dir_dialog.setLayout(self.rm_dir_dialog.layout)
        self.rm_dir_dialog.setFixedWidth(400)
        self.rm_dir_dialog.exec()
        if self.rm_dir:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            self.mpCmds.rmdir(self.rm_dir)
            self.viewTargetFiles()
            QApplication.restoreOverrideCursor()

    def rm_dir_accept(self):
        self.rm_dir = self.rm_dir_tree.currentItem().text(0)
        self.rm_dir_dialog.close()

    def rm_dir_reject(self):
            self.rm_dir = ''
            self.rm_dir_dialog.close()

    # Erase target memory prior to programming with (presumably) microPython
    def eraseTargetFlash(self):
        ret = QMessageBox.question(self, "Erase Target Memory",
                                   "<h4><p>This action will ERASE target flash memory.</p>\n" \
                                   "<p>Do you want to CONTINUE erasure?</p></h4>",
                                   QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.Yes:
            self.shellTextAppend('Erasing Target Memory...\n', False)
            procCmdStr = ''
            if self.setx.getMCU() == 'ESP8266':
                procCmdStr = 'esptool.py --port ' + self.setx.getSerialPort() + ' erase_flash'
            elif self.setx.getMCU() == 'ESP32C3':
                procCmdStr = 'esptool.py --chip esp32c3 --port ' + self.setx.getSerialPort() + ' erase_flash'
            elif self.setx.getMCU() == 'ESP32S2':
                procCmdStr = 'esptool.py --chip esp32s2 --port ' + self.setx.getSerialPort() + ' erase_flash'
            elif self.setx.getMCU() == 'ESP32S3':
                procCmdStr = 'esptool.py --chip esp32s3beta2 --port ' + self.setx.getSerialPort() + ' erase_flash'
            self.mpBoard.serialClose()
            self.startProcess(procCmdStr)
        return

    # Program target memory with (presumably) microPython
    def flashTargetFirmware(self):
        ret = QMessageBox.question(self, "Program Target Memory",
                                   "<h4><p>This will PROGRAM target flash memory.</p>\n" \
                                   "<p>Do you want to CONTINUE programming?</p></h4>",
                                   QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.No:
            return

        self.pgmf_path = self.setx.getAppPath() + '/microPython'
        self.pgmf_name, _ = QFileDialog.getOpenFileName(self, "Open Firmware File", self.pgmf_path,
                                                        "Binary files (*.bin)")
        if not self.pgmf_name or not self.pgmf_name.endswith('.bin'):  # exit if dialog rejected
            self.shellTextAppend('Programming Target Cancelled!\n', False)
            return

        self.shellTextAppend('Programming Target Memory...\n', False)
        chip = self.setx.getMCU().lower()
        procCmdStr = ''
        if chip == 'esp8266':
            procCmdStr = 'esptool.py --port ' + self.setx.getSerialPort() +\
                     ' --baud 460800 write_flash --flash_size=detect 0 ' + self.pgmf_name
        elif chip == 'esp32c3':
            procCmdStr = 'esptool.py --chip ' + chip + ' --port ' + self.setx.getSerialPort() + \
                         ' --baud 460800 write_flash -z 0x0 ' + self.pgmf_name
        elif self.setx.getMCU() == 'esp32s2':
            procCmdStr = 'esptool.py --chip ' + chip + ' --port ' + self.setx.getSerialPort() + \
                         ' --baud 460800 write_flash -z 0x1000 ' + self.pgmf_name
        elif self.setx.getMCU() == 'esp32s3':
            procCmdStr = 'esptool.py --chip esp32s3beta2 --port ' + self.setx.getSerialPort() + \
                         ' write_flash -z 0 ' + self.pgmf_name
        if procCmdStr:
            self.mpBoard.serialClose()
            self.startProcess(procCmdStr)
        else:
            self.shellTextAppend('Chip ' + chip + ' not currently supported!\n', False)

    def pgmf_accept(self):
        self.pgmf_name = self.pgmfedit.text()
        self.pgmfdialog.close()

    def pgmf_reject(self):
        self.pgmf_name = ''
        self.pgmfdialog.close()

        return

    # Start external process. procCmdStr has the name of the external process and its arguments
    def startProcess(self, procCmdStr):
        if len(procCmdStr) == 0:
            return
        if self.extProc.atEnd():  # No process running if true.
            self.extProc.finished.connect(self.procFinished)
            self.extProc.readyReadStandardOutput.connect(self.procHandleStdout)
            self.extProc.readyReadStandardError.connect(self.procHandleStderr)
            self.extProc.stateChanged.connect(self.procHandleState)
            self.extProc.start(procCmdStr)
            self.extProc.waitForStarted(3000)
        else:
            self.shellTextAppend('Run process failed! Another process is currently running.\n', False)

    def procHandleStderr(self):
        data = self.extProc.readAllStandardError()
        stderr = bytes(data).decode("utf8")
        self.shellTextAppend(stderr, False)

    # external process returns data
    def procHandleStdout(self):
        data = self.extProc.readAllStandardOutput()
        stdout = bytes(data).decode("utf8")     # convert bytearray to string
        self.shellTextAppend(stdout, False)

    def procHandleState(self, state):
        states = {
            QProcess.NotRunning: 'Stopped',
            QProcess.Starting: 'Starting',
            QProcess.Running: 'Running',
        }
        state_name = states[state]
        # reopen closed serial port so REPL will work
        # if 'Stopped' in state_name:
        #     self.serialport.open(QIODevice.ReadWrite)
        self.shellTextAppend(f"State changed: {state_name}", False)

    def procFinished(self):
        self.shellTextAppend('\nExternal process has Completed!\n', False)
        if not self.mpBoard.isSerialOpen():
            self.mpBoard.serialOpen()

    def setBaudrate(self, baud):
        self.setx.setBaudRate(baud)
        self.mpBoard.setSerialPortBaudrate(baud)

    def saveComPort(self, comport):
        self.setx.setSerialPort(comport)
        self.mpBoard.setSerialPortName(comport)

    def keyPressEvent(self, event):
        if mpconfig.currentTabIndex >= 0:
            if mpconfig.editorList[mpconfig.currentTabIndex].hasFocus():
                if event.key() == Qt.Key_F10:
                    self.findNextWord()

    def onCursorPositionChanged(self):
        if mpconfig.currentTabIndex >= 0:
            line = mpconfig.editorList[mpconfig.currentTabIndex].textCursor().blockNumber() + 1
            pos = mpconfig.editorList[mpconfig.currentTabIndex].textCursor().positionInBlock()
            self.lineLabel.setText(" Ln:" + str(line) + " | Col:" + str(pos))

    def textColor(self):
        col = QColorDialog.getColor(QColor("#" + mpconfig.editorList[mpconfig.currentTabIndex].textCursor().selectedText()), self)
        self.pix.fill(col)
        if not col.isValid():
            return
        else:
            colorname = 'QColor("' + col.name() + '")'
            mpconfig.editorList[mpconfig.currentTabIndex].textCursor().insertText(colorname)
            self.pix.fill(col)

    def loadTemplates(self):
        folder = self.setx.getAppPath() + "/templates"
        if QDir().exists(folder):
            self.currentDir = QDir(folder)
            count = self.currentDir.count()
            fileName = "*"
            files = self.currentDir.entryList([fileName], QDir.Files | QDir.NoSymLinks)
            for i in range(count - 2):
                file = (files[i])
                if file.endswith(".txt"):
                    self.templates.addItem(file.replace(self.setx.getAppPath() + "/templates", "").replace(".txt", ""))

    def reindentText(self):
        if mpconfig.editorList[mpconfig.currentTabIndex].toPlainText() == '':  # or \
                        # mpconfig.editorList[mpconfig.currentTabIndex].toPlainText() == self.mainText:
            self.statusBar().showMessage("no code to reindent")
        else:
            mpconfig.editorList[mpconfig.currentTabIndex].selectAll()
            tab = "\t"
            oldtext = mpconfig.editorList[mpconfig.currentTabIndex].textCursor().selectedText()
            newtext = oldtext.replace(tab, "    ")      # use spaces instead of tab char
            mpconfig.editorList[mpconfig.currentTabIndex].textCursor().insertText(newtext)
            self.statusBar().showMessage("reindented")

    def insertColor(self):
        col = QColorDialog.getColor(QColor("#000000"), self)
        if not col.isValid():
            return
        else:
            colorname = 'QColor("' + col.name() + '")'
            mpconfig.editorList[mpconfig.currentTabIndex].textCursor().insertText(colorname)

    def changeColor(self):
        if not mpconfig.editorList[mpconfig.currentTabIndex].textCursor().selectedText() == "":
            col = QColorDialog.getColor(QColor("#" + mpconfig.editorList[mpconfig.currentTabIndex].textCursor().selectedText()), self)
            if not col.isValid():
                return
            else:
                colorname = col.name()
                mpconfig.editorList[mpconfig.currentTabIndex].textCursor().insertText(colorname.replace("#", ""))
        else:
            col = QColorDialog.getColor(QColor("black"), self)
            if not col.isValid():
                return
            else:
                colorname = col.name()
                mpconfig.editorList[mpconfig.currentTabIndex].textCursor().insertText(colorname)

    # QPlainTextEdit contextMenu (Right Click on current python editor))
    def editorContextMenu(self, position):
        edit_context_menu = QMenu(mpconfig.editorList[mpconfig.currentTabIndex])
        edit_context_menu.setObjectName("edit_context_menu")
        edit_context_menu.setSeparatorsCollapsible(False)
        edit_context_menu.setToolTipsVisible(True)
        #edit_context_menu.addSection('EDITOR ACTIONS:')
        edit_context_menu.setStyleSheet("QMenu { background-color: #202020;\n"  
                              "color: #d0d0d0;\n"
                              "font-size: 9pt;\n"
                              "border-style: solid;\n"
                              "border-width: 1px;\n"
                              "border-radius: 5px; }"
                              "QMenu#edit_context_menu:selected { background-color: #d8691a; color: #d0d0d0; }")


        edcm_act1 = QAction("Undo")
        edcm_act1.setIcon(QIcon.fromTheme('edit-undo'))
        edcm_act1.setIconVisibleInMenu(True)
        edcm_act1.triggered.connect(self.textUndo)
        edit_context_menu.addAction(edcm_act1)

        edcm_act2 = QAction("Redo")
        edcm_act2.setIcon(QIcon.fromTheme('edit-redo'))
        edcm_act2.setIconVisibleInMenu(True)
        edcm_act2.triggered.connect(self.textRedo)
        edit_context_menu.addAction(edcm_act2)

        edcm_act3 = QAction("Copy")
        edcm_act3.setIcon(QIcon.fromTheme('edit-copy'))
        edcm_act3.setIconVisibleInMenu(True)
        edcm_act3.triggered.connect(self.textCopy)
        edit_context_menu.addAction(edcm_act3)

        edcm_act4 = QAction("Cut")
        edcm_act4.setIcon(QIcon.fromTheme('edit-cut'))
        edcm_act4.setIconVisibleInMenu(True)
        edcm_act4.triggered.connect(self.textCut)
        edit_context_menu.addAction(edcm_act4)

        edcm_act5 = QAction("Paste")
        edcm_act5.setIcon(QIcon.fromTheme('edit-paste'))
        edcm_act5.setIconVisibleInMenu(True)
        edcm_act5.triggered.connect(self.textPaste)
        edit_context_menu.addAction(edcm_act5)

        edcm_act6 = QAction("Delete")
        edcm_act6.setIcon(QIcon.fromTheme('edit-delete'))
        edcm_act6.setIconVisibleInMenu(True)
        edcm_act6.triggered.connect(self.textCut)
        edit_context_menu.addAction(edcm_act6)

        edcm_act7 = QAction("Select All")
        edcm_act7.setIcon(QIcon.fromTheme('edit-select-all'))
        edcm_act7.setIconVisibleInMenu(True)
        edcm_act7.triggered.connect(self.textSelectAll)
        edit_context_menu.addAction(edcm_act7)

        edcm_act8 = QAction("Comment Line")
        edcm_act8.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/comment"))
        edcm_act8.setIconVisibleInMenu(True)
        edcm_act8.triggered.connect(self.commentLine)
        edit_context_menu.addAction(edcm_act8)

        edcm_act9 = QAction("UnComment Line")
        edcm_act9.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/uncomment"))
        edcm_act9.setIconVisibleInMenu(True)
        edcm_act9.triggered.connect(self.uncommentLine)
        edit_context_menu.addAction(edcm_act9)

        edcm_act910 = QAction("Comment Block")
        edcm_act910.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/commentBlock"))
        edcm_act910.setIconVisibleInMenu(True)
        edcm_act910.triggered.connect(self.commentBlock)
        edit_context_menu.addAction(edcm_act910)

        edcm_act911 = QAction("UnComment Block")
        edcm_act911.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/uncommentBlock"))
        edcm_act911.setIconVisibleInMenu(True)
        edcm_act911.triggered.connect(self.uncommentBlock)
        edit_context_menu.addAction(edcm_act911)

        edcm_act912 = QAction("Indent More")
        edcm_act912.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/indent"))
        edcm_act912.setIconVisibleInMenu(True)
        edcm_act912.triggered.connect(self.indentLine)
        edit_context_menu.addAction(edcm_act912)

        edcm_act913 = QAction("Indent Less")
        edcm_act913.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/unindent"))
        edcm_act913.setIconVisibleInMenu(True)
        edcm_act913.triggered.connect(self.unindentLine)
        edit_context_menu.addAction(edcm_act913)

        position.setY(position.y() + 0)
        edit_context_menu.exec(mpconfig.editorList[mpconfig.currentTabIndex].mapToGlobal(position))

    def replaceThis(self):
        rtext = mpconfig.editorList[mpconfig.currentTabIndex].textCursor().selectedText()
        text = QInputDialog.getText(self, "replace with", "replace '" + rtext + "' with:", QLineEdit.Normal, "")
        oldtext = mpconfig.editorList[mpconfig.currentTabIndex].document().toPlainText()
        if not (text[0] == ""):
            newtext = oldtext.replace(rtext, text[0])
            mpconfig.editorList[mpconfig.currentTabIndex].setPlainText(newtext)
            self.setModified(True)

    def showZeal(self):
        if mpconfig.editorList[mpconfig.currentTabIndex].textCursor().selectedText() == "":
            tc = mpconfig.editorList[mpconfig.currentTabIndex].textCursor()
            tc.select(QTextCursor.WordUnderCursor)
            rtext = tc.selectedText()
        else:
            rtext = mpconfig.editorList[mpconfig.currentTabIndex].textCursor().selectedText()
        cmd = "zeal " + str(rtext)
        QProcess().startDetached(cmd)

    def findNextWord(self):
        if mpconfig.editorList[mpconfig.currentTabIndex].textCursor().selectedText() == "":
            mpconfig.editorList[mpconfig.currentTabIndex].moveCursor(QTextCursor.StartOfWord, QTextCursor.MoveAnchor)
            mpconfig.editorList[mpconfig.currentTabIndex].moveCursor(QTextCursor.EndOfWord, QTextCursor.KeepAnchor)
        rtext = mpconfig.editorList[mpconfig.currentTabIndex].textCursor().selectedText()
        self.findfield.setText(rtext)
        self.findText()

    def indentLine(self):
        if not mpconfig.editorList[mpconfig.currentTabIndex].textCursor().selectedText() == "":
            newline = u"\u2029"
            list = []
            ot = mpconfig.editorList[mpconfig.currentTabIndex].textCursor().selectedText()
            theList = ot.splitlines()
            linecount = ot.count(newline)
            if linecount and ot.endswith(newline):    # don't count the last newline
                linecount -= 1
            for i in range(linecount + 1):
                list.insert(i, "    " + theList[i])
            mpconfig.editorList[mpconfig.currentTabIndex].textCursor().insertText(newline.join(list))
            self.setModified(True)
            self.statusBar().showMessage("tabs indented")

    def unindentLine(self):
        if not mpconfig.editorList[mpconfig.currentTabIndex].textCursor().selectedText() == "":
            newline = u"\u2029"
            list = []
            ot = mpconfig.editorList[mpconfig.currentTabIndex].textCursor().selectedText()
            theList = ot.splitlines()
            linecount = ot.count(newline)
            if linecount and ot.endswith(newline):  # don't count the last newline
                linecount -= 1
            for i in range(linecount + 1):
                list.insert(i, (theList[i]).replace("    ", "", 1))
            mpconfig.editorList[mpconfig.currentTabIndex].textCursor().insertText(newline.join(list))
            self.setModified(True)
            #            mpconfig.editorList[mpconfig.currentTabIndex].find(ot)
            self.statusBar().showMessage("tabs deleted")

    def createActions(self):
        maxf = int(self.setx.getMaxRecentFiles())
        for i in range(maxf):
            self.recentFileActs.append(QAction(self, visible=False, triggered=self.openRecentFile))

    def addBookmark(self):
        linenumber = self.getLineNumber()
        linetext = mpconfig.editorList[mpconfig.currentTabIndex].textCursor().block().text().strip()
        self.bookmarks.addItem(str(linenumber) + ') ' + linetext, linenumber)

    def getLineNumber(self):
        mpconfig.editorList[mpconfig.currentTabIndex].moveCursor(self.cursor.StartOfLine)
        linenumber = mpconfig.editorList[mpconfig.currentTabIndex].textCursor().blockNumber() + 1
        return linenumber

    def gotoLine(self):
        ln = int(self.gotofield.text())
        linecursor = QTextCursor(mpconfig.editorList[mpconfig.currentTabIndex].document().findBlockByLineNumber(ln - 1))
        mpconfig.editorList[mpconfig.currentTabIndex].moveCursor(QTextCursor.End)
        mpconfig.editorList[mpconfig.currentTabIndex].setTextCursor(linecursor)

    def gotoErrorLine(self, ln):
        if ln.isalnum:
            t = int(ln)
            if t != 0:
                linecursor = QTextCursor(mpconfig.editorList[mpconfig.currentTabIndex].document().findBlockByLineNumber(t - 1))
                mpconfig.editorList[mpconfig.currentTabIndex].moveCursor(QTextCursor.End)
                mpconfig.editorList[mpconfig.currentTabIndex].setTextCursor(linecursor)
                mpconfig.editorList[mpconfig.currentTabIndex].moveCursor(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
            else:
                return

    def gotoBookmark(self):
        linenum = self.bookmarks.currentData()
        ttext = mpconfig.editorList[mpconfig.currentTabIndex].toPlainText()
        bm_lines = ttext.splitlines()
        cursor_offset = 0
        # find absolute offset to target line number
        for i in range(linenum):
            cursor_offset += len(bm_lines[i])

        mpconfig.editorList[mpconfig.currentTabIndex].centerCursor()    # force scroll if needed
        cur_cursor = mpconfig.editorList[mpconfig.currentTabIndex].textCursor()
        cur_cursor.setPosition(cursor_offset)
        mpconfig.editorList[mpconfig.currentTabIndex].setTextCursor(cur_cursor)

    def gotoBookmarkFromMenu(self):
        if mpconfig.editorList[mpconfig.currentTabIndex].textCursor().selectedText() == "":
            tc = mpconfig.editorList[mpconfig.currentTabIndex].textCursor()
            tc.select(QTextCursor.WordUnderCursor)
            rtext = tc.selectedText()
        else:
            rtext = mpconfig.editorList[mpconfig.currentTabIndex].textCursor().selectedText()
        toFind = rtext
        self.bookmarks.setCurrentIndex(0)
        if self.bookmarks.findText(toFind, Qt.MatchContains):
            row = self.bookmarks.findText(toFind, Qt.MatchContains)
            self.statusBar().showMessage("found '" + toFind + "' at bookmark " + str(row))
            self.bookmarks.setCurrentIndex(row)
            self.gotoBookmark()
        else:
            self.statusBar().showMessage("def not found")

    def clearBookmarks(self):
        self.bookmarks.clear()

    #### find lines with def or class
    def findBookmarks(self):
        mpconfig.editorList[mpconfig.currentTabIndex].setFocus()
        mpconfig.editorList[mpconfig.currentTabIndex].moveCursor(QTextCursor.Start)
        ot = mpconfig.editorList[mpconfig.currentTabIndex].toPlainText()
        if not ot:
            self.clearBookmarks()
            newline = "\n"
            fr = "from"
            im = "import"
            d = "def"
            d2 = "    def"
            c = "class"
            sn = str("if __name__ ==")
            line = ""
            list = []
            theList = ot.split(newline)
            linecount = ot.count(newline)
            for i in range(linecount + 1):
                if theList[i].startswith(im):
                    line = str(theList[i]).replace("'\t','[", "").replace("]", "")
                    self.bookmarks.addItem(str(line), i)
                elif theList[i].startswith(fr):
                    line = str(theList[i]).replace("'\t','[", "").replace("]", "")
                    self.bookmarks.addItem(str(line), i)
                elif theList[i].startswith(c):
                    line = str(theList[i]).replace("'\t','[", "").replace("]", "")
                    self.bookmarks.addItem(str(line), i)
                elif theList[i].startswith(tab + d):
                    line = str(theList[i]).replace(tab, "").replace("'\t','[", "").replace("]", "")
                    self.bookmarks.addItem(str(line), i)
                elif theList[i].startswith(d):
                    line = str(theList[i]).replace(tab, "").replace("'\t','[", "").replace("]", "")
                    self.bookmarks.addItem(str(line), i)
                elif theList[i].startswith(d2):
                    line = str(theList[i]).replace(tab, "").replace("'\t','[", "").replace("]", "")
                    self.bookmarks.addItem(str(line), i)
                elif theList[i].startswith(sn):
                    line = str(theList[i]).replace("'\t','[", "").replace("]", "")
                    self.bookmarks.addItem(str(line), i)

        self.statusBar().showMessage("bookmarks changed")

    def clearShellTerminal(self):
        self.shellText.setText("")
        self.shellText.moveCursor(self.cursor.End)
        self.shellText.setFocus()

    def openRecentFile(self):
        action = self.sender()
        if action:
            myfile = action.data()
            # print('open recent file: ' + myfile)
            if (self.maybeSave()):
                if QFile.exists(myfile):
                    self.openFileOnStart(myfile)
                else:
                    self.msgbox("Info", "File does not exist!")

    ### Create New File
    def newFile(self):
        self.newf_name = 'untitled'
        self.fdialog = QDialog()
        self.fdialog.setWindowTitle('Enter New File Name')
        QBtn = QDialogButtonBox.Ok | QDialogButtonBox.Cancel

        buttonBox = QDialogButtonBox(QBtn)
        buttonBox.accepted.connect(self.newf_accept)
        buttonBox.rejected.connect(self.newf_reject)

        self.fdialog.layout = QVBoxLayout()
        self.fileedit = QLineEdit()
        self.fileedit.setPlaceholderText('file.ext')
        self.fdialog.layout.addWidget(self.fileedit)
        self.fdialog.layout.addWidget(buttonBox)
        self.fdialog.setLayout(self.fdialog.layout)
        self.fdialog.setFixedWidth(400)
        self.fdialog.exec()                 # launch the file name dialog
        if not self.newf_name:              # exit if dialog rejected
            return

        # Check if new file name already exists in project directory
        dirpath = self.setx.getProjectPath() + '/' + self.setx.getCurProjectName()
        for file in os.listdir(dirpath):
            if self.newf_name.lower() == file.lower():
                QMessageBox.warning(self, 'Error!', 'File name <' + self.newf_name + '> already exists!')
                return

        # check if the filename already exists in another tab
        dup_tab = self.searchTabNames(self.newf_name, True)
        if dup_tab == -1 and self.tabsList.tabText(self.tabsList.currentIndex()) != 'untitled':
            self.create_new_tab(path)
            # If the editor tab is 'untitled' and there is text in the current editor, create new editor tab
        elif dup_tab == -1 and self.tabsList.tabText(self.tabsList.currentIndex()) == 'untitled' \
                and mpconfig.editorList[mpconfig.currentTabIndex].toPlainText() != '':
            self.create_new_tab(path)
        self.change_editor_tab(mpconfig.currentTabIndex)
        mpconfig.editorList[mpconfig.currentTabIndex].textHasChanged = False
        mpconfig.editorList[mpconfig.currentTabIndex].moveCursor(self.cursor.End)
        self.statusBar().showMessage("new File (" + self.newf_name + ") created.")
        self.newf_name += '*'       # force file to be saved
        self.tabsList.tabBar().setTabText(self.tabsList.currentIndex(), self.newf_name)     # update editor tab text
        mpconfig.editorList[mpconfig.currentTabIndex].setFocus()
        self.bookmarks.clear()
        self.setWindowTitle('new File[*]')
        # self.filename = self.newf_name
        self.fileSave()
        self.viewProjectFiles()

    def newf_accept(self):
        self.newf_name = self.fileedit.text()
        self.fdialog.close()

    def newf_reject(self):
        self.newf_name = ''
        self.fdialog.close()

    ### open File
    def openFileOnStart(self, path=None):
        if os.path.isfile(path):
            inFile = QFile(path)
            if inFile.open(QFile.ReadWrite | QFile.Text):
                text = inFile.readAll()         # get bytes from file
                inFile.close()
                text = str(text, encoding='utf8')   # convert bytes to string
                fn = os.path.basename(path)
                dup_fname = self.searchTabNames(fn, True)
                # if the editor tab contains a file name and the new file is not a duplicate, create new editor tab
                if dup_fname == -1 and self.tabsList.tabText(self.tabsList.currentIndex()) != 'untitled':
                    self.create_new_tab(path)
                # If the editor tab is 'untitled' and there is text in the current editor, create new editor tab
                elif dup_fname == -1 and self.tabsList.tabText(self.tabsList.currentIndex()) == 'untitled' \
                        and mpconfig.editorList[mpconfig.currentTabIndex].toPlainText() != '':
                    self.create_new_tab(path)

                if mpconfig.editorList[mpconfig.currentTabIndex].toPlainText() == '':
                    mpconfig.editorList[mpconfig.currentTabIndex].setPlainText(text.replace(tab, "    "))
                    self.setModified(False)
                self.setCurrentFile(path, False)
                self.statusBar().showMessage('File ' + path + ' loaded.')
                mpconfig.editorList[mpconfig.currentTabIndex].moveCursor(QTextCursor.End)
                mpconfig.editorList[mpconfig.currentTabIndex].setFocus()
            else:
                print('Failed opening file: ' + path)

    ### Open File
    def openFile(self, path=None):
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Open File", self.setx.getProjectPath() + '/' +
                                                  self.setx.getCurProjectName(), "Python Files (*.py);; all Files (*)")
        if path:
            self.openFileOnStart(path)

    ### Save file
    def fileSave(self, ask_overwrite=False):
        # filename is kept in tab text
        fn = self.tabsList.tabBar().tabText(self.tabsList.currentIndex())   # filename on current editor tab
        if not fn.endswith('*'):    # exit if text is unchanged
            return

        fpath = self.setx.getProjectPath() + '/' + self.setx.getCurProjectName()
        if ask_overwrite:
            if self.findFileDup(fn, fpath):
                reply = QMessageBox.question(self, 'File Already Exists!', 'Do you want to OVERWRITE the file?',
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.No:
                    return

        if fn.endswith('*'):
            fn = fn.replace('*', '')
        fpath += '/' + fn       # full path to file
        if fn and fn != 'untitled':
            file = QFile(fpath)
            if not file.open(QFile.WriteOnly | QFile.Text):
                QMessageBox.warning(self, "Error!",
                                    "Cannot write file %s:\n%s." % (fpath, file.errorString()))
                return

            QApplication.setOverrideCursor(Qt.WaitCursor)
            outstr = QTextStream(file)
            outstr << mpconfig.editorList[mpconfig.currentTabIndex].toPlainText()   # write text to file & close
            file.close()
            self.setModified(False)
            self.statusBar().showMessage('File ' + fn + ' saved.')
            self.setCurrentFile(fpath, False)
            mpconfig.editorList[mpconfig.currentTabIndex].setFocus()
            self.viewProjectFiles()
            QApplication.restoreOverrideCursor()
        else:
            self.fileSaveAs()

    ### save File
    def fileSaveAs(self):
        fpath = self.setx.getProjectPath() + '/' + self.setx.getCurProjectName()
        fname = self.tabsList.tabText(self.tabsList.currentIndex())
        if fname.endswith('*'):
            fname = fname.replace('*', '')
        fn, _ = QFileDialog.getSaveFileName(self, "Save as...", fpath + '/' + fname,
                                            "Python files (*.py)")
        if not fn:
            return False

        lfn = fn.lower()
        if not lfn.endswith('.py'):
            fn += '.py'

        fn = os.path.basename(fn)
        self.tabsList.setTabToolTip(self.tabsList.currentIndex(), fn)
        self.setx.setCurProjectScript(fn)
        if not fn.endswith('*'):
            fn += '*'       # force file to be saved

        self.tabsList.setTabText(self.tabsList.currentIndex(), fn)
        self.fileSave()
        self.viewProjectFiles(fpath)

    def findFileDup(self, dfile, path=''):
        ret = ''
        fileslist = []
        if dfile:
            if dfile.endswith('*'):
                dfile = dfile.replace('*', '')
            # if path is null, use current directory
            for file in os.listdir(path):
                if dfile.lower() == file.lower():
                    ret = file
                    break
        return ret      # return dup filename -or- null string if no duplicates

    def deleteFile(self):
        tcount = self.tabsList.count()
        dialog = QFileDialog(self)
        dialog.setWindowTitle('Delete Project File')
        dialog.setNameFilter('(*.py)')
        dialog.setDirectory(self.setx.getProjectPath() + '/' + self.setx.getCurProjectName())
        dialog.setFileMode(QFileDialog.ExistingFile)
        sfile = self.projectFileViewer.currentItem().text(0)
        dialog.selectFile(sfile)
        if dialog.exec() == QDialog.Accepted:
            filename = dialog.selectedFiles()
            fpath = str(filename[0])
            fname = os.path.basename(fpath)
            for i in range(self.tabsList.count()):
                tt = self.tabsList.tabBar().tabText(i).lower()
                tt1 = tt
                if tt1.endswith('*'):
                    tt1 = tt1.replace('*', '')
                if tt1 == fname.lower():
                    self.tabsList.setCurrentIndex(i)
                    mpconfig.currentTabIndex = i
                    break
            if tt.endswith('*'):
                ret = QMessageBox.question(self, "Delete File: " + tt,
                                           "<h4><p>Editor text has been modified.</p>\n" \
                                           "<p>Do you still want to DELETE file?</p></h4>",
                                           QMessageBox.Yes | QMessageBox.No)
                if ret == QMessageBox.No:
                    return

                mpconfig.editorList[i].textHasChanged = False
                self.remove_tab(i)

            if os.path.exists(fpath):
                os.remove(fpath)
                self.viewProjectFiles(self.setx.getProjectPath() + '/' + self.setx.getCurProjectName())
                if tcount == 1:
                    mpconfig.editorList[0].clear()
                    mpconfig.editorList[0].textHasChanged = False
                    self.tabsList.tabBar().setTabText(0, 'untitled')
        return

    def renameFile(self):
        self.ren_dialog = QDialog()
        self.ren_edit = QLineEdit()
        self.new_fname = ''
        cur_path = self.setx.getProjectPath() + '/' + self.setx.getCurProjectName()
        old_fname = self.projectFileViewer.currentItem().text(0)
        if not old_fname:
            QMessageBox.warning(self, "Warning!",
                                       "<h4><p>No file Selected.</p>\n" \
                                       "<p>Left click project file window</p>\n"\
                                       "<p>to select file to rename.</p></h4>",
                                       QMessageBox.Close)
            return

        self.ren_dialog.setWindowTitle('Rename File')
        QBtn = QDialogButtonBox.Ok | QDialogButtonBox.Cancel

        buttonBox = QDialogButtonBox(QBtn)
        buttonBox.accepted.connect(self.rename_accept)
        buttonBox.rejected.connect(self.rename_reject)

        self.ren_dialog.layout = QVBoxLayout()
        self.ren_edit.setText(old_fname)
        self.ren_dialog.layout.addWidget(self.ren_edit)
        self.ren_dialog.layout.addWidget(buttonBox)
        self.ren_dialog.setLayout(self.ren_dialog.layout)
        self.ren_dialog.setFixedWidth(400)
        self.ren_dialog.exec()                 # launch the file name dialog
        if not self.new_fname:              # exit if dialog rejected
            return

        os.rename(cur_path + '/' + old_fname, cur_path + '/' + self.new_fname)
        self.viewProjectFiles(self.setx.getProjectPath() + '/' + self.setx.getCurProjectName())
        return

    def rename_accept(self):
        self.new_fname = self.ren_edit.text()
        self.ren_dialog.close()

    def rename_reject(self):
        self.new_fname = ''
        self.ren_dialog.close()

    def closeEvent(self, e):
        self.writeSettings()
        self.setx.setWinClose()
        if self.maybeSave():
            e.accept()
        else:
            e.ignore()

    ### ask to save if text has changed in current editor tab
    def maybeSave(self):
        if not mpconfig.editorList[mpconfig.currentTabIndex].textHasChanged:
            return True

        ret = QMessageBox.question(self, "Save File",
                                   "<h4><p>The text was modified.</p>\n" \
                                   "<p>Do you want to save changes?</p></h4>",
                                   QMessageBox.Yes | QMessageBox.Discard | QMessageBox.Cancel)
        if ret == QMessageBox.Yes:
            fn = self.tabsList.tabText(self.tabsList.currentIndex())
            if fn == 'untitled':
                self.fileSaveAs()
                return True
            else:
                self.fileSave()
                return True
        elif ret == QMessageBox.Cancel:
            return False
        return True

    def about(self):
        title = "About microPy"
        message = """
                    <span style='color: #3465a4; font-size: 20pt;font-weight: bold;'
                    >microPy 1.0</strong></span></p><h3>MicroPython Integrated Development Environment</h3>By J. Hoeppner@Abbykus 2022
                    <br>
                    <span style='color: #8a8a8a; font-size: 9pt;'>Forked from PyEdit2 by Axel Schneider @2017</strong></span></p>
                        """
        self.infobox(title, message)

    def settingsmenu(self):
        self.setx.openSettingsWindow()
        return

    def commentBlock(self):
        mpconfig.editorList[mpconfig.currentTabIndex].copy()
        clipboard = QApplication.clipboard();
        originalText = clipboard.text()
        mt1 = tab + tab + "'''" + "\n"
        mt2 = "\n" + tab + tab + "'''"
        mt = mt1 + originalText + mt2
        clipboard.setText(mt)
        mpconfig.editorList[mpconfig.currentTabIndex].paste()

    def uncommentBlock(self):
        mpconfig.editorList[mpconfig.currentTabIndex].copy()
        clipboard = QApplication.clipboard();
        originalText = clipboard.text()
        mt1 = tab + tab + "'''" + "\n"
        mt2 = "\n" + tab + tab + "'''"
        clipboard.setText(originalText.replace(mt1, "").replace(mt2, ""))
        mpconfig.editorList[mpconfig.currentTabIndex].paste()

        self.statusBar().showMessage("added block comment")

    def commentLine(self):
        newline = u"\u2029"
        comment = "#"
        list = []
        ot = mpconfig.editorList[mpconfig.currentTabIndex].textCursor().selectedText()
        if not mpconfig.editorList[mpconfig.currentTabIndex].textCursor().selectedText() == "":
            ### multiple lines selected
            theList = ot.splitlines()
            linecount = ot.count(newline)
            for i in range(linecount + 1):
                list.insert(i, comment + theList[i])
            mpconfig.editorList[mpconfig.currentTabIndex].textCursor().insertText(newline.join(list))
            self.setModified(True)
            self.statusBar().showMessage("added comment")
        else:
            ### one line selected
            mpconfig.editorList[mpconfig.currentTabIndex].moveCursor(QTextCursor.StartOfLine)
            mpconfig.editorList[mpconfig.currentTabIndex].textCursor().insertText("#")

    def uncommentLine(self):
        comment = "#"
        newline = u"\u2029"
        list = []
        ot = mpconfig.editorList[mpconfig.currentTabIndex].textCursor().selectedText()
        if not mpconfig.editorList[mpconfig.currentTabIndex].textCursor().selectedText() == "":
            ### multiple lines selected
            theList = ot.splitlines()
            linecount = ot.count(newline)
            for i in range(linecount + 1):
                list.insert(i, (theList[i]).replace(comment, "", 1))
            mpconfig.editorList[mpconfig.currentTabIndex].textCursor().insertText(newline.join(list))
            self.setModified(True)
            self.statusBar().showMessage("comment removed")
        else:
            ### one line selected
            mpconfig.editorList[mpconfig.currentTabIndex].moveCursor(QTextCursor.StartOfLine)
            mpconfig.editorList[mpconfig.currentTabIndex].moveCursor(QTextCursor.Right, QTextCursor.KeepAnchor)
            if mpconfig.editorList[mpconfig.currentTabIndex].textCursor().selectedText() == comment:
                mpconfig.editorList[mpconfig.currentTabIndex].textCursor().deleteChar()
                mpconfig.editorList[mpconfig.currentTabIndex].moveCursor(QTextCursor.StartOfLine)
            else:
                mpconfig.editorList[mpconfig.currentTabIndex].moveCursor(QTextCursor.StartOfLine)

    def goToLine(self, ft):
        mpconfig.editorList[mpconfig.currentTabIndex].moveCursor(int(self.gofield.currentText()),
                               QTextCursor.MoveAnchor)  ### not working

    def findText(self, backward=False):
        # search from the current cursor position
        word = self.findfield.text()
        if backward:
            n = mpconfig.editorList[mpconfig.currentTabIndex].find(word, QTextDocument.FindBackward)
        else:
            n = mpconfig.editorList[mpconfig.currentTabIndex].find(word)
        if n:
            mpconfig.editorList[mpconfig.currentTabIndex].centerCursor()    # force scroll if needed
        else:
            # Search term not found from the current cursor position
            # If reverse search, try searching backwards from the end of the text
            if backward:
                mpconfig.editorList[mpconfig.currentTabIndex].moveCursor(QTextCursor.End)
                if mpconfig.editorList[mpconfig.currentTabIndex].find(word, QTextDocument.FindBackward):
                    n = True
                    mpconfig.editorList[mpconfig.currentTabIndex].centerCursor()
            # Else try searching forward from the start of the text
            else:
                mpconfig.editorList[mpconfig.currentTabIndex].moveCursor(QTextCursor.Start)
                if mpconfig.editorList[mpconfig.currentTabIndex].find(word):
                    n = True
                    mpconfig.editorList[mpconfig.currentTabIndex].centerCursor()
        return n    # True if search term found, False otherwise

    def findTextChanged(self):
        cursor = mpconfig.editorList[mpconfig.currentTabIndex].textCursor()
        cursor.movePosition(QTextCursor.Start, QTextCursor.MoveAnchor)
        mpconfig.editorList[mpconfig.currentTabIndex].setTextCursor(cursor)
        self.findText()


    def findTextNext(self):
        cursor = mpconfig.editorList[mpconfig.currentTabIndex].textCursor()
        cursor.movePosition(QTextCursor.NextCharacter, QTextCursor.MoveAnchor)
        mpconfig.editorList[mpconfig.currentTabIndex].setTextCursor(cursor)
        return self.findText(False)

    def findTextPrev(self):
        return self.findText(True)     # search for text backwards

    def findBookmark(self, word):
        if mpconfig.editorList[mpconfig.currentTabIndex].find(word):
            linenumber = self.getLineNumber()  # mpconfig.editorList[mpconfig.currentTabIndex].textCursor().blockNumber() + 1
            self.statusBar().showMessage("found <b>'" + self.findfield.text() + "'</b> at Line: " + str(linenumber))

    def handleQuit(self):
        if self.maybeSave():
            # print("Goodbye ...")
            app.quit()

    def match_left(self, block, character, start, found):
        map = {'{': '}', '(': ')', '[': ']'}

        while block.isValid():
            data = block.userData()
            if data is not None:
                braces = data.braces
                N = len(braces)

                for k in range(start, N):
                    if braces[k].character == character:
                        found += 1

                    if braces[k].character == map[character]:
                        if not found:
                            return braces[k].position + block.position()
                        else:
                            found -= 1

                block = block.next()
                start = 0

    def match_right(self, block, character, start, found):
        map = {'}': '{', ')': '(', ']': '['}

        while block.isValid():
            data = block.userData()

            if data is not None:
                braces = data.braces

                if start is None:
                    start = len(braces)
                for k in range(start - 1, -1, -1):
                    if braces[k].character == character:
                        found += 1
                    if braces[k].character == map[character]:
                        if found == 0:
                            return braces[k].position + block.position()
                        else:
                            found -= 1
            block = block.previous()
            start = None

        cursor = mpconfig.editorList[mpconfig.currentTabIndex].textCursor()
        block = cursor.block()
        data = block.userData()
        previous, next = None, None

        if data is not None:
            position = cursor.position()
            block_position = cursor.block().position()
            braces = data.braces
            N = len(braces)

            for k in range(0, N):
                if braces[k].position == position - block_position or braces[
                        k].position == position - block_position - 1:
                    previous = braces[k].position + block_position
                    if braces[k].character in ['{', '(', '[']:
                        next = self.match_left(block,
                                               braces[k].character,
                                               k + 1, 0)
                    elif braces[k].character in ['}', ')', ']']:
                        next = self.match_right(block,
                                                braces[k].character,
                                                k, 0)
                    if next is None:
                        next = -1

        if next is not None and next > 0:
            if next == 0 and next >= 0:
                format = QTextCharFormat()

            cursor.setPosition(previous)
            cursor.movePosition(QTextCursor.NextCharacter,
                                QTextCursor.KeepAnchor)

            format.setBackground(QColor('white'))
            self.left_selected_bracket.format = format
            self.left_selected_bracket.cursor = cursor

            cursor.setPosition(next)
            cursor.movePosition(QTextCursor.NextCharacter,
                                QTextCursor.KeepAnchor)

            format.setBackground(QColor('white'))
            self.right_selected_bracket.format = format
            self.right_selected_bracket.cursor = cursor

    def paintEvent(self, event):
        if self.tabsList.count() > 0:
            highlighted_line = QTextEdit.ExtraSelection()
            highlighted_line.format.setBackground(textline_highlight_color)
            highlighted_line.format.setProperty(QTextFormat
                                                .FullWidthSelection,
                                                QVariant(True))
            highlighted_line.cursor = mpconfig.editorList[mpconfig.currentTabIndex].textCursor()
            highlighted_line.cursor.clearSelection()
            mpconfig.editorList[mpconfig.currentTabIndex].setExtraSelections([highlighted_line,
                                            self.left_selected_bracket,
                                            self.right_selected_bracket])

    def document(self):
        return mpconfig.editorList[mpconfig.currentTabIndex].document

    # def isModified(self):
    #     return mpconfig.editorList[mpconfig.currentTabIndex].textHasChanged

    def setModified(self, modified):
        mpconfig.editorList[mpconfig.currentTabIndex].textHasChanged = modified

    def setLineWrapMode(self, mode):
        mpconfig.editorList[mpconfig.currentTabIndex].setLineWrapMode(mode)

    def clear(self):
        mpconfig.editorList[mpconfig.currentTabIndex].clear()

    # def setPlainText(self, *args, **kwargs):
    #     mpconfig.editorList[mpconfig.currentTabIndex].setPlainText(*args, **kwargs)

    def setDocumentTitle(self, *args, **kwargs):
        mpconfig.editorList[mpconfig.currentTabIndex].setDocumentTitle(*args, **kwargs)

    def replaceAll(self):
        if not mpconfig.editorList[mpconfig.currentTabIndex].document().toPlainText() == "":
            if not self.findfield.text() == "":
                self.statusBar().showMessage("Replacing all")
                # Position cursor at the beginning of text
                cursor = mpconfig.editorList[mpconfig.currentTabIndex].textCursor()
                cursor.movePosition(QTextCursor.Start, QTextCursor.MoveAnchor)
                mpconfig.editorList[mpconfig.currentTabIndex].setTextCursor(cursor)
                self.findText()
                while self.replaceOne():
                    pass

                # oldtext = mpconfig.editorList[mpconfig.currentTabIndex].document().toPlainText()
                # newtext = oldtext.replace(self.findfield.text(), self.replacefield.text())
                # mpconfig.editorList[mpconfig.currentTabIndex].setPlainText(newtext)
                self.setModified(True)
            else:
                self.statusBar().showMessage("nothing to replace")
        else:
            self.statusBar().showMessage("no text")

    def replaceOne(self):
        # Check if search params are valid
        if not mpconfig.editorList[mpconfig.currentTabIndex].document().toPlainText() == "":
            if not self.findfield.text() == "":
                self.statusBar().showMessage("Replacing Text")
                # use cut & paste so the 'undo' history persists
                clipboard = QApplication.clipboard()
                mpconfig.editorList[mpconfig.currentTabIndex].cut()
                clipboard.setText(self.replacefield.text())
                mpconfig.editorList[mpconfig.currentTabIndex].paste()
                self.setModified(True)
                return self.findTextNext()
            else:
                self.statusBar().showMessage("No text to replace.")
        else:
            self.statusBar().showMessage("No text in Editor")

        return False

    def setCurrentFile(self, fileName, modified):
        # self.filename = fileName
        ttip = 'untitled'
        fname = ttip

        if fileName:
            fname = self.strippedName(fileName)
            if modified:
                fname += "*"
            ttip = fname
            # if len(fname) > 11:
            #     fname = fname[:8] + "..."

        self.tabsList.setTabText(self.tabsList.currentIndex(), fname)
        self.tabsList.tabBar().setTabToolTip(self.tabsList.currentIndex(), ttip)

        _files = self.setx.getRecentFileList()
        if _files:
            try:
                _files.remove(fileName)
            except ValueError:
                pass

            if not fileName == "/tmp/tmp.py":
                _files.insert(0, fileName)

            maxf = int(self.setx.getMaxRecentFiles())
            del _files[maxf:]

            self.setx.setRecentFileList(_files)

        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, pyEditor):
                widget.updateRecentFileActions()

    def updateRecentFileActions(self):
        mytext = ""
        _files = self.setx.getRecentFileList()
        if not _files:
            numRecentFiles = 0
        else:
            numRecentFiles = min(len(_files), int(self.setx.getMaxRecentFiles()))

        for i in range(numRecentFiles):
            text = "&%d %s" % (i + 1, self.strippedName(_files[i]))
            self.recentFileActs[i].setText(text)
            self.recentFileActs[i].setData(_files[i])
            self.recentFileActs[i].setVisible(True)
            self.recentFileActs[i].setIcon(QIcon.fromTheme("gnome-mime-text-x-python"))

        self.separatorAct.setVisible((numRecentFiles > 0))

    def strippedName(self, fullFileName):
        return QFileInfo(fullFileName).fileName()

    def clearRecentFiles(self):
        #self.settings.setValue('recentFileList', [])
        self.updateRecentFileActions()

    def readSettings(self):
        pos = self.setx.getWinPos()
        if pos == '':
            pos = QPoint(200, 200)      # use this as default screen position
            self.setx.setWinPos(pos)
        self.move(pos)
        size = self.setx.getWinSize()
        if size == '':
            size = QSize(400, 400)
            self.setx.setWinSize(size)
        self.resize(size)

    def writeSettings(self):
        self.setx.setWinPos(self.pos())
        self.setx.setWinSize(self.size())

    def msgbox(self, title, message):
        QMessageBox.warning(self, title, message)

    def infobox(self, title, message):
        QMessageBox(QMessageBox.Information, title, message, QMessageBox.NoButton, self,
                    Qt.Dialog | Qt.NoDropShadowWindowHint).show()

    def insertTemplate(self):
        line = int(self.getLineNumber())
        path = self.setx.getAppPath() + "/templates/" + self.templates.itemText(self.templates.currentIndex()) + ".txt"
        if path:
            inFile = QFile(path)
            if inFile.open(QFile.ReadOnly | QFile.Text):
                text = inFile.readAll()
                mpconfig.editorList[mpconfig.currentTabIndex].setFocus()
                try:  ### python 3
                    mpconfig.editorList[mpconfig.currentTabIndex].textCursor().insertText(str(text, encoding='utf8'))
                except TypeError:  ### python 2
                    mpconfig.editorList[mpconfig.currentTabIndex].textCursor().insertText(str(text))
                self.setModified(True)
                self.statusBar().showMessage(
                    "'" + self.templates.itemText(self.templates.currentIndex()) + "' inserted")
                inFile.close()
                text = ""
                self.selectLine(line)
            else:
                self.statusBar().showMessage("error loadind Template")

    def selectLine(self, line):
        linecursor = QTextCursor(mpconfig.editorList[mpconfig.currentTabIndex].document().findBlockByLineNumber(line - 1))
        mpconfig.editorList[mpconfig.currentTabIndex].moveCursor(QTextCursor.End)
        mpconfig.editorList[mpconfig.currentTabIndex].setTextCursor(linecursor)

    def createTrayIcon(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            QMessageBox.critical(None, "Systray", "System tray not detected on this system.")
        else:
            self.trayIcon = QSystemTrayIcon(self)
            self.trayIcon.setIcon(QIcon.fromTheme("applications-python"))
            self.trayIconMenu = QMenu(self)
            self.trayIconMenu.addAction(
                QAction(QIcon.fromTheme("applications-python"), "about microPy", self, triggered=self.about))
            self.trayIconMenu.addSeparator()
            self.trayIconMenu.addAction(
                QAction(QIcon.fromTheme("application-exit"), "Exit", self, triggered=self.handleQuit))
            self.trayIcon.setContextMenu(self.trayIconMenu)

    def handlePrint(self):
        if mpconfig.editorList[mpconfig.currentTabIndex].toPlainText() == "":
            self.statusBar().showMessage("No text to Print!")
        else:
            dialog = QPrintDialog()
            if dialog.exec_() == QDialog.Accepted:
                self.handlePaintRequest(dialog.printer())
                self.statusBar().showMessage("Document printed")

    def handlePrintPreview(self):
        if mpconfig.editorList[mpconfig.currentTabIndex].toPlainText() == "":
            self.statusBar().showMessage("No text to Preview!")
        else:
            dialog = QPrintPreviewDialog()
            dialog.setFixedSize(900, 650)
            dialog.paintRequested.connect(self.handlePaintRequest)
            dialog.exec_()
            self.statusBar().showMessage("Print Preview closed")

    def handlePaintRequest(self, printer):
        ptxt = self.tabsList.tabText(self.tabsList.currentIndex())
        if ptxt.endswith('*'):
            ptxt = ptxt.replace('*', '')
        printer.setDocName(ptxt)
        document = mpconfig.editorList[mpconfig.currentTabIndex].document()
        document.print_(printer)

def stylesheet2(self):
    return """
    QPlainTextEdit
    {
    font-family: Monospace;
    font-size: 15px;
    background: #2B2B2B;
    color: #d1d1d1;
    border: 0px solid #1EAE3D;
    }
    QTextEdit
    {
    background: #2B2B2B;
    color: #22f750;
    font-family: Monospace;
    font-size: 8pt;
    padding-left: 6px;
    border: 0px solid #1EAE3D;
    }
    QStatusBar
    {
    font-family: Monospace;
    color: #dbdbdb;
    font-size: 9pt;
    }
    QLabel
    {
    font-family: Monospace;
    color: #22f750;
    font-size: 9pt;
    }
    QLineEdit
    {
    font-family: Helvetica;
    font-size: 8pt;
    border: 1px solid #84aff4;
    border-radius: 4px;
    }
    QPushButton
    {
    font-family: Helvetica;
    font-size: 8pt;
    }
    QComboBox
    {
    font-family: Helvetica;
    font-size: 8pt;
    border: 1px solid #84aff4;
    border-radius: 4px;
    }
    QMenuBar
    {
    font-family: Helvetica;
    font-size: 8pt;
    }
    QMenu
    {
    font-family: Helvetica;
    font-size: 8pt;
    }
    QToolBar
    {
    background: transparent;
    }
    QTreeWidget
    {
    background: #2B2B2B;
    color: #d1d1d1;
    font-family: Monospace;
    font-size: 8pt;
    padding-left: 8px;
    border: 2px solid #84aff4;
    border-radius: 4px;
    }
    QTabWidget
    {
    font-family: Monospace;
    font-size: 15px;
    background: #2B2B2B;
    color: #d1d1d1;
    border: 0px solid #1EAE3D;
    }
    """

if __name__ == '__main__':
    app = QApplication(argv)
    translator = QTranslator(app)
    locale = QLocale.system().name()
    # print('locale = ' + locale)
    path = QLibraryInfo.location(QLibraryInfo.TranslationsPath)
    translator.load('qt_%s' % locale, path)
    app.installTranslator(translator)
    win = pyEditor()
    win.setWindowTitle("MicroPy IDE" + "[*]")
    win.show()
    # win.resetTargetDevice()
    win.viewTargetFiles()
    if len(argv) > 1:
        print('argv= ' + argv[1])
        win.openFileOnStart(argv[1])

    sys.exit(app.exec_())

