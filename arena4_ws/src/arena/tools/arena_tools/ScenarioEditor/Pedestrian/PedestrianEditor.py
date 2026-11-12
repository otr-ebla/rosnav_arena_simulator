from PyQt5 import QtGui, QtCore, QtWidgets
import os
import copy
from arena_tools.ScenarioEditor.ArenaScenario import *
from arena_tools.utils.QtExtensions import *
from arena_tools.utils.HelperFunctions import *
from .Pedestrian import PedestrianAgentType, Pedestrian
import arena_simulation_setup.entities.obstacles.dynamic


class PedestrianAgentEditor(QtWidgets.QWidget):
    editorSaved = QtCore.pyqtSignal()

    def __init__(self, pedestrianAgentWidget=None, **kwargs):
        super().__init__(**kwargs)
        self.pedestrianAgentWidget = pedestrianAgentWidget
        if pedestrianAgentWidget is None:
            self.pedestrianAgent:Pedestrian = Pedestrian('Pedestrian 1')
        else:
            self.pedestrianAgent:Pedestrian = pedestrianAgentWidget.pedestrianAgent
        self.setup_ui()
        self.updateValuesFromPedestrianAgent()

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

        self.vertical_idx = 0

        # heading "general"
        general_label = QtWidgets.QLabel("#### General")
        general_label.setTextFormat(QtCore.Qt.TextFormat.MarkdownText)
        self.scrollAreaFrame.layout().addWidget(general_label, self.vertical_idx, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
        line = Line()
        self.scrollAreaFrame.layout().addWidget(line, self.vertical_idx, 1, QtCore.Qt.AlignmentFlag.AlignRight)
        self.vertical_idx += 1

        # name
        # label
        self.nameLabel = QtWidgets.QLabel("Name")
        self.nameLabel.setTextFormat(QtCore.Qt.TextFormat.MarkdownText)
        self.scrollAreaFrame.layout().addWidget(self.nameLabel, self.vertical_idx, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
        # editbox
        name = self.pedestrianAgentWidget.name_label.text() if self.pedestrianAgentWidget is not None else "global agent"
        self.name_edit = QtWidgets.QLineEdit(name)
        self.name_edit.setFixedSize(200, 30)
        self.scrollAreaFrame.layout().addWidget(self.name_edit, self.vertical_idx, 1, QtCore.Qt.AlignmentFlag.AlignRight)
        self.vertical_idx += 1

        # type
        # label
        type_label = QtWidgets.QLabel("Type")
        type_label.setTextFormat(QtCore.Qt.TextFormat.MarkdownText)
        self.scrollAreaFrame.layout().addWidget(type_label, self.vertical_idx, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
        # dropdown
        self.typeComboBox = QtWidgets.QComboBox()
        for agent_type in PedestrianAgentType:
            self.typeComboBox.insertItem(agent_type.value, agent_type.name.lower())
        self.typeComboBox.setFixedSize(200, 30)
        self.typeComboBox.currentIndexChanged.connect(self.updateWidgetsFromSelectedType)
        self.scrollAreaFrame.layout().addWidget(self.typeComboBox, self.vertical_idx, 1, QtCore.Qt.AlignmentFlag.AlignRight)
        self.vertical_idx += 1

        # model
        # label
        model_label = QtWidgets.QLabel("Model")
        model_label.setTextFormat(QtCore.Qt.TextFormat.MarkdownText)
        self.scrollAreaFrame.layout().addWidget(model_label, self.vertical_idx, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
        # dropdown
        self.modelComboBox = QtWidgets.QComboBox()
        for index, agent_model in enumerate(arena_simulation_setup.entities.obstacles.dynamic.DynamicObstacle.list()):
            self.modelComboBox.insertItem(index, agent_model)
        self.modelComboBox.setFixedSize(200, 30)
        self.modelComboBox.currentIndexChanged.connect(self.updateWidgetsFromSelectedModel)
        self.scrollAreaFrame.layout().addWidget(self.modelComboBox, self.vertical_idx, 1, QtCore.Qt.AlignmentFlag.AlignRight)
        self.vertical_idx += 1

        # custom property scrollarea
        self.cpScrollArea = QtWidgets.QScrollArea(self)
        self.cpScrollArea.setWidgetResizable(True)
        self.cpScrollArea.setMinimumWidth(400)
        self.layout().addWidget(self.cpScrollArea, 1, 0, 1, -1)
        # frame
        self.cpScrollAreaFrame = QtWidgets.QFrame()
        self.cpScrollAreaFrame.setLayout(QtWidgets.QVBoxLayout())
        self.cpScrollAreaFrame.setSizePolicy(QtWidgets.QSizePolicy.Policy.Maximum, QtWidgets.QSizePolicy.Policy.Maximum)
        self.cpScrollAreaFrame.setMinimumWidth(400)
        self.cpScrollArea.setWidget(self.cpScrollAreaFrame)

        # heading "custom_properties"
        self.cp_heading_container = QtWidgets.QWidget()
        self.cp_heading_container.setLayout(QtWidgets.QHBoxLayout())
        custom_properties_label = QtWidgets.QLabel("#### Custom properties")
        custom_properties_label.setTextFormat(QtCore.Qt.TextFormat.MarkdownText)
        self.cp_heading_container.layout().addWidget(custom_properties_label, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
        line = Line()
        self.cp_heading_container.layout().addWidget(line, 1, QtCore.Qt.AlignmentFlag.AlignRight)
        self.cpScrollAreaFrame.layout().addWidget(self.cp_heading_container)
        self.vertical_idx += 1

        # add custom property button
        self.add_custom_property_button = QtWidgets.QPushButton("Add custom property")
        self.add_custom_property_button.clicked.connect(self.onAddCustomPropertyClicked)
        self.cpScrollAreaFrame.layout().addWidget(self.add_custom_property_button, 1, QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.vertical_idx += 1

        # save button
        self.save_button = QtWidgets.QPushButton("Save and Close")
        self.save_button.clicked.connect(self.onSaveClicked)
        self.layout().addWidget(self.save_button, 2, 0, -1, -1)

    def updateWidgetsFromSelectedType(self):
        ...

    def updateValuesFromPedestrianAgent(self):
        self.typeComboBox.setCurrentIndex(PedestrianAgentType[self.pedestrianAgent.type.upper()].value)
        self.modelComboBox.setCurrentText(self.pedestrianAgent.model)

        self.name_edit.setText(self.pedestrianAgent.name)
        # custom properties
        self.custom_properties:list[dict] = copy.deepcopy(self.pedestrianAgent.custom_properties)
        # clear the cpScrollAreaFrame
        if self.cpScrollAreaFrame.layout():
            for idx in range(self.cpScrollAreaFrame.layout().count()):
                item = self.cpScrollAreaFrame.layout().itemAt(idx)
                # self.cpScrollAreaFrame.layout().removeItem(item)
                if item is not None and isinstance(item.widget(), CustomPropertyWidget):
                    self.cpScrollAreaFrame.layout().removeWidget(item.widget())
                    # item.widget().deleteLater()
        
        if len (self.custom_properties) > 0:
            for property in self.custom_properties:
                # name editbox
                property_name = list(property.keys())[0]
                property_value = property.get(property_name)
                self.cpScrollAreaFrame.layout().addWidget(CustomPropertyWidget(self, property_name, property_value))
                self.vertical_idx += 1

    def updateWidgetsFromSelectedModel(self):
        ...

    def show(self):
        self.updateValuesFromPedestrianAgent()
        return super().show()

    def updatePedestrianAgentFromWidgets(self, agent: Pedestrian):
        agent.type = PedestrianAgentType(self.typeComboBox.currentIndex()).name.lower()
        agent.model = self.modelComboBox.currentText()
        agent.name = self.name_edit.text()
        agent.custom_properties = copy.deepcopy(self.custom_properties)

    def onSaveClicked(self):
        self.updatePedestrianAgentFromWidgets(self.pedestrianAgent)
        self.hide()
        self.editorSaved.emit()

    def closeEvent(self, event):
        # check if any changes have been made
        current_agent = copy.deepcopy(self.pedestrianAgent)
        self.updatePedestrianAgentFromWidgets(current_agent)
        if self.pedestrianAgent != current_agent:
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
                self.updateValuesFromPedestrianAgent()
            elif ret == QtWidgets.QMessageBox.Cancel:
                event.ignore()


    def onAddCustomPropertyClicked(self):
        self.addCustomPropertyWidget()

    def addCustomPropertyWidget(self, property_name:Optional[str]="", property_value:Optional[str]="", property_type:Optional[str]="str"):
        w = CustomPropertyWidget(self, property_name, property_value, property_type, parent=self)
        self.cpScrollAreaFrame.layout().addWidget(w, )
        self.custom_properties.append({property_name:property_value})
        self.vertical_idx += 1

    def removeCustomProperty(self, customPropertyWidget: CustomPropertyWidget):
        self.cpScrollAreaFrame.layout().removeWidget(customPropertyWidget)
        for idx, property in enumerate(self.custom_properties):
            property_name = list(property.keys())[0]
            if property_name == customPropertyWidget.property_name:
                self.custom_properties.pop(idx)

        self.vertical_idx -= 1


class PedestrianAgentEditorGlobalConfig(PedestrianAgentEditor):
    """
    A Pedestrian Agent Editor excluding widgets that shouldn't be globally configured
    and without a parent PedestrianAgentWidget.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def setup_ui(self):
        super().setup_ui()
        self.nameLabel.hide()
        self.name_edit.hide()
