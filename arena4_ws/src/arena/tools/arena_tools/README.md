# arena-tools
A collection of tools to make working with [Arena-Rosnav](https://github.com/ignc-research/arena-rosnav/) and [Arena-Rosnav-3D](https://github.com/ignc-research/arena-rosnav-3D/) easier. It currently includes:
- [Scenario Editor](#scenario-editor)
- [Map Generator (2D)](#map-generator)

## Prerequisites
- Python 3.6 or higher

## Installation
Install Python packages (preferably in your virtual environment):
```bash
pip3 install pyqt5 numpy pyyaml lxml scikit-image Pillow scikit-image opencv-python matplotlib
pip install PyQt5 --upgrade
```
If you wish to use our 2D map to 3D Gazebo world functionality follow these 2 additional steps:  
\
Install potrace and imagemagick to convert png/pgm images to SVG format:
```bash
sudo apt-get install potrace imagemagick
```
Install Blender according to [documentation](https://docs.blender.org/manual/en/latest/getting_started/installing/linux.html), making sure that it can be run from the terminal.  
Note: This feature was tested with Blender v3.1
# Run
To start the gui and select your task, run:
```bash
roscd arena-tools && python arena_tools.py
```


# Map Generator
How to create a custom map blueprint like shown here:


https://user-images.githubusercontent.com/74921738/130034174-fa6b334b-e220-47ea-91ba-4bc815663ae5.mov



1. Map Generator is a tool to generate random ROS maps. Firstly select map generator in the *arena-tools* menu. Or run `python MapGenerator.py`

> **NOTE:**
>- Maps can be either an indoor or an outdoor type map. For **indoor** maps you can adjust the **Corridor With** and number of **Iterations**. For **outdoor** maps you can adjust the number of **Obstacles** and the **Obstacle Extra Radius**.
>- Generate maps in bulk by setting **Number of Maps**
>- Each map will be saved in its own folder. Folders will be named like "map[number]". [number] will be incremented starting from the highest number that already exists in the folder, so as not to overwrite any existing maps.

2. If you wish to create Gazebo worlds for all of the generated maps click on the 'Convert existing maps into Gazebo worlds' button, which automates the process, provided you followed the installation steps. Otherwise, you can have a look [here](map_to_gazebo/map_to_gazebo.md) on how to achieve this manually with the help of Blender. Below you can find a short summary

<img src="map_to_gazebo/example-videos/short-map-to-svg.gif">



# Scenario Editor
![](img/scenario_editor.png)
Scenario Editor is a tool to create scenarios for use in Arena-Rosnav. Run it using Python:
```bash
roscd arena-tools && python ArenaScenarioEditor.py
```
### Example Usage


https://user-images.githubusercontent.com/74921738/127912004-4e97af74-b6b8-4501-a463-afbce78a0a13.mov


### General Usage
- Drag the scene or items around by pressing the LEFT mouse button
- Zoom in and out using the mouse scroll wheel
- Select multiple items by drawing a selection rectangle pressing the RIGHT mouse button
- Copy selected items by pressing CTRL+C
- Paste items by pressing CTRL+V
- Delete selected items by pressing DELETE on your keyboard


### Load and Save Scenarios
Click on File->Open or File->Save. Scenarios can be saved in YAML or JSON format, just use the according file ending.

### Set Scenario Map
Click on Elements->Set Map. Select a `map.yaml` file in the format of a typical ROS map (see [map_server Docs](http://wiki.ros.org/map_server#YAML_format)). The map will be loaded into the scene.

### Set Robot initial position and goal
Robot position and goal is always part of a scenario.

### Add Pedestrian Agents

https://user-images.githubusercontent.com/74921738/126493822-88e94f7b-3595-4cce-93cd-df3a8a664607.mov


- Click on Elements->Add Pedestrian Agent. An agent widget will be added on the left and the default Model for Pedestrian Agents will be added to the scene.
- Open the Pedestrian Agent Editor by clicking on Edit or double click the model in the scene. Here you can set the Model, type and all other attributes of your agent.
- Click on 'Add Waypoints...' or select an agent and press CTRL+D to enter Waypoint Mode. Click anywhere in the scene to add a waypoint for this agent. Press ESC or click OK when finished.
