# !/usr/bin/python3
# -- coding: utf-8 --
# microPy.py - microPython IDE for microcontrollers.
#
from __future__ import print_function

from PyQt5.QtWidgets import (QPlainTextEdit, QWidget, QVBoxLayout, QApplication, QFileDialog, QMessageBox, QLabel,
                             QCompleter, QHBoxLayout, QTextEdit, QToolBar, QComboBox, QAction, QLineEdit, QDialog,
                             QPushButton, QToolButton, QMenu, QMainWindow, QInputDialog, QColorDialog, QStatusBar,
                             QSystemTrayIcon, QSplitter, QTreeWidget, QTreeWidgetItem, QTabWidget, QDialogButtonBox,
                             QScrollBar, QSpacerItem, QSizePolicy, QLayout, QStyle, QFrame, QHeaderView)
from PyQt5.QtGui import (QIcon, QPainter, QTextFormat, QColor, QTextCursor, QKeySequence, QClipboard, QTextDocument,
                         QPixmap, QStandardItemModel, QStandardItem, QCursor, QPalette)
from PyQt5.QtCore import (Qt, QVariant, QRect, QDir, QFile, QFileInfo, QTextStream, QSettings, QTranslator, QLocale,
                          QProcess, QPoint, QSize, QCoreApplication, QStringListModel, QLibraryInfo, QIODevice, QEvent,
                          pyqtSlot, QModelIndex, QVersionNumber)

from PyQt5.QtPrintSupport import QPrintDialog, QPrinter
#from PyQt5.QtSerialPort import QSerialPort

from sys import argv
import inspect

from syntax_py import *
import os
import signal
import sys
import re
import time
import codecs
import mpconfig
import ntpath
import settings
import pyboard
import files

# GLOBAL CONSTANTS
lineBarColor = QColor("#84aff4")
lineHighlightColor = QColor("#232323")
border_outer_color = QColor("#ef4343")
tab = chr(9)
eof = "\n"
iconsize = QSize(16, 16)


#####################################################################
# pyTextEditor widget - the python script editor
#####################################################################
class PyTextEdit(QPlainTextEdit):
    def __init__(self, parent=None):
        super(PyTextEdit, self).__init__(parent)

        self.textHasChanged = False
        self.installEventFilter(self)
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
        #                print("\n".join(self.wordList))
        #                self.words.append("\n".join(self.wordList))

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
            painter.fillRect(event.rect(), lineBarColor)
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

        ### Critical section lock/release
        #self.LOCK = threading.Lock()

        ### Serial data buffer
        self.serialByteArray = b''
        self.serialDataRcvd = False

        self.targetScript = b''

        ### Initialize settings
        self.setx = settings.Settings()

        self.shellText = QTextEdit()
        self.shellText.setObjectName("shellText")
        _device = self.setx.getSerialPort()
        _baud = self.setx.getBaudRate()
        self.mpBoard = pyboard.Pyboard(self.shellText, _device, _baud)
        self.mpCmds = files.Files(self.mpBoard)

        self.TargetFileList = []

        # set up the non-persistent system settings
        print('os name= ' + self.setx.getOS())     # find name of os, 'linux', 'windows', etc
        print('project path= ' + self.setx.getCurProjectPath())
        print('project name= ' + self.setx.getCurProjectName())
        print('app path= ' + self.setx.getAppPath())

        self.extProc = QProcess()       # used to start external programs
        self.tabsList = QTabWidget()
        self.tabsList.setTabsClosable(True)
        self.tabsList.setTabVisible(0, True)
        self.tabsList.currentChanged.connect(self.change_text_editor)
        self.tabsList.tabCloseRequested.connect(self.remove_tab)

        self.cursor = QTextCursor()
        self.wordList = []
        self.statusBar().showMessage(self.setx.getAppPath())
        self.lineLabel = QLabel("line")
        self.statusBar().addPermanentWidget(self.lineLabel)
        self.windowList = []
        self.recentFileActs = []

        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowIcon(QIcon.fromTheme("applications-python"))

        # # create the QSerialPort widget
        # self.serialport = QSerialPort(self)
        # self.serialport.setPortName(self.setx.getSerialPort())

        # Create the project files viewer derived from QTreeWidget
        self.projectFileViewer = fileViewer()
        self.projectFileViewer.setStyleSheet(stylesheet2(self))
        proj_name = self.setx.getCurProjectName()
        if self.isProjectValid(proj_name):
            proj_name = 'Project: ' + proj_name
        else:
            proj_name = 'Project: None'
            #self.settings.setValue('CUR_PROJECT_NAME', '')
        self.projectFileViewer.setHeaderItem(QTreeWidgetItem([proj_name]))
        self.projectFileViewer.setColumnCount(1)
        self.projectFileViewer.itemDoubleClicked.connect(self.projectFileViewerDblClicked)
        self.projectFileViewer.setContextMenuPolicy(Qt.CustomContextMenu)
        self.projectFileViewer.customContextMenuRequested.connect(self.projectViewerContextMenu)

        # Populate the Project file viewer
        self.showDirectoryTree(self.setx.getCurProjectPath())
        self.projectFileViewer.expandAll()

        # Create the Target file viewer
        self.targetFileViewer = fileViewer()
        self.targetFileViewer.setStyleSheet(stylesheet2(self))
        self.targetFileViewer.setHeaderItem(QTreeWidgetItem([" Target Files"]))
        self.targetFileViewer.setColumnCount(1)

        targ1 = QTreeWidgetItem([self.setx.getSerialPort()])
        self.targetFileViewer.addTopLevelItem(targ1)
        self.targetFileViewer.expandAll()
        self.targetFileViewer.itemDoubleClicked.connect(self.targetFileViewerDblClicked)
        self.targetFileViewer.setContextMenuPolicy(Qt.CustomContextMenu)
        self.targetFileViewer.customContextMenuRequested.connect(self.targetViewerContextMenu)

        # Editor Widget ...
        self.extra_selections = []
        self.mainText = "#!/usr/bin/python3\n# -*- coding: utf-8 -*-\n"
        self.fname = ""
        self.filename = ""
        self.mypython = "3"

        # shellText widget - interacts with the target over serial
        # self.shellText = QTextEdit()
        # self.shellText.setObjectName("shellText")
        self.shellText.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.shellText.setReadOnly(False)
        self.shellText.installEventFilter(self)

        # statusbar
        self.statusBar()
        self.statusBar().setStyleSheet(stylesheet2(self))
        self.statusBar().showMessage('Welcome')

        ### begin toolbar
        tb = self.addToolBar("File")
        tb.setStyleSheet(stylesheet2(self))
        tb.setContextMenuPolicy(Qt.PreventContextMenu)
        tb.setIconSize(QSize(iconsize))
        tb.setMovable(True)
        tb.setAllowedAreas(Qt.AllToolBarAreas)
        tb.setFloatable(True)

        ### Create action button objects used by menus and toolbars ###
        self.newProjectAct = QAction("&Create New Project", self, shortcut=QKeySequence.New, triggered=self.createNewProject)
        self.newProjectAct.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/new_project"))

        self.openProjectAct = QAction("&Open Existing Project", self, shortcut=QKeySequence.New, triggered=self.openExistingProject)
        self.openProjectAct.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/open_project"))

        self.closeProjectAct = QAction("&Close Current Project", self, shortcut=QKeySequence.New, triggered=self.closeCurrentProject)
        self.closeProjectAct.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/close_project"))

        self.newFileAct = QAction("&New File", self, shortcut=QKeySequence.New, triggered=self.newFile)
        self.newFileAct.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/new24"))
        # if len(self.settings.value('CUR_PROJECT_NAME', '')) == 0:
        #     self.newFileAct.setEnabled(False)

        self.openFileAct = QAction("&Open File", self, shortcut=QKeySequence.Open,  triggered=self.openFile)
        self.openFileAct.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/open24"))

        self.saveFileAct = QAction("&Save File", self, shortcut=QKeySequence.Save, triggered=self.fileSave)
        self.saveFileAct.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/floppy24"))

        self.saveFileAsAct = QAction("&Save File as...", self, shortcut=QKeySequence.SaveAs, triggered=self.fileSaveAs)
        self.saveFileAsAct.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/floppy25"))

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

        self.printPreviewAct = QAction("Print Preview (Ctl+Shf+P)", self, shortcut="Ctrl+Shift+P", triggered=self.handlePrintPreview)
        self.printPreviewAct.setIcon(QIcon.fromTheme("document-print-preview"))

        self.printAct = QAction("Print", self, shortcut=QKeySequence.Print, triggered=self.handlePrint)
        self.printAct.setIcon(QIcon.fromTheme("document-print"))

        self.exitAct = QAction("Exit", self, shortcut=QKeySequence.Quit, triggered=self.handleQuit)
        self.exitAct.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/quit"))

        self.indentAct = QAction(QIcon.fromTheme(self.setx.getAppPath() + "/icons/indent"), "Indent more", self,
                                 triggered=self.indentLine, shortcut="F8")

        self.indentLessAct = QAction(QIcon.fromTheme(self.setx.getAppPath() + "/icons/unindent"), "Indent less", self,
                                     triggered=self.unindentLine, shortcut="F9")

        self.bookAct = QAction("Add Bookmark", self, triggered=self.addBookmark)
        self.bookAct.setIcon(QIcon.fromTheme("previous"))

        self.bookrefresh = QAction("Update Bookmarks", self, triggered=self.findBookmarks)
        self.bookrefresh.setIcon(QIcon.fromTheme("view-refresh"))

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
        self.newFolderAct.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/folder"))

        self.delFolderAct = QAction("&Remove Target Folder", self, shortcut='', triggered=self.rmTargetFolder)
        self.delFolderAct.setIcon(QIcon.fromTheme(self.setx.getAppPath() + "/icons/folder_del"))

        ### file buttons
        tb.addAction(self.newProjectAct)
        tb.addAction(self.openProjectAct)
        tb.addAction(self.closeProjectAct)
        tb.addSeparator()
        tb.addSeparator()
        tb.addAction(self.newFileAct)
        tb.addAction(self.openFileAct)
        tb.addAction(self.saveFileAct)
        tb.addAction(self.saveFileAsAct)
        tb.addSeparator()
        tb.addSeparator()

        ### comment buttons
        tb.addSeparator()
        tb.addAction(self.commentAct)
        tb.addAction(self.uncommentAct)
        tb.addAction(self.commentBlockAct)
        tb.addAction(self.uncommentBlockAct)

        ### color chooser
        tb.addSeparator()
        tb.addAction(QIcon.fromTheme(self.setx.getAppPath() + "/icons/color1"), "insert QColor", self.insertColor)
        tb.addSeparator()
        tb.addAction(QIcon.fromTheme("preferences-color"), "Insert Color Hex Value", self.changeColor)

        ### Insert templates
        tb.addSeparator()
        self.templates = QComboBox()
        self.templates.setStyleSheet(stylesheet2(self))
        self.templates.setFixedWidth(120)
        self.templates.setToolTip("insert template")
        self.templates.activated[str].connect(self.insertTemplate)
        tb.addWidget(self.templates)

        ### path python buttons
        tb.addSeparator()
        # tb.addAction(QIcon.fromTheme("edit-clear"), "clear Shell Terminal", self.clearLabel)
        tb.addSeparator()

        ### print preview
        tb.addAction(self.printPreviewAct)

        ### print
        tb.addAction(self.printAct)

        ### Help (Zeal) button
        tb.addSeparator()
        tb.addAction(QIcon.fromTheme(self.setx.getAppPath() + "/icons/zeal"), "&Zeal Developer Help", self.showZeal)
        tb.addSeparator()

        ### about buttons
        tb.addAction(QIcon.fromTheme(self.setx.getAppPath() + "/icons/info2"), "&About microPy", self.about)
        tb.addSeparator()
        tb.addSeparator()
        tb.addSeparator()
        tb.addSeparator()

        ### exit button
        tb.addAction(self.exitAct)

        ### end toolbar

        ### find / replace toolbar
        self.addToolBarBreak()
        tbf = self.addToolBar("Find")
        tbf.setStyleSheet(stylesheet2(self))
        tbf.setContextMenuPolicy(Qt.PreventContextMenu)
        tbf.setIconSize(QSize(iconsize))
        self.findfield = QLineEdit()
        self.findfield.setStyleSheet(stylesheet2(self))
        self.findfield.addAction(QIcon.fromTheme("edit-find"), QLineEdit.LeadingPosition)
        self.findfield.setClearButtonEnabled(True)
        self.findfield.setFixedWidth(150)
        self.findfield.setPlaceholderText("find")
        self.findfield.setToolTip("press RETURN to find")
        self.findfield.setText("")
        ft = self.findfield.text()
        self.findfield.returnPressed.connect(self.findText)
        tbf.addWidget(self.findfield)
        self.replacefield = QLineEdit()
        self.replacefield.setStyleSheet(stylesheet2(self))
        self.replacefield.addAction(QIcon.fromTheme("edit-find-and-replace"), QLineEdit.LeadingPosition)
        self.replacefield.setClearButtonEnabled(True)
        self.replacefield.setFixedWidth(150)
        self.replacefield.setPlaceholderText("replace with")
        self.replacefield.setToolTip("press RETURN to replace the first")
        self.replacefield.returnPressed.connect(self.replaceOne)
        tbf.addSeparator()
        tbf.addWidget(self.replacefield)
        tbf.addSeparator()

        self.repAllAct = QPushButton("Replace All")
        self.repAllAct.setFixedWidth(100)
        self.repAllAct.setStyleSheet(stylesheet2(self))
        self.repAllAct.setIcon(QIcon.fromTheme("gtk-find-and-replace"))
        self.repAllAct.clicked.connect(self.replaceAll)
        tbf.addWidget(self.repAllAct)
        tbf.addSeparator()
        tbf.addAction(self.indentAct)
        tbf.addAction(self.indentLessAct)
        tbf.addSeparator()
        self.gotofield = QLineEdit()
        self.gotofield.setStyleSheet(stylesheet2(self))
        self.gotofield.addAction(QIcon.fromTheme("next"), QLineEdit.LeadingPosition)
        self.gotofield.setClearButtonEnabled(True)
        self.gotofield.setFixedWidth(120)
        self.gotofield.setPlaceholderText("go to line")
        self.gotofield.setToolTip("press RETURN to go to line")
        self.gotofield.returnPressed.connect(self.gotoLine)
        tbf.addWidget(self.gotofield)

        tbf.addSeparator()
        self.bookmarks = QComboBox()
        self.bookmarks.setStyleSheet(stylesheet2(self))
        self.bookmarks.setFixedWidth(280)
        self.bookmarks.setToolTip("go to bookmark")
        self.bookmarks.activated[str].connect(self.gotoBookmark)
        tbf.addWidget(self.bookmarks)
        tbf.addAction(self.bookAct)

        tbf.addSeparator()
        tbf.addAction(self.bookrefresh)
        tbf.addAction(QAction(QIcon.fromTheme("document-properties"), "Check && Reindent Text", self,
                              triggered=self.reindentText))

        # 'File' dropdown menu
        bar = self.menuBar()
        bar.setStyleSheet(stylesheet2(self))
        self.filemenu = bar.addMenu("File")
        self.filemenu.setStyleSheet(stylesheet2(self))
        self.separatorAct = self.filemenu.addSeparator()
        self.filemenu.addSeparator()
        self.filemenu.addAction(self.newProjectAct)
        self.filemenu.addAction(self.openProjectAct)
        self.filemenu.addAction(self.closeProjectAct)
        self.filemenu.addSeparator()

        #self.filemenu.insertSeparator(self.separatorAct)
        self.filemenu.addAction(self.newFileAct)
        self.filemenu.addAction(self.openFileAct)
        self.filemenu.addAction(self.saveFileAct)
        self.filemenu.addAction(self.saveFileAsAct)
        self.filemenu.addSeparator()
        # for i in range(self.rt_settings['max_recent_files']):
        #    self.filemenu.addAction(self.recentFileActs[i])
        self.updateRecentFileActions()
        self.filemenu.addSeparator()
        self.filemenu.addAction(self.clearRecentAct)
        self.filemenu.addAction(self.exitAct)

        ### Top level menu bar 'Edit'
        editmenu = bar.addMenu("Edit")
        editmenu.setStyleSheet(stylesheet2(self))
        editmenu.addAction(
            QAction(QIcon.fromTheme('edit-undo'), "Undo", self, triggered=PyTextEdit.undo, shortcut="Ctrl+u"))
        editmenu.addAction(
            QAction(QIcon.fromTheme('edit-redo'), "Redo", self, triggered=PyTextEdit.redo, shortcut="Shift+Ctrl+u"))
        editmenu.addSeparator()
        editmenu.addAction(
            QAction(QIcon.fromTheme('edit-copy'), "Copy", self, triggered=PyTextEdit.copy, shortcut="Ctrl+c"))
        editmenu.addAction(
            QAction(QIcon.fromTheme('edit-cut'), "Cut", self, triggered=PyTextEdit.cut, shortcut="Ctrl+x"))
        editmenu.addAction(
            QAction(QIcon.fromTheme('edit-paste'), "Paste", self, triggered=PyTextEdit.paste, shortcut="Ctrl+v"))
        editmenu.addAction(
            QAction(QIcon.fromTheme('edit-delete'), "Delete", self, triggered=PyTextEdit.cut, shortcut="Del"))
        editmenu.addSeparator()
        editmenu.addAction(
            QAction(QIcon.fromTheme('edit-select-all'), "Select All", self, triggered=PyTextEdit.selectAll,
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

        ### Top level menu bar 'Help'
        self.helpmenu = bar.addMenu("Help")
        self.helpmenu.setStyleSheet(stylesheet2(self))
        self.separatorAct = self.helpmenu.addSeparator()

        ### Zeal button
        self.helpmenu.addAction(self.zealAct)
        self.helpmenu.addSeparator()

        ### shell text widget
        self.shellText.setMinimumHeight(28)
        self.shellText.setStyleSheet(stylesheet2(self))

        ### Micropython toolbar
        mptb = self.addToolBar("Run")
        mptb.setStyleSheet(stylesheet2(self))
        mptb.setContextMenuPolicy(Qt.PreventContextMenu)
        mptb.setIconSize(QSize(iconsize))
        mptb.setMovable(False)
        mptb.setAllowedAreas(Qt.AllToolBarAreas)
        mptb.setFloatable(False)

        ### Serial Port line editor widget
        self.comportfield = QLineEdit()
        self.comportfield.setStyleSheet(stylesheet2(self))
        self.comportfield.addAction(QIcon.fromTheme(self.setx.getAppPath() + "/icons/connect"), QLineEdit.LeadingPosition)
        self.comportfield.setClearButtonEnabled(True)
        self.comportfield.setFixedWidth(150)
        if self.setx.getSerialPort():
            self.comportfield.setText(self.setx.getSerialPort())
        else:
            self.comportfield.setPlaceholderText("serial com port")
        self.comportfield.setToolTip("Serial Port Name")
        self.comportfield.returnPressed.connect(self.saveComPort)
        mptb.addWidget(self.comportfield)

        ### Baudrate dropdown editbox
        self.baudrates = QComboBox()
        self.baudrates.setStyleSheet(stylesheet2(self))
        self.baudrates.setFixedWidth(90)
        self.baudrates.setToolTip("Serial Baudrate")
        self.baudrates.activated[str].connect(self.setBaudrate)
        baud_list = ["9600", "19200", "38400", "57600", "115200", "250000"]
        self.baudrates.addItems(baud_list)
        mptb.addWidget(self.baudrates)

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
        mptb.addSeparator()
        mptb.addAction(QIcon.fromTheme("edit-clear"), "clear Shell Terminal", self.clearLabel)

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
        #self.create_new_tab('tab2')
        self.top_right_layout.addWidget(self.tabsList, 1)
        self.top_right_layout.setContentsMargins(0, 0, 0, 0) #6, 6, 6, 6)
        self.top_right_widget = QWidget()
        self.setCentralWidget(self.tabsList)
        self.top_right_widget.setLayout(self.top_right_layout)
        self.top_right_widget.setStyleSheet("background-color: rgb(43, 43, 43);\n"
                                            "color: rgb(160, 160, 160);\n"
                                            "border-style: solid;\n"
                                            "border-color: rgb(132, 175, 244);\n" 
                                            "border-width: 0px;\n"
                                            "border-radius: 4px;")

        #*** BOT RIGHT Horiz Layout
        self.bot_right_layout = QHBoxLayout()
        self.bot_right_layout.setContentsMargins(2, 2, 4, 2)
        self.bot_right_layout.addWidget(self.shellText)
        self.bot_right_widget = QWidget()
        self.bot_right_widget.setLayout(self.bot_right_layout)
        self.bot_right_widget.setStyleSheet("background-color: rgb(43, 43, 43);\n"
                                            "color: rgb(160, 160, 160);\n"  
                                            "border-style: solid;\n"
                                            "border-color: rgb(132, 175, 244);;\n"  
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
        if len(baud) > 0:
            indx = self.baudrates.findText(baud)
            self.baudrates.setCurrentIndex(indx)
            # self.serialport.setBaudRate(int(baud))
            # if self.serialport.open(QIODevice.ReadWrite):
            #     self.serialport.setFlowControl(QSerialPort.HardwareControl)
            #     self.serialport.readyRead.connect(self.serial_read_bytes)
            #     self.shellText.clear()
            #     self.shellText.setText('Serial port ' + self.setx.getSerialPort() + ' is connected to Target.')
            # else:
            #     self.shellText.clear()
            #     self.shellText.setText('Unable to open Serial port ' + self.setx.getSerialPort())


    def getFilesInDir(self, dirpath):
        files = []
        for file in os.listdir(dirpath):
            fpath = dirpath + '/' + file
            if os.path.isfile(fpath):
                files.append(file)
        return files


    def isProjectValid(self, proj_name):
        if len(proj_name) == 0:
            return False
        path = self.setx.getCurProjectPath()
        return os.path.isdir(path)

    def getDirectory(self):
        gdir_dialog = QFileDialog(self, 'Select Directory', self.setx.getAppPath(), None)
        gdir_dialog.setFileMode(QFileDialog.DirectoryOnly)
        #dialog.setSidebarUrls([QtCore.QUrl.fromLocalFile(place)])
        if gdir_dialog.exec_() == QDialog.Accepted:
            new_dir = gdir_dialog.selectedFiles()[0]
            self.showDirectoryTree(new_dir)

    # Show folders & files in the 'path' directory to the projectFileViewer tree widget
    def showDirectoryTree(self, curpath):
        self.projectFileViewer.clear()
        if len(self.setx.getCurProjectName()) == 0:
            return

        self.load_project_tree(curpath, self.projectFileViewer)
        self.projectFileViewer.setItemsExpandable(True)

        proj_name = 'Project: ' + self.setx.getCurProjectName()
        self.projectFileViewer.setHeaderItem(QTreeWidgetItem([proj_name]))

    # recursive function to display directory contnts in projectFileViewer
    def load_project_tree(self, startpath, tree):
        for element in os.listdir(startpath):
            path_info = os.path.join(startpath, element)
            parent_itm = QTreeWidgetItem(tree, [os.path.basename(element)])
            parent_itm.setData(0, Qt.UserRole, path_info)
            if os.path.isdir(path_info):
                self.load_project_tree(path_info, parent_itm)
                parent_itm.setIcon(0, QIcon(self.setx.getAppPath() + '/icons/folder_closed'))
            else:
                parent_itm.setIcon(0, QIcon(self.setx.getAppPath() + '/icons/file'))

        # self.projectFileViewer.clear()
        # dirfiles = os.listdir(curpath)
        # fullpaths = map(lambda name: os.path.join(curpath, name), dirfiles)
        # head, tail = ntpath.split(curpath)
        # tldir = tail or ntpath.basename(head)
        # #print('tldir=' + tldir)
        # l1 = QTreeWidgetItem([tldir])
        # l1.setIcon(0, QIcon(self.setx.getAppPath() + "/icons/folder_open"))
        #
        # dirs = []
        # files = []
        #
        # for file in fullpaths:
        #     if os.path.isdir(file):
        #         head, tail = ntpath.split(file)
        #         file = tail or ntpath.basename(head)
        #         dirs.append(file)
        #     elif os.path.isfile(file):
        #         head, tail = ntpath.split(file)
        #         file = tail or ntpath.basename(head)
        #         files.append(file)
        #
        # # display directories on top
        # for ndir in dirs:
        #     l1_child = QTreeWidgetItem(['/' + ndir])
        #     icd = QIcon(self.setx.getAppPath() + "/icons/folder_closed")
        #     l1_child.setIcon(0, icd)
        #     l1.addChild(l1_child)
        #
        # # display files on bottom
        # for nfile in files:
        #     l1_child = QTreeWidgetItem([nfile])
        #     icf = QIcon(self.setx.getAppPath() + "/icons/file")
        #     l1_child.setIcon(0, icf)
        #     l1.addChild(l1_child)
        #
        # self.projectFileViewer.addTopLevelItem(l1)
        # self.projectFileViewer.expand(0)
        # self.projectFileViewer.expandAll()
        # self.projectFileViewer.setItemsExpandable(False)

    def createNewProject(self):
        self.new_proj = 'untitled'
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

        # new project accepted?
        if self.new_proj == 'rejected':   # exit if project rejected
            return
        # check if the project name already exists
        dup_proj_name = False
        proj_path = self.setx.getAppPath() + '/projects'
        for folder in os.listdir(proj_path):
            if os.path.isdir(proj_path):
                if folder.lower() == self.new_proj.lower():
                    dup_proj_name = True
                    break

        if not dup_proj_name:
            self.setx.setCurProject(self.setx.getAppPath() + '/projects/' + self.new_proj + '/')
            os.mkdir(self.setx.getCurProjectPath())
            os.chdir(self.setx.getCurProjectPath())
            self.statusBar().showMessage("New Project (" + self.new_proj + ") created.")
            self.showDirectoryTree(self.setx.getCurProjectPath())

        # self.newProjectAct.setEnabled(True)
        # self.bookmarks.clear()
        # self.setWindowTitle('new File[*]')

    def new_proj_accept(self):
        self.new_proj = self.projedit.text()
        self.np_dialog.close()

    def new_proj_reject(self):
        self.new_proj = 'rejected'
        self.np_dialog.close()

    def openExistingProject(self):
        # FIXME: fix duplicate project name and set new project details
        proj_path = self.setx.getAppPath() + '/projects'
        os.chdir(proj_path)
        for folder in os.listdir(proj_path):
            print(folder)
            break
        else:
            print(proj_path)
        self.setx.setCurProject(self.setx.getCurProjectPath() + self.new_proj)
        self.newProjectAct.setEnabled(True)

    def closeCurrentProject(self):
        return

    # Function to display context menu on the target file viewer
    def targetViewerContextMenu(self, position):
        tv_menu = QMenu(self.targetFileViewer)
        tv_menu.addSection('TARGET ACTIONS:')
        tv_act1 = QAction("Reset Target")
        tv_act1.setIcon(QIcon(self.setx.getAppPath() + "/icons/reset"))
        tv_act1.setIconVisibleInMenu(True)
        tv_act1.triggered.connect(self.resetTargetDevice)
        tv_menu.addAction(tv_act1)
        tv_act2 = QAction("Run Script on Target")
        tv_act2.setIcon(QIcon(self.setx.getAppPath() + "/icons/run"))
        tv_act2.setIconVisibleInMenu(True)
        tv_act2.triggered.connect(self.runTargetScript)
        tv_menu.addAction(tv_act2)
        tv_act3 = QAction("Stop Target Script")
        tv_act3.setIcon(QIcon(self.setx.getAppPath() + "/icons/stop"))
        tv_act3.setIconVisibleInMenu(True)
        tv_act3.triggered.connect(self.stopTargetScript)
        tv_menu.addAction(tv_act3)
        tv_act4 = QAction("Download File to Target")
        tv_act4.setIcon(QIcon(self.setx.getAppPath() + "/icons/download"))
        tv_act4.setIconVisibleInMenu(True)
        tv_act4.triggered.connect(self.downloadScript)
        tv_menu.addAction(tv_act4)
        tv_act5 = QAction("Upload File from Target")
        tv_act5.setIcon(QIcon(self.setx.getAppPath() + "/icons/upload"))
        tv_act5.setIconVisibleInMenu(True)
        tv_act5.triggered.connect(self.uploadScript)
        tv_menu.addAction(tv_act5)
        tv_act6 = QAction("Remove File from Target")
        tv_act6.setIcon(QIcon(self.setx.getAppPath() + "/icons/delete"))
        tv_act6.setIconVisibleInMenu(True)
        tv_act6.triggered.connect(self.removeScript)
        tv_menu.addAction(tv_act6)
        tv_act7 = QAction("New Target Folder")
        tv_act7.setIcon(QIcon(self.setx.getAppPath() + "/icons/folder"))
        tv_act7.setIconVisibleInMenu(True)
        tv_act7.triggered.connect(self.newTargetFolder)
        tv_menu.addAction(tv_act7)
        tv_act8 = QAction("Remove Target Folder")
        tv_act8.setIcon(QIcon(self.setx.getAppPath() + "/icons/folder_del"))
        tv_act8.setIconVisibleInMenu(True)
        tv_act8.triggered.connect(self.newTargetFolder)
        tv_menu.addAction(tv_act8)
        position.setY(position.y() + 50)
        tv_menu.exec(self.targetFileViewer.mapToGlobal(position))

    # Function to display context menu on the project file viewer
    def projectViewerContextMenu(self, position):
        pv_menu = QMenu(self.projectFileViewer)
        pv_menu.addSection('PROJECT ACTIONS:')

        # pv_act1 = QAction("Back")
        # pv_act1.setIcon(QIcon(self.setx.getAppPath() + "/icons/unindent"))
        # pv_act1.setIconVisibleInMenu(True)
        # pv_act1.triggered.connect(self.backUpOneDirectory)
        # pv_menu.addAction(pv_act1)

        pv_act1 = QAction("Change Project Directory")
        pv_act1.setIcon(QIcon(self.setx.getAppPath() + "/icons/folder_open"))
        pv_act1.setIconVisibleInMenu(True)
        pv_act1.triggered.connect(self.getDirectory)
        pv_menu.addAction(pv_act1)

        pv_act2 = QAction("New Project File")
        pv_act2.setIcon(QIcon(self.setx.getAppPath() + "/icons/new24"))
        pv_act2.setIconVisibleInMenu(True)
        pv_act2.triggered.connect(self.newFile)
        pv_menu.addAction(pv_act2)

        # pv_act3 = QAction("Stop Target Script")
        # pv_act3.setIcon(QIcon(self.setx.getAppPath() + "/icons/stop"))
        # pv_act3.setIconVisibleInMenu(True)
        # pv_act3.triggered.connect(self.stopTargetScript)
        # pv_menu.addAction(pv_act3)
        # pv_act4 = QAction("Download File to Target")
        # pv_act4.setIcon(QIcon(self.settings.value('APP_PATH', '') + "/icons/download"))
        # pv_act4.setIconVisibleInMenu(True)
        # pv_act4.triggered.connect(self.downloadScript)
        # pv_menu.addAction(pv_act4)
        # pv_act5 = QAction("Upload File from Target")
        # pv_act5.setIcon(QIcon(self.settings.value('APP_PATH', '') + "/icons/upload"))
        # pv_act5.setIconVisibleInMenu(True)
        # pv_act5.triggered.connect(self.uploadScript)
        # pv_menu.addAction(pv_act5)
        # pv_act6 = QAction("Remove File from Target")
        # pv_act6.setIcon(QIcon(self.settings.value('APP_PATH', '') + "/icons/delete"))
        # pv_act6.setIconVisibleInMenu(True)
        # pv_act6.triggered.connect(self.removeScript)
        # pv_menu.addAction(pv_act6)
        # pv_act7 = QAction("New Target Folder")
        # pv_act7.setIcon(QIcon(self.settings.value('APP_PATH', '') + "/icons/folder"))
        # pv_act7.setIconVisibleInMenu(True)
        # pv_act7.triggered.connect(self.newTargetFolder)
        # pv_menu.addAction(pv_act7)
        # pv_act8 = QAction("Remove Target Folder")
        # pv_act8.setIcon(QIcon(self.settings.value('APP_PATH', '') + "/icons/folder_del"))
        # pv_act8.setIconVisibleInMenu(True)
        # pv_act8.triggered.connect(self.newTargetFolder)
        # pv_menu.addAction(pv_act8)
        position.setY(position.y() + 50)
        pv_menu.exec(self.projectFileViewer.mapToGlobal(position))


    # def backUpOneDirectory(self):
    #     path = os.getcwd().split('/', 20)
    #     print(path)
    #     newpath = ''
    #     for i in range(len(path) - 1):
    #         if path[i]:
    #             newpath += ('/' + path[i])
    #
    #     print(newpath)
    #     os.chdir(newpath)
    #     self.showDirectoryTree(newpath)

    # the action executed when menu is clicked
    def display_selection(self):
        column = self.targetFileViewer.currentColumn()
        text = self.targetFileViewer.currentItem().text(column)
        print("right-clicked item is " + text)

    def remove_tab(self, index):
        self.maybeSave()        # check if text in tab (editor) needs to be saved
        # don't delete last tab
        if index < self.tabsList.count() and self.tabsList.count() > 1:
            self.tabsList.removeTab(index)
            del mpconfig.editorList[index]
            del mpconfig.highlighterList[index]
            del mpconfig.numberbarList[index]
            mpconfig.currentTabIndex = self.tabsList.currentIndex()

    def create_new_tab(self, tab_title):
        new_tab = QWidget()
        new_tab.setObjectName('new_tab')
        new_tab.layout = QHBoxLayout()

        text_editor = PyTextEdit()
        new_cursor = QTextCursor(text_editor.document())
        text_editor.setTextCursor(new_cursor)
        text_editor.setStyleSheet("background-color: rgb(0, 0, 0);\n"
                                  "color: rgb(160, 160, 160);\n"
                                  "border-style: solid;\n"
                                  "border-color: rgb(132, 175, 244);\n"
                                  "border-width: 0px;\n"
                                  "border-radius: 4px;")
        text_editor.setTabStopWidth(12)
        text_editor.setObjectName('editor')
        text_editor.textChanged.connect(self.onTextHasChanged)
        text_editor.cursorPositionChanged.connect(self.onCursorPositionChanged)
        text_editor.setContextMenuPolicy(Qt.CustomContextMenu)
        text_editor.customContextMenuRequested.connect(self.contextMenuRequested)
        text_editor.setLineWrapMode(QPlainTextEdit.NoWrap)

        horiz_sbar = QScrollBar()
        horiz_sbar.setOrientation(Qt.Horizontal)
        horiz_sbar.setStyleSheet("""
                         QScrollBar:horizontal { background-color: rgb(132, 175, 244) } """)
        text_editor.setHorizontalScrollBar(horiz_sbar)

        vert_sbar = QScrollBar()
        vert_sbar.setOrientation(Qt.Vertical)
        vert_sbar.setStyleSheet("""
                         QScrollBar:vertical { background-color: rgb(132, 175, 244) } """)
        text_editor.setVerticalScrollBar(vert_sbar)

        # text_editor.setPlainText(self.mainText)
        text_editor.moveCursor(new_cursor.Start)
        # mpconfig.editorList.append(text_editor)
        highlighter = Highlighter(text_editor.document())
        mpconfig.highlighterList.append(highlighter)
        mpconfig.editorList.append(text_editor)

        mpconfig.currentTabIndex += 1       # update
        num_bar = NumberBar()
        num_bar.setStyleSheet("background-color: rgb(0, 0, 0);\n"  #43, 43, 43);\n"
                                       "color: rgb(160, 160, 160);\n"
                                       "border-style: solid;\n"
                                       "border-color: rgb(132, 175, 244);\n"
                                       "border-width: 0px;\n"
                                       "border-radius: 4px;")
        num_bar.setObjectName('num_bar')
        mpconfig.numberbarList.append(num_bar)
        new_tab.layout.addWidget(num_bar)
        new_tab.layout.addWidget(text_editor)
        new_tab.setLayout(new_tab.layout)
        # set style properties for the new tab
        new_tab.setStyleSheet("background-color: rgb(72, 72, 72);\n"  #"(43, 43, 43);\n"
                              "color: rgb(160, 160, 160);\n"
                              "border-style: solid;\n"
                              "border-width: 0px;\n"
                              "border-radius: 4px;")
        ttip = tab_title
        if len(tab_title) > 11:
            tab_title = tab_title[:8] + "..."

        self.tabsList.addTab(new_tab, tab_title)
        self.tabsList.tabBar().setTabToolTip(self.tabsList.currentIndex(), ttip)
        if self.tabsList.count() > 0:
            self.tabsList.setCurrentIndex(self.tabsList.count()-1)
        self.tabsList.tabBar().setUsesScrollButtons(False)
        return new_tab

    # text in the editor of the current selected tab has changed
    def onTextHasChanged(self):
        if self.setx.getFlagStr('IGNORE_TEXT_CHANGED') == 'True':
            return
        else:
            self.setModified(True)

    # tab selection has changed
    def change_text_editor(self, index):
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
                    pass
                    # self.serialport.write(b'\x08')
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
        print(item_text)
        if len(item_text) > 0:
            path = self.setx.getCurProjectPath() + '/' + self.setx.getCurProjectName() + '/' + item_text
            self.openFile(path)

    def targetFileViewerDblClicked(self, index):
        titem = self.targetFileViewer.currentItem().text(0)
        # ignore dbl click on serial port name
        if titem != self.setx.getSerialPort():
            print(titem)

    # Reset ESP32 target device by asserting DTR
    def resetTargetDevice(self):
        data = self.mpBoard.hardReset()
        self.shellText.append('Reset Target.\n')
        datastr = str(data, 'utf-8')
        self.shellText.append(datastr)

        # if self.serialport.isOpen():
        #     self.serialport.setDataTerminalReady(False)
        #     time.sleep(0.1)
        #     self.serialport.setDataTerminalReady(True)
        #     self.shellText.append('>Reset Target.\n')
        #     self.setx.setFlagStr('IGNORE_SERIAL_AFTER_RESET', 'True')      # ignore bytes from target MCU after reset
        #     time.sleep(0.1)

    def viewTargetFiles(self):
        ret = True

        self.targetFileViewer.clear()
        self.TargetFileList.clear()
        self.TargetFileList = self.mpCmds.ls('/', False, False)

        targ1 = QTreeWidgetItem([self.setx.getSerialPort()])
        targ1.setIcon(0, QIcon(self.setx.getAppPath() + "/icons/port"))
        for i in range(len(self.TargetFileList)):
            if self.TargetFileList[i] == '':
                break
            # print('stdout_list[i]=' + stdout_list[i])
            if self.TargetFileList[i].startswith('/', 0, 1) and self.TargetFileList[i].find('.') != -1:  # is this a directory?
                self.TargetFileList[i] = self.TargetFileList[i].replace('/', '', 1)
            #self.TargetFileList.append(stdout_list[i])
            targ1_child = QTreeWidgetItem([self.TargetFileList[i]])
            targ1_child.setIcon(0, QIcon(self.setx.getAppPath() + "/icons/file"))
            targ1.addChild(targ1_child)

        self.targetFileViewer.addTopLevelItem(targ1)
        self.targetFileViewer.expandAll()

        return ret

        # return
        # proc = 'ampy -p ' + self.setx.getSerialPort()
        # proc += ' -b ' + self.setx.getBaudRate()  # add baudrate
        # proc += ' ls'
        # self.setx.setFlagStr('LIST_TARGET_FILES', 'True')    # direct listed files into the Target Files viewer
        # self.startProcess(proc)

    # Start external process. procCmdStr has the name of the external proc and its arguments
    def startProcess(self, procCmdStr):
        if len(procCmdStr) == 0:
            return
        if self.extProc.atEnd():  # No process running if true.
            # self.serialport.close()     # close serial port cuz external proc needs to use serial port
            self.extProc.finished.connect(self.procFinished)
            self.extProc.readyReadStandardOutput.connect(self.procHandleStdout)
            self.extProc.readyReadStandardError.connect(self.procHandleStderr)
            self.extProc.stateChanged.connect(self.procHandleState)
            self.extProc.start(procCmdStr)
            self.extProc.waitForStarted(3000)
            mpconfig.sline = ''
        else:
            self.shellText.append('Run Failed! Another script is currently running!\n')

    def procHandleStderr(self):
        data = self.extProc.readAllStandardError()
        stderr = bytes(data).decode("utf8")
        self.shellText.append(stderr)

    # external process returns data
    def procHandleStdout(self):
        data = self.extProc.readAllStandardOutput()
        stdout = bytes(data).decode("utf8")

        # --- redirect files list to Target Files viewer
        if self.setx.getFlagStr('LIST_TARGET_FILES') == 'True' and len(stdout) > 0:
            self.setx.setFlagStr('LIST_TARGET_FILES', 'False')
            self.targetFileViewer.clear()
            self.TargetFileList.clear()
            stdout_list = stdout.split('\n')
            targ1 = QTreeWidgetItem([self.setx.getSerialPort()])
            targ1.setIcon(0, QIcon(self.setx.getAppPath() + "/icons/port"))
            for i in range(len(stdout_list)):
                if stdout_list[i] == "":
                    break
                # print('stdout_list[i]=' + stdout_list[i])
                if stdout_list[i].startswith('/', 0, 1) and stdout_list[i].find('.') != -1:     # is this a directory?
                    stdout_list[i] = stdout_list[i].replace('/', '', 1)
                self.TargetFileList.append(stdout_list[i])
                targ1_child = QTreeWidgetItem([stdout_list[i]])
                targ1_child.setIcon(0, QIcon(self.setx.getAppPath() + "/icons/file"))
                targ1.addChild(targ1_child)

            self.targetFileViewer.addTopLevelItem(targ1)
            self.targetFileViewer.expandAll()

        # Redirect target file text to the python text editor on the current tab
        elif self.setx.getFlagStr('UPLOAD_TARGET_FILE') == 'True' and len(stdout) > 0:
            self.setx.setFlagStr('UPLOAD_TARGET_FILE', 'False')
            print(stdout)
            mpconfig.editorList[mpconfig.currentTabIndex].setPlainText(stdout.replace(tab, "    "))
            QApplication.restoreOverrideCursor()

        else:
            mpconfig.sline += stdout
            if mpconfig.sline.endswith('\x0a'):
                # Replace all occurrences of character s with an empty string
                mpconfig.sline = re.sub('\x0d', '', mpconfig.sline)
                mpconfig.sline = re.sub('\x0a', '', mpconfig.sline)
                print(":".join("{:02x}".format(ord(c)) for c in mpconfig.sline))
                self.shellText.append(mpconfig.sline)   # default - send ext proc text to shellText
                self.shellText.moveCursor(self.cursor.End)
                self.shellText.setFocus()
                mpconfig.sline = ''

    def procHandleState(self, state):
        states = {
            QProcess.NotRunning: 'Stopped',
            QProcess.Starting: 'Starting',
            QProcess.Running: 'Running',
        }
        state_name = states[state]
        # reopen closed serial port so REPL will work
        # if 'Stopped' in state_name:
        #     self.serialport.open(QIODevice.ReadWrite)       # reopen serial port
        #self.shellText.append(f"Process status: {state_name}")

    def procFinished(self):
        if self.setx.getFlagStr('SCRIPT_IS_RUNNING') == 'True':
            self.shellText.append('\nScript ' + self.setx.getCurProjectPath() + '.' +
                        self.setx.getCurTargetScript() + ' has Completed\n')
            self.setx.setFlagStr('SCRIPT_IS_RUNNING', 'False')

        if self.setx.getFlagStr('REMOVE_TARGET_FILE') == 'True':
            self.setx.setFlagStr('REMOVE_TARGET_FILE', 'False')
            QApplication.restoreOverrideCursor()

    ### Run current script on target device (no download)
    def runTargetScript(self):
        dialog = QFileDialog(self)
        dialog.setWindowTitle('Run Script on Target Device')
        dialog.setNameFilter('(*.py)')
        dialog.setDirectory(self.setx.getCurProjectPath() + '.' + self.setx.getCurTargetScript())
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

        self.setx.setCurTargetScript(fname)
        self.shellText.append('\nStarting script: ' + fname + '\n')
        self.shellText.moveCursor(self.cursor.End)
        #self.setx.setCurProjectPath(fname)
        #self.setx.setScriptIsRunning(True)
        self.mpCmds.run(fname, False, True)


    def stopTargetScript(self):
        self.shellText.append("Stopping current script " + self.setx.getCurTargetScript() + "\n")
        self.mpBoard.stopScript()

    def downloadScript(self):
        dialog = QFileDialog(self)
        dialog.setWindowTitle('Download File to Target Device')
        dialog.setNameFilter('(*.py)')
        dialog.setDirectory(self.setx.getCurProjectPath() + '.' + self.setx.getCurTargetScript())
        dialog.setFileMode(QFileDialog.ExistingFile)
        filename = None
        fname = ''
        if dialog.exec_() == QDialog.Rejected:
            return
        filename = dialog.selectedFiles()
        fname = str(filename[0])

        if len(fname) > 0:
            self.mpCmds.put(fname)
        # proc = 'ampy -p ' + self.setx.getSerialPort()
        # proc += ' -b ' + self.setx.getBaudRate()       # add baudrate
        # proc += ' put ' + fname
        # self.startProcess(proc)
        # if self.extProc.waitForFinished(10000):

        self.viewTargetFiles()

    def uploadScript(self):
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
        if self.upldDialog.result() == QDialog.Accepted:
            data = self.mpCmds.get(self.upldTree.currentItem().text(0))
            if len(data) > 0:
                data = str(data, 'utf-8')   # convert bytes to string
                mpconfig.editorList[mpconfig.currentTabIndex].setPlainText(data.replace(tab, "    "))

    def upldDialogCancel(self):
        self.upldDialog.reject()  #  .setResult(0)
        self.upldDialog.close()

    def upldDialogAccept(self):
        self.upldDialog.accept()
        self.upldDialog.close()

    # remove (delete) target script file
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
            items.append(l1)

        self.rmTree.addTopLevelItems(items)
        if len(items) > 0:
            self.rmTree.setCurrentItem(items[0])  # highlight first item

        self.rmTree.expandAll()
        vLayout.addWidget(self.rmTree)

        hLayout = QHBoxLayout()
        hLayout.addStretch()
        btn_ok = QPushButton("OK")
        btn_ok.clicked.connect(self.rmDialogAccept)
        btn_ok.setToolTip('Accept File')
        btn_ok.setMaximumWidth(100)
        hLayout.addWidget(btn_ok, 1, Qt.AlignHCenter);
        self.rmTree.itemDoubleClicked.connect(self.rmDialogAccept)
        hLayout.addWidget(btn_ok)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.rmDialogCancel)
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

    def rmDialogCancel(self):
        self.rmScriptDialog.reject()  #  .setResult(0)
        self.rmScriptDialog.close()

    def rmDialogAccept(self):
        self.rmScriptDialog.accept()
        self.rmScriptDialog.close()

    def newTargetFolder(self):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.mpCmds.mkdir('testdir')
        self.viewTargetFiles()
        QApplication.restoreOverrideCursor()

    def rmTargetFolder(self):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.mpCmds.rmdir('testdir')
        self.viewTargetFiles()
        QApplication.restoreOverrideCursor()

    def setBaudrate(self, baud):
        self.setx.setBaudRate(baud)
       # self.serialport.setBaudRate(int(baud))

    def saveComPort(self):
        if len(self.comportfield.text()) > 0:
            self.comportfield.selectAll()
            self.comportfield.repaint()
            self.setx.setSerialPort(self.comportfield.text())
            self.comportfield.deselect()
            #self.serialport.setPortName(self.comportfield.text())

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
        if mpconfig.editorList[mpconfig.currentTabIndex].toPlainText() == "" or \
                        mpconfig.editorList[mpconfig.currentTabIndex].toPlainText() == self.mainText:
            self.statusBar().showMessage("no code to reindent")
        else:
            mpconfig.editorList[mpconfig.currentTabIndex].selectAll()
            tab = "\t"
            oldtext = mpconfig.editorList[mpconfig.currentTabIndex].textCursor().selectedText()
            newtext = oldtext.replace(tab, "    ")
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

    ### QPlainTextEdit contextMenu
    def contextMenuRequested(self, point):
        cmenu = QMenu()
        cmenu = mpconfig.editorList[mpconfig.currentTabIndex].createStandardContextMenu()
        cmenu.addSeparator()
        cmenu.addAction(self.jumpToAct)
        cmenu.addSeparator()
        if not mpconfig.editorList[mpconfig.currentTabIndex].textCursor().selectedText() == "":
            cmenu.addAction(QIcon.fromTheme("gtk-find-and-replace"), "replace all occurrences with", self.replaceThis)
            cmenu.addSeparator()
        cmenu.addAction(QIcon.fromTheme(self.setx.getAppPath() + "/icons/zeal"), "Zeal Developer Help", self.showZeal)
        cmenu.addAction(QIcon.fromTheme(self.setx.getAppPath() + "/icons/find"), "Find this (F10)", self.findNextWord)
        cmenu.addSeparator()
        cmenu.addSeparator()
        cmenu.addAction(self.commentAct)
        cmenu.addAction(self.uncommentAct)
        cmenu.addSeparator()
        if not mpconfig.editorList[mpconfig.currentTabIndex].textCursor().selectedText() == "":
            cmenu.addAction(self.commentBlockAct)
            cmenu.addAction(self.uncommentBlockAct)
            cmenu.addSeparator()
            cmenu.addAction(self.indentAct)
            cmenu.addAction(self.indentLessAct)
        cmenu.addSeparator()
        cmenu.addAction(QIcon.fromTheme(self.setx.getAppPath() + "/icons/color1"), "Insert QColor", self.insertColor)
        cmenu.addSeparator()
        cmenu.addAction(QIcon.fromTheme("preferences-color"), "Insert Color Hex Value", self.changeColor)
        cmenu.exec_(mpconfig.editorList[mpconfig.currentTabIndex].mapToGlobal(point))

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
            print(rtext)
        #            mpconfig.editorList[mpconfig.currentTabIndex].moveCursor(QTextCursor.StartOfWord, QTextCursor.MoveAnchor)
        #            mpconfig.editorList[mpconfig.currentTabIndex].moveCursor(QTextCursor.EndOfWord, QTextCursor.KeepAnchor)
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
            for i in range(linecount + 1):
                list.insert(i, "    " + theList[i])
            mpconfig.editorList[mpconfig.currentTabIndex].textCursor().insertText(newline.join(list))
            self.setModified(True)
            #            mpconfig.editorList[mpconfig.currentTabIndex].find(ot)
            self.statusBar().showMessage("tabs indented")

    def unindentLine(self):
        if not mpconfig.editorList[mpconfig.currentTabIndex].textCursor().selectedText() == "":
            newline = u"\u2029"
            list = []
            ot = mpconfig.editorList[mpconfig.currentTabIndex].textCursor().selectedText()
            theList = ot.splitlines()
            linecount = ot.count(newline)
            for i in range(linecount + 1):
                list.insert(i, (theList[i]).replace("    ", "", 1))
            mpconfig.editorList[mpconfig.currentTabIndex].textCursor().insertText(newline.join(list))
            self.setModified(True)
            #            mpconfig.editorList[mpconfig.currentTabIndex].find(ot)
            self.statusBar().showMessage("tabs deleted")

    def dataReady(self):
        out = ""
        try:
            out = str(self.process.readAll(), encoding='utf8').rstrip()
        except TypeError:
            self.msgbox("Error", str(self.process.readAll(), encoding='utf8'))
            out = str(self.process.readAll()).rstrip()
        self.shellText.moveCursor(self.cursor.Start)
        self.shellText.append(out)
        if self.shellText.find("line", QTextDocument.FindWholeWords):
            t = self.shellText.toPlainText().partition("line")[2].partition("\n")[0].lstrip()
            if t.find(",", 0):
                tr = t.partition(",")[0]
            else:
                tr = t.lstrip()
            self.gotoErrorLine(tr)
        else:
            return
        self.shellText.moveCursor(self.cursor.End)
        self.shellText.ensureCursorVisible()

    def createActions(self):
        maxf = int(self.setx.getMaxRecentFiles())
        for i in range(maxf):
            self.recentFileActs.append(QAction(self, visible=False, triggered=self.openRecentFile))

    def addBookmark(self):
        linenumber = self.getLineNumber()
        linetext = mpconfig.editorList[mpconfig.currentTabIndex].textCursor().block().text().strip()
        self.bookmarks.addItem(linetext, linenumber)

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
        if mpconfig.editorList[mpconfig.currentTabIndex].find(self.bookmarks.itemText(self.bookmarks.currentIndex())):
            pass
        else:
            mpconfig.editorList[mpconfig.currentTabIndex].moveCursor(QTextCursor.Start)
            mpconfig.editorList[mpconfig.currentTabIndex].find(self.bookmarks.itemText(self.bookmarks.currentIndex()))

        mpconfig.editorList[mpconfig.currentTabIndex].centerCursor()
        mpconfig.editorList[mpconfig.currentTabIndex].moveCursor(self.cursor.StartOfLine, self.cursor.MoveAnchor)

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
        if not mpconfig.editorList[mpconfig.currentTabIndex].toPlainText() == "":
            self.clearBookmarks()
            newline = "\n"  # u"\2029"
            fr = "from"
            im = "import"
            d = "def"
            d2 = "    def"
            c = "class"
            sn = str("if __name__ ==")
            line = ""
            list = []
            ot = mpconfig.editorList[mpconfig.currentTabIndex].toPlainText()
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

    def clearLabel(self):
        self.shellText.setText("")
        self.shellText.moveCursor(self.cursor.End)

    def openRecentFile(self):
        action = self.sender()
        if action:
            myfile = action.data()
            print('open recent file: ' + myfile)
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

        # check if the filename already exists in another tab
        dup_tab_name = False
        for i in range(self.tabsList.count()):
            tn = self.tabsList.tabBar().tabText(i)
            if tn.lower() == self.newf_name.lower():
                self.tabsList.setCurrentIndex(i)
                mpconfig.currentTabIndex = i
                dup_tab_name = True
                break
        if dup_tab_name or mpconfig.editorList[mpconfig.currentTabIndex].toPlainText() != '':
            self.create_new_tab(self.newf_name)     # create
        self.change_text_editor(mpconfig.currentTabIndex)
        self.setModified(False)
        mpconfig.editorList[mpconfig.currentTabIndex].moveCursor(self.cursor.End)
        self.statusBar().showMessage("new File (" + self.newf_name + ") created.")
        self.tabsList.tabBar().setTabText(self.tabsList.currentIndex(), self.newf_name) # update editor tab text
        mpconfig.editorList[mpconfig.currentTabIndex].setFocus()
        self.bookmarks.clear()
        self.setWindowTitle('new File[*]')
        self.filename = self.newf_name
        self.fileSave()

    def newf_accept(self):
        self.newf_name = self.fileedit.text()
        self.fdialog.close()

    def newf_reject(self):
        self.newf_name = 'untitled'
        self.fdialog.close()

    ### open File
    def openFileOnStart(self, path=None):
        if os.path.isfile(path):
            inFile = QFile(path)
            if inFile.open(QFile.ReadWrite | QFile.Text):
                text = inFile.readAll()
                text = str(text, encoding='utf8')   # encode bytes to ascii string (Python3 method)
                # if file is not currently being edited, create new tab & editor for text
                files = self.getFilesInDir(self.setx.getCurProjectPath() +
                                           '/' + self.setx.getCurProjectName())
                dupFileFound = False
                for i in range(len(files)):
                    if files[i] == self.tabsList.tabBar().tabText(i):
                        dupFileFound = True
                if not dupFileFound and mpconfig.editorList[mpconfig.currentTabIndex].toPlainText() != '':
                    self.create_new_tab(path)
                if mpconfig.editorList[mpconfig.currentTabIndex].toPlainText() == '':
                    mpconfig.editorList[mpconfig.currentTabIndex].setPlainText(text.replace(tab, "    "))
                    self.setModified(False)
                self.setCurrentFile(path, False)
                self.findBookmarks()
                self.statusBar().showMessage("File '" + path + "' loaded.")
                mpconfig.editorList[mpconfig.currentTabIndex].setFocus()
            else:
                print('Opening file "' + path + '" failed!')

    ### Open File
    def openFile(self, path=None):
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Open File", self.setx.getCurProjectPath(),
                                                  "Python Files (*.py);; all Files (*)")
        if path:
            self.openFileOnStart(path)

    ### Save file
    def fileSave(self):
        if self.filename != "" and self.filename != 'untitled':
            file = QFile(self.filename)
            if not file.open(QFile.WriteOnly | QFile.Text):
                QMessageBox.warning(self, "Error",
                                    "Cannot write file %s:\n%s." % (self.filename, file.errorString()))
                return

            outstr = QTextStream(file)
            QApplication.setOverrideCursor(Qt.WaitCursor)
            outstr << mpconfig.editorList[mpconfig.currentTabIndex].toPlainText()   # write text to file & close
            QApplication.restoreOverrideCursor()
            self.setModified(False)
            self.fname = QFileInfo(self.filename).fileName()
            #self.setWindowTitle(self.fname + "[*]")
            self.statusBar().showMessage("File saved.")
            self.setCurrentFile(self.filename, False)
            mpconfig.editorList[mpconfig.currentTabIndex].setFocus()
            self.showDirectoryTree(self.setx.getCurProjectPath())

        else:
            self.fileSaveAs()

    ### save File
    def fileSaveAs(self):
        fn, _ = QFileDialog.getSaveFileName(self, "Save as...", self.filename,
                                            "Python files (*.py)")
        if not fn:
            print("Error saving")
            return False

        lfn = fn.lower()
        if not lfn.endswith('.py'):
            fn += '.py'

        self.filename = fn
        self.fname = QFileInfo(QFile(fn).fileName())
        self.fileSave()
        self.showDirectoryTree(self.setx.getCurProjectPath())
        self.setx.setCurProjectScript(self.fname)

    def closeEvent(self, e):
        self.writeSettings()
        if self.maybeSave():
            e.accept()
        else:
            e.ignore()

    ### ask to save
    def maybeSave(self):
        if not mpconfig.editorList[mpconfig.currentTabIndex].textHasChanged:
            return True
        # if not self.isModified():
        #     return True

        if self.filename.startswith(':/'):      # ???
            return True

        ret = QMessageBox.question(self, "Message",
                                   "<h4><p>The document was modified.</p>\n" \
                                   "<p>Do you want to save changes?</p></h4>",
                                   QMessageBox.Yes | QMessageBox.Discard | QMessageBox.Cancel)

        if ret == QMessageBox.Yes:
            if self.filename == "":
                self.fileSaveAs()
                return False
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
                    <span style='color: #8a8a8a; font-size: 9pt;'>Original code Forked from PyEdit2 by Axel Schneider @2017</strong></span></p>
                        """
        self.infobox(title, message)

    def readData(self, cmd):
        self.shellText.clear()
        dname = QFileInfo(self.filename).filePath().replace(QFileInfo(self.filename).fileName(), "")
        self.statusBar().showMessage(str(dname))
        QProcess().execute("cd '" + dname + "'")
        self.process.start(cmd, ['-u', dname + self.strippedName(self.filename)])

    def killPython(self):
        if (self.mypython == "3"):
            cmd = "killall python3"
        else:
            cmd = "killall python"
        self.readData(cmd)

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

    def findText(self):
        word = self.findfield.text()
        if mpconfig.editorList[mpconfig.currentTabIndex].find(word):
            linenumber = mpconfig.editorList[mpconfig.currentTabIndex].textCursor().blockNumber() + 1
            self.statusBar().showMessage("found <b>'" + self.findfield.text() + "'</b> at Line: " + str(linenumber))
            mpconfig.editorList[mpconfig.currentTabIndex].centerCursor()
        else:
            self.statusBar().showMessage("<b>'" + self.findfield.text() + "'</b> not found")
            mpconfig.editorList[mpconfig.currentTabIndex].moveCursor(QTextCursor.Start)
            if mpconfig.editorList[mpconfig.currentTabIndex].find(word):
                linenumber = mpconfig.editorList[mpconfig.currentTabIndex].textCursor().blockNumber() + 1
                self.statusBar().showMessage("found <b>'" + self.findfield.text() + "'</b> at Line: " + str(linenumber))
                mpconfig.editorList[mpconfig.currentTabIndex].centerCursor()

    def findBookmark(self, word):
        if mpconfig.editorList[mpconfig.currentTabIndex].find(word):
            linenumber = self.getLineNumber()  # mpconfig.editorList[mpconfig.currentTabIndex].textCursor().blockNumber() + 1
            self.statusBar().showMessage("found <b>'" + self.findfield.text() + "'</b> at Line: " + str(linenumber))

    def handleQuit(self):
        if self.maybeSave():
            print("Goodbye ...")
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
            highlighted_line.format.setBackground(lineHighlightColor)
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

    def isModified(self):
        return mpconfig.editorList[mpconfig.currentTabIndex].textHasChanged

    def setModified(self, modified):
        mpconfig.editorList[mpconfig.currentTabIndex].textHasChanged = modified

    def setLineWrapMode(self, mode):
        mpconfig.editorList[mpconfig.currentTabIndex].setLineWrapMode(mode)

    def clear(self):
        mpconfig.editorList[mpconfig.currentTabIndex].clear()

    def setPlainText(self, *args, **kwargs):
        mpconfig.editorList[mpconfig.currentTabIndex].setPlainText(*args, **kwargs)

    def setDocumentTitle(self, *args, **kwargs):
        mpconfig.editorList[mpconfig.currentTabIndex].setDocumentTitle(*args, **kwargs)

    def replaceAll(self):
        if not mpconfig.editorList[mpconfig.currentTabIndex].document().toPlainText() == "":
            if not self.findfield.text() == "":
                self.statusBar().showMessage("replacing all")
                oldtext = mpconfig.editorList[mpconfig.currentTabIndex].document().toPlainText()
                newtext = oldtext.replace(self.findfield.text(), self.replacefield.text())
                mpconfig.editorList[mpconfig.currentTabIndex].setPlainText(newtext)
                self.setModified(True)
            else:
                self.statusBar().showMessage("nothing to replace")
        else:
            self.statusBar().showMessage("no text")

    def replaceOne(self):
        if not mpconfig.editorList[mpconfig.currentTabIndex].document().toPlainText() == "":
            if not self.findfield.text() == "":
                self.statusBar().showMessage("replacing all")
                oldtext = mpconfig.editorList[mpconfig.currentTabIndex].document().toPlainText()
                newtext = oldtext.replace(self.findfield.text(), self.replacefield.text(), 1)
                mpconfig.editorList[mpconfig.currentTabIndex].setPlainText(newtext)
                self.setModified(True)
            else:
                self.statusBar().showMessage("nothing to replace")
        else:
            self.statusBar().showMessage("no text")

    def setCurrentFile(self, fileName, modified):
        self.filename = fileName
        ttip = 'untitled'
        fname = ttip

        if self.filename:
            fname = self.strippedName(self.filename)
            if modified:
                fname += " *"
            ttip = fname
            if len(fname) > 11:
                fname = fname[:8] + "..."

        self.tabsList.setTabText(self.tabsList.currentIndex(), fname)
        self.tabsList.tabBar().setTabToolTip(self.tabsList.currentIndex(), ttip)

        files = self.setx.getRecentFileList()

        if files:
            try:
                files.remove(fileName)
            except ValueError:
                pass

            if not fileName == "/tmp/tmp.py":
                files.insert(0, fileName)

            maxf = int(self.setx.getMaxRecentFiles())
            del files[maxf:]

            self.setx.setRecentFileList(files)

        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, pyEditor):
                widget.updateRecentFileActions()

    def updateRecentFileActions(self):
        mytext = ""
        files = self.setx.getRecentFileList()
        if not files:
            numRecentFiles = 0
        else:
            numRecentFiles = min(len(files), int(self.setx.getMaxRecentFiles()))

        for i in range(numRecentFiles):
            text = "&%d %s" % (i + 1, self.strippedName(files[i]))
            self.recentFileActs[i].setText(text)
            self.recentFileActs[i].setData(files[i])
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
                self.findBookmarks()
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
            self.statusBar().showMessage("no text")
        else:
            dialog = QPrintDialog()
            if dialog.exec_() == QDialog.Accepted:
                self.handlePaintRequest(dialog.printer())
                self.statusBar().showMessage("Document printed")

    def handlePrintPreview(self):
        if mpconfig.editorList[mpconfig.currentTabIndex].toPlainText() == "":
            self.statusBar().showMessage("no text")
        else:
            dialog = QtPrintSupport.QPrintPreviewDialog()
            dialog.setFixedSize(900, 650)
            dialog.paintRequested.connect(self.handlePaintRequest)
            dialog.exec_()
            self.statusBar().showMessage("Print Preview closed")

    def handlePaintRequest(self, printer):
        printer.setDocName(self.filename)
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
    color: #1EAE3D;
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
    color: #1EAE3D;
    font-size: 9pt;
    }
    QLineEdit
    {
    font-family: Helvetica;
    font-size: 8pt;
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
    color: #A0A0A0;
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
    print('locale = ' + locale)
    path = QLibraryInfo.location(QLibraryInfo.TranslationsPath)
    translator.load('qt_%s' % locale, path)
    app.installTranslator(translator)
    win = pyEditor()
    win.setWindowTitle("MicroPy IDE" + "[*]")
    win.show()
    win.resetTargetDevice()
    win.viewTargetFiles()       # try to view Target directory
    if len(argv) > 1:
        print('argv= ' + argv[1])
        win.openFileOnStart(argv[1])

    sys.exit(app.exec_())

