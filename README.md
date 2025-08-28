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

### Example Configuration

```json
{
  "server": {
    "endpoint": "opc.tcp://localhost:53530/OPCUA/SimulationServer",
    "timeout": 30,
    "reconnect_interval": 5
  },
  "sensors": [
    {
      "id": "Temperature",
      "node_id": "ns=3;i=1001",
      "name": "Temperature Sensor",
      "unit": "°C",
      "alarms": {
        "low_low": 10,
        "low": 15,
        "high": 35,
        "high_high": 40
      },
      "trend": {
        "window_size": 10,
        "rapid_threshold": 5.0
      }
    }
  ],
  "monitoring": {
    "sample_interval": 1000,
    "publish_interval": 500
  }
}
```

## Important Notes

- **Write limitations**: Writing alarm status back to the OPC UA server is not supported in the Free Version of Prosys Server (read-only access only)
- **macOS compatibility**: On macOS, `keyboard.is_pressed("q")` is not supported. Use `q + ENTER` to stop the simulation
- **Connection resilience**: If the connection is lost, the program automatically attempts reconnection and restores subscriptions

## Troubleshooting

### Connection Issues
- Verify the OPC UA server is running
- Check the endpoint URL in `config.json`
- Ensure no firewall is blocking the connection

### Permission Errors
- On Linux/macOS, you may need to run with appropriate permissions for keyboard input
- Consider running without keyboard module if not needed

### Performance Optimization
- Adjust `sample_interval` and `publish_interval` in configuration
- Reduce the number of monitored sensors if experiencing lag
- Check system resources (CPU, memory usage)

## License

This project is provided as-is for educational and testing purposes.

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## Support

For issues related to:
- **Prosys OPC UA Server**: Consult the Prosys documentation
- **Python opcua library**: Check the python-opcua GitHub repository
- **This monitoring tool**: Open an issue in this repository