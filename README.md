This project is a Python-based monitoring tool for reading sensor values from an OPC UA server (tested with Prosys OPC UA Simulation Server – Free Version). It supports real-time monitoring, alarm management, trend detection, historization, and a web dashboard.

It features:
	•	OPC UA Connection to Prosys Simulation Server (anonymous login).
	•	Real-time monitoring of multiple sensors.
	•	Alarm management (High, High-High, Low, Low-Low).
	•	Trend detection (rapid rise or fall).
	•	Alarm historization (JSON and CSV).
	•	Interactive console menu for simulation control.
	•	Web dashboard (Flask and SocketIO) for live updates.
	•	Dynamic configuration reload without restart.
	•	Shutdown and data export on exit.

Directory structure: 
├── opcua_monitor.py 		# Main Python script 
├── config.json 			# Configuration file 
├── templates/ 
│ └── index.html 			# Web dashboard 
├── alarm_history_.json 	# Auto-saved alarm history (per run) 
├── alarm_history_.csv 		# Exported alarm history

Requirement: python3 -m pip install opcua flask flask-socketio keyboard install the opc ua simulation server (here Prosys free version).

To run the program on the monitor: python3 opcua_monitor.py

Usage:
	1	Start the OPC UA Simulation Server Use Prosys OPC UA Simulation Server (Free Version). Ensure the endpoint is available at: opc.tcp://localhost:53530/OPCUA/SimulationServer
	2	Run the monitoring program: python3 opcua_monitor.py
	3	Access the dashboard Open your browser at: http://localhost:5000

Sensors, alarms, and trend settings are defined in a JSON file.

Notes:
	•	Writing alarm status back to OPC UA server is not supported in the Free Version of Prosys Server (read-only).
	•	On macOS, keyboard.is_pressed("q") is not supported → must use q + ENTER to stop simulation.
	•	If connection is lost, the program attempts automatic reconnection and restores subscriptions.
