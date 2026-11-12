import pathlib
from PyQt5 import QtGui, QtCore, QtWidgets
import os
import time
import yaml
from typing import Tuple, List, Set
from arena_tools.utils.QtExtensions import *
from arena_tools.utils.HelperFunctions import *
from arena_tools.ZonesEditor.ZonePropertyEditor import *
from arena_tools.ScenarioEditor.ArenaScenarioEditor import RosMapData
import arena_simulation_setup


class PointWidget(QtWidgets.QWidget):
    def __init__(self, polygonWidget, graphicsScene: QtWidgets.QGraphicsScene, posIn: QtCore.QPointF = None, **kwargs):
        super().__init__(**kwargs)
        self.id = 0
        self.polygonWidget = polygonWidget  # needed so the ellipse item can trigger a polygon redraw

        # create circle and add to scene
        self.ellipseItem = PointGraphicsEllipseItem(self, None, None, -0.25, -0.25, 0.5, 0.5)
        self.graphicsScene = graphicsScene
        graphicsScene.addItem(self.ellipseItem)

        # setup widgets
        self.setupUI()
        self.setId(self.id)

        # set initial position
        if posIn is not None:
            self.setPos(posIn)

    def setupUI(self):
        self.setLayout(QtWidgets.QHBoxLayout())
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Maximum, QtWidgets.QSizePolicy.Policy.Maximum)

        # x value
        # label
        label = QtWidgets.QLabel("x")
        self.layout().addWidget(label)
        # spinbox
        self.posXSpinBox = ArenaQDoubleSpinBox()
        self.posXSpinBox.valueChanged.connect(self.updateEllipseItemFromSpinBoxes)
        self.layout().addWidget(self.posXSpinBox)

        # y value
        # label
        label = QtWidgets.QLabel("y")
        self.layout().addWidget(label)
        # spinbox
        self.posYSpinBox = ArenaQDoubleSpinBox()
        self.posYSpinBox.valueChanged.connect(self.updateEllipseItemFromSpinBoxes)
        self.layout().addWidget(self.posYSpinBox)

        # delete button
        deleteButton = QtWidgets.QPushButton("X")
        deleteButton.setFixedWidth(30)
        deleteButton.setStyleSheet("background-color: red")
        deleteButton.clicked.connect(self.remove)
        self.layout().addWidget(deleteButton)

    def setId(self, id: int):
        self.id = id

    def setPos(self, posIn: QtCore.QPointF):
        # set values of spin boxes (and ellipse item)
        # since spin boxes are connected to the ellipse item, the change will be propagated
        self.posXSpinBox.setValue(posIn.x())
        self.posYSpinBox.setValue(posIn.y())

    def getPos(self) -> Tuple[float, float]:
        return self.posXSpinBox.value(), self.posYSpinBox.value()

    def updateEllipseItemFromSpinBoxes(self):
        if not self.ellipseItem.isDragged:  # do this to prevent recursion between spin boxes and graphics item
            x = self.posXSpinBox.value()
            y = self.posYSpinBox.value()
            self.ellipseItem.setPosNoEvent(x, y)  # set without event to prevent recursion between spin boxes and graphics item

    def updateSpinBoxesFromGraphicsItem(self):
        new_pos = self.ellipseItem.mapToScene(self.ellipseItem.transformOriginPoint())
        self.posXSpinBox.setValue(new_pos.x())
        self.posYSpinBox.setValue(new_pos.y())

    def remove(self):
        self.ellipseItem.scene().removeItem(self.ellipseItem)
        del self.ellipseItem.keyPressEater  # delete to remove event filter
        self.parent().layout().removeWidget(self)
        self.polygonWidget.update()
        self.deleteLater()


class PolygonWidget(QtWidgets.QFrame):
    def __init__(self, graphicsScene: QtWidgets.QGraphicsScene, graphicsView: ArenaQGraphicsView, label: str, polygon: shapely.Polygon = None, color: QtGui.QColor = QtGui.QColor(0, 0, 0), **kwargs):
        super().__init__(**kwargs)
        self.graphicsScene = graphicsScene
        self.graphicsView = graphicsView
        self.addWaypointModeActive = False

        self.setupUI()

        graphicsView.clickedPos.connect(self.handleGraphicsViewClick)

        # Label
        self.textItem = QtWidgets.QGraphicsTextItem(label)
        self.textItem.setScale(0.03)
        self.textItem.setZValue(3)
        self.textItem.setDefaultTextColor(QtGui.QColor(255, 0, 0))
        self.textItem.setVisible(False)
        labelpen = QtGui.QPen(QtGui.QColor(0, 0, 255))
        labelpen.setWidthF(0.05)
        labelpen.setStyle(QtCore.Qt.PenStyle.SolidLine)
        labelpen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
        labelpen.setJoinStyle(QtCore.Qt.PenJoinStyle.RoundJoin)
        labelbrush = QtGui.QBrush(QtGui.QColor(255, 255, 255, 144), QtCore.Qt.BrushStyle.SolidPattern)
        self.textRectItem = QtWidgets.QGraphicsRectItem()
        self.textRectItem.setPen(labelpen)
        self.textRectItem.setBrush(labelbrush)
        self.textRectItem.setZValue(2)

        # Polygon for drawing a path connecting the points
        self.polygonDrawItem = QtWidgets.QGraphicsPolygonItem()

        self.setBrush(color)

        pen = QtGui.QPen()
        pen.setColor(QtGui.QColor(65, 143, 154))
        pen.setWidthF(0.1)
        pen.setStyle(QtCore.Qt.PenStyle.SolidLine)
        pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(QtCore.Qt.PenJoinStyle.RoundJoin)
        self.polygonDrawItem.setPen(pen)

        # add to scene
        graphicsScene.addItem(self.polygonDrawItem)
        graphicsScene.addItem(self.textItem)
        graphicsScene.addItem(self.textRectItem)

        if polygon is not None:
            for x, y in polygon.exterior.coords[:-1]:
                self.addPointWidget(QtCore.QPointF(x, y))
        else:
            # setup waypoints
            self.activeModeWindow = ActiveModePointWindow(self)
            self.setAddPointMode(True)

    def setupUI(self):

        self.setLayout(QtWidgets.QVBoxLayout())
        self.layout().setSpacing(0)
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.setFrameStyle(QtWidgets.QFrame.Shape.Box | QtWidgets.QFrame.Shadow.Raised)

    def getPolygon(self) -> shapely.Polygon:
        return shapely.Polygon(self.getPoints())

    def getQPoints(self) -> List[QtCore.QPointF]:
        return [widget.ellipseItem.mapToScene(widget.ellipseItem.transformOriginPoint()) for widget in self.getPointWidgets()]

    def getPoints(self) -> List[Tuple[float, float]]:
        return [(qpoint.x(), qpoint.y()) for qpoint in self.getQPoints()]

    def setLabel(self, text: str):
        self.textItem.setPlainText(text)
        self.drawPolygon()

    def setBrush(self, color: QtGui.QColor):
        color.setAlpha(64)
        brush = QtGui.QBrush(color)
        self.polygonDrawItem.setBrush(brush)

    def drawPolygon(self):
        polygon = QtGui.QPolygonF()

        for point in self.getQPoints():
            polygon.append(point)

        tl = polygon.boundingRect().topLeft()

        self.polygonDrawItem.setPolygon(polygon)

        topLeft = sorted(self.getQPoints(), key=lambda p: QtCore.QPointF.dotProduct(tl - p, tl - p))
        if (topLeft != []):
            self.textItem.setPos(topLeft[0])
            self.textItem.setY(self.textItem.y() - 0.5)
            self.textItem.setX(self.textItem.x() + 0.3)
            self.textRectItem.setRect(self.textItem.sceneBoundingRect())

    def handleGraphicsViewClick(self, pos: QtCore.QPointF):
        if self.addWaypointModeActive:
            self.addPointWidget(pos)

    def addPointWidget(self, pos: QtCore.QPointF = None):
        w = PointWidget(self, self.graphicsScene, pos, parent=self)
        self.layout().addWidget(w)
        self.update()

    def removePoint(self, pointWidget: PointWidget):
        self.layout().removeWidget(pointWidget)
        self.update()

    def setAddPointMode(self, enable: bool):
        self.addWaypointModeActive = enable
        if enable:
            self.activeModeWindow.show()
        else:
            self.activeModeWindow.hide()
            self.update()

    def getPointWidgets(self) -> List[PointWidget]:
        widgets = []
        for i in range(self.layout().count()):
            w = self.layout().itemAt(i).widget()
            if w is not None:
                widgets.append(w)
        return widgets

    def handleItemChange(self):
        # function will be called by the graphics item
        self.update()

    def update(self):
        widgets = self.getPointWidgets()
        if len(widgets) == 0:
            self.remove()
        self.textItem.setVisible(True)
        for i, w in enumerate(widgets):
            w.setId(i)
        self.drawPolygon()

    def remove(self):
        # remove waypoints
        for w in self.getPointWidgets():
            w.remove()

        # remove items from scene
        self.graphicsScene.removeItem(self.polygonDrawItem)
        self.graphicsScene.removeItem(self.textItem)
        self.graphicsScene.removeItem(self.textRectItem)
        # remove widget
        self.parent().layout().removeWidget(self)

        self.deleteLater()


class ZoneWidget(QtWidgets.QFrame):
    '''
    This is a row in the obstacles frame.
    '''

    def __init__(self, zone: Zone, graphicsScene: QtWidgets.QGraphicsScene, graphicsView: ArenaQGraphicsView, catEditor: CategoriesEditor, **kwargs):
        super().__init__(**kwargs)
        self.zone = zone

        self.graphicsScene = graphicsScene
        self.graphicsView = graphicsView

        self.catEditor = catEditor
        self.catEditor.editorSaved.connect(self.handleEditorSaved)

        self.zoneEditor = ZonePropertyEditor(zone, parent=self.parent(), flags=QtCore.Qt.WindowType.Window)
        self.zoneEditor.editorSaved.connect(self.handleEditorSaved)

        self.color = None

        # setup widgets
        self.setupUI()

        for polygon in zone.polygon.geoms:
            self.addPolygonWidget(polygon)

    def setupUI(self):
        self.setLayout(QtWidgets.QGridLayout())
        self.setMinimumWidth(275)
        self.setFrameStyle(QtWidgets.QFrame.Shape.Box | QtWidgets.QFrame.Shadow.Raised)

        # name label
        self.nameLabel = QtWidgets.QLabel(self.zone.label)
        self.layout().addWidget(self.nameLabel, 0, 0)

        # edit button
        self.editButton = QtWidgets.QPushButton("Edit")
        self.editButton.clicked.connect(self.onEditClicked)
        self.layout().addWidget(self.editButton, 0, 1)

        # delete button
        self.deleteButton = QtWidgets.QPushButton("Delete")
        self.deleteButton.clicked.connect(self.onDeleteClicked)
        self.layout().addWidget(self.deleteButton, 0, 2)

        # waypoints
        label = QtWidgets.QLabel("Polygons:")
        self.layout().addWidget(label, 2, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
        button = QtWidgets.QPushButton("Add Polygons...")
        button.clicked.connect(self.onAddPolygonClicked)
        self.layout().addWidget(button, 2, 1, 1, 2)
        self.polygonListWidget = QtWidgets.QWidget()
        self.polygonListWidget.setLayout(QtWidgets.QVBoxLayout())
        self.polygonListWidget.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(self.polygonListWidget, 3, 0, -1, 3)

    def getPolygonWidgets(self) -> List[PolygonWidget]:
        widgets = []
        for i in range(self.polygonListWidget.layout().count()):
            w = self.polygonListWidget.layout().itemAt(i).widget()
            if w is not None:
                widgets.append(w)
        return widgets

    def handleEditorSaved(self):
        # editor was saved, update possibly changed values
        self.update()

    def handleMouseDoubleClick(self):
        # function will be called by the graphics item
        self.onEditClicked()

    def update(self):
        self.nameLabel.setText(self.zone.label)

        catColor = self.catEditor.getCategories()
        if self.zone.category != []:
            self.color = catColor[self.zone.category[0]]

        for w in self.getPolygonWidgets():
            if self.zone.category != []:
                w.setBrush(self.color)
            w.setLabel(self.zone.label)

        self.zone.polygon = shapely.MultiPolygon([w.getPolygon() for w in self.getPolygonWidgets()])

    def addPolygonWidget(self, polygon: shapely.Polygon = None):
        if self.color:
            w = PolygonWidget(self.graphicsScene, self.graphicsView, self.zone.label, polygon, self.color, parent=self)
        else:
            w = PolygonWidget(self.graphicsScene, self.graphicsView, self.zone.label, polygon, parent=self)
        self.polygonListWidget.layout().addWidget(w)

    def remove(self):
        # remove polygons
        for w in self.getPolygonWidgets():
            w.remove()
        self.parent().layout().removeWidget(self)
        self.deleteLater()

    def onDeleteClicked(self):
        self.remove()

    def onAddPolygonClicked(self):
        self.addPolygonWidget()

    def onEditClicked(self):
        self.zoneEditor.show()

    def disableWaypointMode(self):
        for w in self.getPolygonWidgets():
            w.setAddPointMode(False)


class ZonesEditor(QtWidgets.QMainWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.numZones = 0
        self.pixmapItem = None
        self.mapData = None
        self.zoneData = ZonesData()
        self.currentDirectory = ""
        self.currentSaveFile = ""

        self.setupUI()
        QtCore.QTimer.singleShot(0, self.show_select_world_dialog)

    def show_select_world_dialog(self):
        dialog = ComboBoxDialog(
            self, 
            combo_box_items=arena_simulation_setup.world.World.list(),
            window_title="Choose world",
            label="Please select a world:"
        )
        result = dialog.exec_()  # Modal dialog, execution pauses here

        if result == QtWidgets.QDialog.Accepted:
            selected_world = dialog.get_selected_option()
            print(f"User selected: {selected_world}")
            self.statusBar().showMessage(f"Selected: {selected_world}")

            self.selected_world = selected_world
            path = pathlib.Path(arena_simulation_setup.world.World(self.selected_world).map.path) / "map.yaml"
            if path.is_file():
                self.setMap(str(path))
            
        else:
            print("Dialog was rejected or closed unexpectedly.")

    def setupUI(self):
        self.updateWindowTitle()
        self.resize(1300, 700)
        self.move(100, 100)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap('icon.png'), QtGui.QIcon.Selected, QtGui.QIcon.On)
        self.setWindowIcon(icon)

        # set central widget
        centralWidget = QtWidgets.QWidget()
        centralWidget.setLayout(QtWidgets.QGridLayout())
        self.setCentralWidget(centralWidget)

        # menu bar
        menubar = self.menuBar()
        fileMenue = menubar.addMenu("File")
        fileMenue.addAction("New...", self.onNewScenarioClicked, "Ctrl+N")
        fileMenue.addAction("Open...", self.onOpenClicked, "Ctrl+O")
        fileMenue.addAction("Load Zones", self.onLoadZonesClicked, "Ctrl+L")
        fileMenue.addAction("Save...", self.onSaveClicked, "Ctrl+S")
        fileMenue.addAction("Save As...", self.onSaveAsClicked, "Ctrl+Shift+S")
        fileMenue.addAction("Load Map...", self.onLoadMapClicked, "Ctrl+M")
        fileMenue.addAction("Export as PNG", self.onExportClicked, "Ctrl+E")
        fileMenue.addAction("Exit", self.close)

        elementMenue = menubar.addMenu("Elements")
        elementMenue.addAction("Add new Zone", self.onAddZoneClicked, "Ctrl+T")
        elementMenue.addAction("Edit categories", self.onEditCategoriesClicked, "Ctrl+G")

        # status bar
        self.statusBar()  # create status bar

        # categories
        self.catEditor = CategoriesEditor(self.zoneData, parent=self, flags=QtCore.Qt.WindowType.Window)
        self.catEditor.editorSaved.connect(self.updateCategories)

        # drawing frame
        # frame
        drawingFrame = QtWidgets.QFrame()
        drawingFrame.setLayout(QtWidgets.QVBoxLayout())
        drawingFrame.setFrameStyle(QtWidgets.QFrame.Shape.Box | QtWidgets.QFrame.Shadow.Raised)
        self.centralWidget().layout().addWidget(drawingFrame, 0, 1, -1, -1)
        # graphicsscene
        self.gscene = ArenaQGraphicsScene()
        # graphicsview
        self.gview = ArenaQGraphicsView(self.gscene)
        self.gview.scale(0.25, 0.25)  # zoom out a bit
        drawingFrame.layout().addWidget(self.gview)

        # zones
        # scrollarea
        self.scrollarea = QtWidgets.QScrollArea(self)
        self.scrollarea.setWidgetResizable(True)
        self.scrollarea.setMinimumWidth(310)
        self.centralWidget().layout().addWidget(self.scrollarea, 0, 0, 1, 1)
        # frame
        self.widgetFrame = QtWidgets.QFrame()
        self.widgetFrame.setLayout(QtWidgets.QVBoxLayout())
        self.widgetFrame.setSizePolicy(QtWidgets.QSizePolicy.Policy.Maximum, QtWidgets.QSizePolicy.Policy.Maximum)
        self.scrollarea.setWidget(self.widgetFrame)
        # button
        self.addZoneButton = QtWidgets.QPushButton("Add new Zone")
        self.addZoneButton.pressed.connect(self.onAddZoneClicked)
        self.centralWidget().layout().addWidget(self.addZoneButton, 1, 0, -1, 1)

        self.updateCategories()

    def onEditCategoriesClicked(self):
        self.catEditor.show()

    def onAddZoneClicked(self):
        self.addZoneWidget()

    def addZoneWidget(self, zone: Zone = None):
        '''
        Adds a new ZoneWidget with the given Zone
        '''
        w = ZoneWidget(zone if zone is not None else Zone("Zone {0}".format(self.numZones)), self.gscene, self.gview, self.catEditor, parent=self)
        self.widgetFrame.layout().addWidget(w)
        self.numZones += 1
        self.updateCategories()

    def getZoneWidgets(self) -> List[ZoneWidget]:
        widgets = []
        for i in range(self.widgetFrame.layout().count()):
            w = self.widgetFrame.layout().itemAt(i).widget()
            widgets.append(w)
        return widgets

    def updateCategories(self):
        for w in self.getZoneWidgets():
            w.zoneEditor.category = list(self.catEditor.getCategories().keys())

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        if event.key() == QtCore.Qt.Key.Key_Escape or event.key() == QtCore.Qt.Key.Key_Return:
            self.disableAddWaypointMode()

        return super().keyPressEvent(event)

    def disableAddWaypointMode(self):
        widgets = self.getZoneWidgets()
        for w in widgets:
            w.disableWaypointMode()

    #####

    def onNewScenarioClicked(self):
        self.currentDirectory = ""
        self.currentSaveFile = ""
        self.gscene.removeItem(self.pixmapItem)
        self.loadZones("")
        self.updateWindowTitle()

    def onOpenClicked(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(parent=self, options=QtWidgets.QFileDialog.ShowDirsOnly)
        if path != "":
            if os.path.exists(path + "/map/map.yaml"):
                self.setMap(path + "/map/map.yaml")
                self.currentDirectory = path
                if os.path.exists(path + "/map/zones.yaml"):
                    self.loadZones(path + "/map/zones.yaml")
                msg = f"[Opened world in {path}]"
                self.statusBar().showMessage(msg, 10 * 1000)
                self.updateWindowTitle()
            else:
                msg = f"[Could not open world in {path}]"
                self.statusBar().showMessage(msg, 10 * 1000)

    def onExportClicked(self):
        image = QtGui.QImage(self.gview.viewport().rect().size(), QtGui.QImage.Format_ARGB32_Premultiplied)
        painter = QtGui.QPainter(image)
        self.gview.render(painter, QtCore.QRectF(self.gview.viewport().rect()), QtCore.QRect(0, 0, 0, 0))
        painter.end()
        res = QtWidgets.QFileDialog.getSaveFileName(parent=self, directory=self.currentDirectory + ("/photos" if self.currentDirectory else ""), filter="Image (*.png)")
        path = res[0]
        if path != "":
            image.save(path)
            msg = f"[Saved image in {path}"
            self.statusBar().showMessage(msg, 10 * 1000)

    def onLoadMapClicked(self):
        self.show_select_world_dialog()

    def onLoadZonesClicked(self):
        res = QtWidgets.QFileDialog.getOpenFileName(parent=self, filter="YAML File (*.yaml)")
        path = res[0]
        if path != "":
            self.loadZones(path)
            self.updateWindowTitle()

    def onSaveClicked(self) -> bool:
        if self.currentDirectory:
            if self.currentSaveFile:
                return self.save(self.currentDirectory + "/" + self.currentSaveFile)
        self.onSaveAsClicked()

    def onSaveAsClicked(self) -> bool:
        path = pathlib.Path(arena_simulation_setup.world.World(self.selected_world).map.zones)
        if path!= "":
            self.statusBar().showMessage(f"Saved at: {str(path)}")
            return self.save(str(path))

        return False

    #####

    def setMap(self, path: str):
        self.mapData = RosMapData(path)
        pixmap = QtGui.QPixmap(self.mapData.image_path)
        transform = QtGui.QTransform.fromScale(1.0, -1.0)  # flip y axis
        pixmap = pixmap.transformed(transform)
        if self.pixmapItem is not None:
            self.gscene.removeItem(self.pixmapItem)        # remove old map
        self.pixmapItem = QtWidgets.QGraphicsPixmapItem(pixmap)
        self.pixmapItem.setZValue(-1.0)  # make sure map is always in the background
        self.pixmapItem.setScale(self.mapData.resolution)
        self.pixmapItem.setOffset(self.mapData.origin[0] / self.mapData.resolution, self.mapData.origin[1] / self.mapData.resolution)
        self.gscene.addItem(self.pixmapItem)

    def loadZones(self, path: str):
        self.zoneData = ZonesData(path)
        if path != "":
            self.currentSaveFile = path.rsplit("/", 1)[1]

        for widget in self.getZoneWidgets():
            widget.remove()

        for zone in self.zoneData.zones:
            self.addZoneWidget(zone)

        self.catEditor.updateValuesFromZone(self.zoneData)
        self.updateCategories()

    def save(self, path: str = "") -> bool:
        self.updateZoneFromWidgets()

        if self.zoneData.saveToFile(path):
            msg = f"[Saved zones to {self.zoneData.path}]"
            self.statusBar().showMessage(msg, 10 * 1000)
            return True

        return False

    def updateZoneFromWidgets(self):
        '''
        Save data from widgets into self.zoneData
        '''
        self.zoneData.zones = []
        for w in self.getZoneWidgets():
            w.update()
            self.zoneData.zones.append(w.zone)

    def updateWindowTitle(self):
        self.setWindowTitle(((self.currentDirectory.rsplit("/", 1)[1] + " - ") if self.currentDirectory else "") + (self.currentSaveFile + " - " if self.currentSaveFile else "") + "Zones Editor")


