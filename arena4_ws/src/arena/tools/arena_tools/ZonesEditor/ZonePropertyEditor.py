from PyQt5 import QtGui, QtCore, QtWidgets
import os
import copy
from arena_tools.ZonesEditor.Zone import *
from arena_tools.utils.QtExtensions import *
from arena_tools.utils.HelperFunctions import *


class PropertyField(QtWidgets.QWidget):
    def __init__(self, key: str, value="", **kwargs):
        super().__init__(**kwargs)
        self.key = key
        self.value = value

        self.setupUI()

    def setupUI(self):
        self.setLayout(QtWidgets.QHBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)

        self.keyLabel = QtWidgets.QLabel(self.key)
        self.keyLabel.setFixedWidth(150)
        self.layout().addWidget(self.keyLabel)

        self.valueEdit = QtWidgets.QLineEdit(self.value)
        self.layout().addWidget(self.valueEdit)

        self.removeButton = QtWidgets.QPushButton("X")
        self.removeButton.pressed.connect(self.remove)
        self.removeButton.setFixedWidth(30)
        self.removeButton.setStyleSheet("background-color: red")
        self.layout().addWidget(self.removeButton)

    def getKeyValue(self):
        return self.key, self.valueEdit.text()

    def remove(self):
        self.parentWidget().layout().removeWidget(self)
        self.deleteLater()


class ColorField(QtWidgets.QWidget):
    def __init__(self, key: str, color: QtGui.QColor, **kwargs):
        super().__init__(**kwargs)
        self.key = key
        self.color = color

        self.setupUI()

    def setupUI(self):
        self.setLayout(QtWidgets.QHBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)

        self.keyLabel = QtWidgets.QLabel(self.key)
        self.keyLabel.setFixedWidth(150)
        self.layout().addWidget(self.keyLabel)

        self.colorButton = QtWidgets.QPushButton()
        self.colorButton.setStyleSheet("background-color: {0}".format(self.color.name()))
        self.colorButton.pressed.connect(self.pickColor)
        self.layout().addWidget(self.colorButton)

        self.removeButton = QtWidgets.QPushButton("X")
        self.removeButton.pressed.connect(self.remove)
        self.removeButton.setFixedWidth(30)
        self.removeButton.setStyleSheet("background-color: red")
        self.layout().addWidget(self.removeButton)

    def getKeyColor(self):
        return self.key, self.color

    def pickColor(self):
        color = QtWidgets.QColorDialog(self.color).getColor()
        if color.isValid():
            self.color = color
            self.colorButton.setStyleSheet("background-color: {0}".format(self.color.name()))

    def remove(self):
        self.parentWidget().layout().removeWidget(self)
        self.deleteLater()


class ZonePropertyEditor(QtWidgets.QWidget):
    editorSaved = QtCore.pyqtSignal()

    def __init__(self, zone: Zone, **kwargs):
        super().__init__(**kwargs)
        self.zone = zone
        self.category = []

        self.setupUI()
        self.updateValuesFromZone()

    def setupUI(self):
        self.setWindowTitle("Zone Editor")
        self.setLayout(QtWidgets.QGridLayout())
        self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        self.resize(600, 600)
        self.move(220, 150)

        # scrollarea
        self.scrollArea = QtWidgets.QScrollArea(self)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setMinimumWidth(600)
        self.layout().addWidget(self.scrollArea, 0, 0, 1, -1)

        # frame
        self.scrollAreaFrame = QtWidgets.QFrame()
        self.scrollAreaFrame.setLayout(QtWidgets.QGridLayout())
        self.scrollAreaFrame.setSizePolicy(QtWidgets.QSizePolicy.Policy.Maximum, QtWidgets.QSizePolicy.Policy.Maximum)
        self.scrollAreaFrame.setMinimumWidth(500)
        self.scrollArea.setWidget(self.scrollAreaFrame)

        # name
        self.nameLabel = QtWidgets.QLabel("Label")
        name = self.zone.label
        self.nameEdit = QtWidgets.QLineEdit(name)
        self.scrollAreaFrame.layout().addWidget(self.nameLabel, 0, 0)
        self.scrollAreaFrame.layout().addWidget(self.nameEdit, 0, 1)

        # categories
        self.catLabel = QtWidgets.QLabel("Categories")
        self.scrollAreaFrame.layout().addWidget(self.catLabel, 1, 0)

        self.toolbutton = QtWidgets.QToolButton(self)
        self.toolbutton.setFixedSize(325, 25)
        self.toolbutton.setStyleSheet("text-align:left")
        self.toolmenu = QtWidgets.QMenu(self)
        self.toolmenu.triggered.connect(self.updateToolText)
        self.toolmenu.setFixedWidth(325)
        self.toolbutton.setMenu(self.toolmenu)
        self.toolbutton.setPopupMode(QtWidgets.QToolButton.InstantPopup)

        self.scrollAreaFrame.layout().addWidget(self.toolbutton, 1, 1)

        # additional json props
        self.propLabel = QtWidgets.QLabel("Addtional properties")
        self.scrollAreaFrame.layout().addWidget(self.propLabel, 2, 0, 1, 1, QtCore.Qt.AlignmentFlag.AlignLeft)
        self.propFrame = QtWidgets.QFrame()
        self.propFrame.setLayout(QtWidgets.QVBoxLayout())
        self.propFrame.setContentsMargins(0, 0, 0, 0)
        self.scrollAreaFrame.layout().addWidget(self.propFrame, 3, 0, 1, 2)
        self.propEdit = QtWidgets.QLineEdit()
        self.propEdit.setFixedWidth(150)
        self.propEdit.returnPressed.connect(self.addNewKey)
        self.scrollAreaFrame.layout().addWidget(self.propEdit, 4, 0, 1, 1, QtCore.Qt.AlignmentFlag.AlignLeft)

        # save button
        self.save_button = QtWidgets.QPushButton("Save and Close")
        self.save_button.clicked.connect(self.onSaveClicked)
        self.scrollAreaFrame.layout().addWidget(self.save_button, 5, 0, 1, 2)

    def updateValuesFromZone(self):
        self.nameEdit.setText(self.zone.label)

        self.toolmenu.clear()

        for i, cat in enumerate(self.category):
            action = self.toolmenu.addAction(cat)
            action.setCheckable(True)
            action.setChecked(cat in self.zone.category)

        self.updateToolText()

        for i in reversed(range(self.propFrame.layout().count())):
            self.propFrame.layout().itemAt(i).widget().setParent(None)

        for key, value in self.zone.properties.items():
            self.addKeyValueField(key, value)

    def updateToolText(self):
        self.toolbutton.setText(", ".join(self.getCategories()))

    def getProperties(self):
        widgets: List[PropertyField] = []
        for i in range(self.propFrame.layout().count()):
            w = self.propFrame.layout().itemAt(i).widget()
            if w is not None:
                widgets.append(w)

        return {key: value for key, value in (p.getKeyValue() for p in widgets)}

    def addNewKey(self):
        key = self.propEdit.text()
        self.propEdit.setText("")
        if key not in self.getProperties().keys():
            self.addKeyValueField(key)

    def addKeyValueField(self, key, value=""):
        self.propFrame.layout().addWidget(PropertyField(key, value, parent=self.propFrame))

    def show(self):
        self.updateValuesFromZone()
        return super().show()

    def getCategories(self):
        return [action.text() for action in self.toolmenu.actions() if action.isChecked()]

    def onSaveClicked(self):
        self.zone.category = self.getCategories()
        self.zone.label = self.nameEdit.text()
        self.zone.properties = self.getProperties()
        self.hide()
        self.editorSaved.emit()

    def closeEvent(self, event):
        # ask user if changes should be saved
        msg_box = QtWidgets.QMessageBox()
        msg_box.setText("Do you want to save changes to this zone?")
        msg_box.setStandardButtons(QtWidgets.QMessageBox.Save | QtWidgets.QMessageBox.Discard | QtWidgets.QMessageBox.Cancel)
        msg_box.setDefaultButton(QtWidgets.QMessageBox.Save)
        ret = msg_box.exec()
        if ret == QtWidgets.QMessageBox.Save:
            self.onSaveClicked()
        elif ret == QtWidgets.QMessageBox.Discard:
            self.updateValuesFromZone()
        elif ret == QtWidgets.QMessageBox.Cancel:
            event.ignore()


class CategoriesEditor(QtWidgets.QWidget):
    editorSaved = QtCore.pyqtSignal()

    def __init__(self, zonesData: ZonesData, **kwargs):
        super().__init__(**kwargs)

        self.setupUI()
        self.updateValuesFromZone(zonesData)

    def setupUI(self):
        self.setWindowTitle("Categories Editor")
        self.setLayout(QtWidgets.QGridLayout())
        self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        self.resize(600, 600)
        self.move(220, 150)

        # scrollarea
        self.scrollArea = QtWidgets.QScrollArea(self)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setMinimumWidth(600)
        self.layout().addWidget(self.scrollArea, 0, 0, 1, -1)

        # frame
        self.scrollAreaFrame = QtWidgets.QFrame()
        self.scrollAreaFrame.setLayout(QtWidgets.QGridLayout())
        self.scrollAreaFrame.setSizePolicy(QtWidgets.QSizePolicy.Policy.Maximum, QtWidgets.QSizePolicy.Policy.Maximum)
        self.scrollAreaFrame.setMinimumWidth(500)
        self.scrollArea.setWidget(self.scrollAreaFrame)

        # label
        self.label = QtWidgets.QLabel("Categories")
        self.scrollAreaFrame.layout().addWidget(self.label, 0, 0, 1, 2)

        # additional categories
        self.catFrame = QtWidgets.QFrame()
        self.catFrame.setLayout(QtWidgets.QVBoxLayout())
        self.catFrame.setContentsMargins(0, 0, 0, 0)
        self.scrollAreaFrame.layout().addWidget(self.catFrame, 1, 0, 1, 2)

        self.catEdit = QtWidgets.QLineEdit()
        self.catEdit.setPlaceholderText("Enter new category...")
        self.catEdit.setFixedWidth(150)
        self.catEdit.returnPressed.connect(self.addNewCat)
        self.scrollAreaFrame.layout().addWidget(self.catEdit, 2, 0, 1, 1, QtCore.Qt.AlignmentFlag.AlignLeft)

        # save button
        self.save_button = QtWidgets.QPushButton("Save and Close")
        self.save_button.clicked.connect(self.onSaveClicked)
        self.scrollAreaFrame.layout().addWidget(self.save_button, 3, 0, 1, 2)

    def updateValuesFromZone(self, zonesData: ZonesData = None):
        for i in reversed(range(self.catFrame.layout().count())):
            self.catFrame.layout().itemAt(i).widget().setParent(None)

        if zonesData is not None:
            self.zonesData = zonesData
            self.catColor = dict()
            for key in self.zonesData.getCategories():
                self.addKeyColorField(key)
            self.catColor = self.getCategories()

        else:
            for key, color in self.catColor.items():
                self.addKeyColorField(key, color)

    def getColorFields(self) -> List[ColorField]:
        widgets: List[ColorField] = []
        for i in range(self.catFrame.layout().count()):
            w = self.catFrame.layout().itemAt(i).widget()
            if w is not None:
                widgets.append(w)
        return widgets

    def getCategories(self):
        return {key: color for key, color in (p.getKeyColor() for p in self.getColorFields())}

    def addNewCat(self):
        key = self.catEdit.text()
        self.catEdit.setText("")
        if key not in self.getCategories().keys():
            self.addKeyColorField(key)

    def addKeyColorField(self, key, color=QtGui.QColor("red")):
        self.catFrame.layout().addWidget(ColorField(key, color, parent=self.catFrame))

    def show(self):
        return super().show()

    def onSaveClicked(self):
        self.catColor = self.getCategories()
        self.hide()
        self.editorSaved.emit()

    def closeEvent(self, event):
        # ask user if changes should be saved
        msg_box = QtWidgets.QMessageBox()
        msg_box.setText("Do you want to save changes?")
        msg_box.setStandardButtons(QtWidgets.QMessageBox.Save | QtWidgets.QMessageBox.Discard | QtWidgets.QMessageBox.Cancel)
        msg_box.setDefaultButton(QtWidgets.QMessageBox.Save)
        ret = msg_box.exec()
        if ret == QtWidgets.QMessageBox.Save:
            self.onSaveClicked()
        elif ret == QtWidgets.QMessageBox.Discard:
            self.updateValuesFromZone()
        elif ret == QtWidgets.QMessageBox.Cancel:
            event.ignore()
    ...
