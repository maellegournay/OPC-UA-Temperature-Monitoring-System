# OPC UA Monitoring Tool

A Python-based monitoring tool for reading sensor values from an OPC UA server (tested with Prosys OPC UA Simulation Server – Free Version). This tool provides real-time monitoring, alarm management, trend detection, historization, and a web dashboard interface.

## Features

- **OPC UA Connection** to Prosys Simulation Server (anonymous login)
- **Real-time monitoring** of multiple sensors
- **Alarm management** (High, High-High, Low, Low-Low)
- **Trend detection** (rapid rise or fall)
- **Alarm historization** (JSON and CSV formats)
- **Interactive console menu** for simulation control
- **Web dashboard** (Flask and SocketIO) for live updates
- **Dynamic configuration reload** without restart
- **Shutdown and data export** on exit

## Directory Structure

```
├── opcua_monitor.py        # Main Python script
├── config.json             # Configuration file
├── templates/
│   └── index.html          # Web dashboard
├── alarm_history_.json     # Auto-saved alarm history (per run)
└── alarm_history_.csv      # Exported alarm history
```

## Requirements

Install the required Python packages:

```bash
python3 -m pip install opcua flask flask-socketio keyboard
```

Additionally, install the OPC UA Simulation Server (Prosys Free Version).

## Installation & Setup

1. **Install the OPC UA Simulation Server**
   - Download and install Prosys OPC UA Simulation Server (Free Version)
   - Ensure the endpoint is available at: `opc.tcp://localhost:53530/OPCUA/SimulationServer`

2. **Install Python dependencies**
   ```bash
   python3 -m pip install opcua flask flask-socketio keyboard
   ```

3. **Configure sensors and alarms**
   - Edit `config.json` to define your sensors, alarms, and trend settings

## Usage

1. **Start the OPC UA Simulation Server**
   - Launch Prosys OPC UA Simulation Server (Free Version)
   - Verify the endpoint is accessible at: `opc.tcp://localhost:53530/OPCUA/SimulationServer`

2. **Run the monitoring program**
   ```bash
   python3 opcua_monitor.py
   ```

3. **Access the web dashboard**
   - Open your browser and navigate to: `http://localhost:5000`

## Configuration

Sensors, alarms, and trend settings are defined in the `config.json` file. This allows for flexible configuration of monitoring parameters without modifying the source code.

## Important Notes

- **Write limitations**: Writing alarm status back to the OPC UA server is not supported in the Free Version of Prosys Server (read-only access only)
- **macOS compatibility**: On macOS, `keyboard.is_pressed("q")` is not supported. Use `q + ENTER` to stop the simulation
- **Connection resilience**: If the connection is lost, the program automatically attempts reconnection and restores subscriptions

## License

This project is provided as-is for educational and testing purposes.
