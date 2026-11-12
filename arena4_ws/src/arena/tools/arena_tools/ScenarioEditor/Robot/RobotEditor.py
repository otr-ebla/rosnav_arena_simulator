from PyQt5 import QtGui, QtCore, QtWidgets
import os
import copy
import arena_simulation_setup.entities.robot
from arena_tools.ScenarioEditor.ArenaScenario import *
from arena_tools.utils.QtExtensions import *
from arena_tools.utils.HelperFunctions import *

import arena_simulation_setup.entities.obstacles.dynamic


class RobotAgentEditor(QtWidgets.QWidget):
    editorSaved = QtCore.pyqtSignal()

    def __init__(self, robotAgentWidget=None, **kwargs):
        super().__init__(**kwargs)
        self.robotAgentWidget = robotAgentWidget
        if robotAgentWidget is None:
            self.robotAgent = Pedestrian('Pedestrian 1')
        else:
            self.robotAgent = robotAgentWidget.robotAgent
        self.setup_ui()
        self.updateValuesFromRobotAgent()

    def setup_ui(self):
        self.setWindowTitle("Pedestrian Agent Editor")
        self.setLayout(QtWidgets.QGridLayout())
        self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        self.resize(600, 600)
        self.move(220, 150)

        # scrollarea
        self.scrollArea = QtWidgets.QScrollArea(self)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setMinimumWidth(400)
        self.layout().addWidget(self.scrollArea, 0, 0, 1, -1)
        # frame
        self.scrollAreaFrame = QtWidgets.QFrame()
        self.scrollAreaFrame.setLayout(QtWidgets.QGridLayout())
        self.scrollAreaFrame.setSizePolicy(QtWidgets.QSizePolicy.Policy.Maximum, QtWidgets.QSizePolicy.Policy.Maximum)
        self.scrollAreaFrame.setMinimumWidth(400)
        self.scrollArea.setWidget(self.scrollAreaFrame)

        vertical_idx = 0

        # heading "general"
        general_label = QtWidgets.QLabel("#### General")
        general_label.setTextFormat(QtCore.Qt.TextFormat.MarkdownText)
        self.scrollAreaFrame.layout().addWidget(general_label, vertical_idx, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
        line = Line()
        self.scrollAreaFrame.layout().addWidget(line, vertical_idx, 1, QtCore.Qt.AlignmentFlag.AlignRight)
        vertical_idx += 1

        # name
        # label
        self.nameLabel = QtWidgets.QLabel("Name")
        self.nameLabel.setTextFormat(QtCore.Qt.TextFormat.MarkdownText)
        self.scrollAreaFrame.layout().addWidget(self.nameLabel, vertical_idx, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
        # editbox
        name = self.robotAgentWidget.name_label.text() if self.robotAgentWidget is not None else "global agent"
        self.name_edit = QtWidgets.QLineEdit(name)
        self.name_edit.setFixedSize(200, 30)
        self.scrollAreaFrame.layout().addWidget(self.name_edit, vertical_idx, 1, QtCore.Qt.AlignmentFlag.AlignRight)
        vertical_idx += 1

        # model
        # label
        model_label = QtWidgets.QLabel("Model")
        model_label.setTextFormat(QtCore.Qt.TextFormat.MarkdownText)
        self.scrollAreaFrame.layout().addWidget(model_label, vertical_idx, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
        # dropdown
        self.modelComboBox = QtWidgets.QComboBox()
        for index, agent_model in enumerate(arena_simulation_setup.entities.robot.Robot.list()):
            self.modelComboBox.insertItem(index, agent_model)
        self.modelComboBox.setFixedSize(200, 30)
        self.modelComboBox.currentIndexChanged.connect(self.updateWidgetsFromSelectedModel)
        self.scrollAreaFrame.layout().addWidget(self.modelComboBox, vertical_idx, 1, QtCore.Qt.AlignmentFlag.AlignRight)
        vertical_idx += 1


        # save button
        self.save_button = QtWidgets.QPushButton("Save and Close")
        self.save_button.clicked.connect(self.onSaveClicked)
        self.layout().addWidget(self.save_button, 1, 0, -1, -1)

    def updateValuesFromRobotAgent(self):
        self.modelComboBox.setCurrentText(self.robotAgent.model)
        self.name_edit.setText(self.robotAgent.name)

    def updateWidgetsFromSelectedModel(self):
        ...

    def show(self):
        self.updateValuesFromRobotAgent()
        return super().show()

    def updateRobotAgentFromWidgets(self, agent: Pedestrian):
        agent.model = self.modelComboBox.currentText()
        agent.name = self.name_edit.text()

    def onSaveClicked(self):
        self.updateRobotAgentFromWidgets(self.robotAgent)
        self.hide()
        self.editorSaved.emit()

    def closeEvent(self, event):
        # check if any changes have been made
        current_agent = copy.deepcopy(self.robotAgent)
        self.updateRobotAgentFromWidgets(current_agent)
        if self.robotAgent != current_agent:
            # ask user if changes should be saved
            msg_box = QtWidgets.QMessageBox()
            msg_box.setText("Do you want to save changes to this agent?")
            msg_box.setStandardButtons(QtWidgets.QMessageBox.Save | QtWidgets.QMessageBox.Discard | QtWidgets.QMessageBox.Cancel)
            msg_box.setDefaultButton(QtWidgets.QMessageBox.Save)
            ret = msg_box.exec()
            if ret == QtWidgets.QMessageBox.Save:
                self.onSaveClicked()
            elif ret == QtWidgets.QMessageBox.Discard:
                # reset to values already saved
                self.updateValuesFromRobotAgent()
            elif ret == QtWidgets.QMessageBox.Cancel:
                event.ignore()