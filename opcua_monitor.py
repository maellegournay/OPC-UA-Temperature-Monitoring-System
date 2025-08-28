                                                                 # OPC UA Sensor Monitoring with interactive menu
                                                                # Prosys OPC UA Simulation Server (Free Version)

from opcua import Client
from opcua import ua
from datetime import datetime, timezone
from collections import deque
from statistics import mean
from opcua import Client, ua
from flask import Flask, render_template
from flask_socketio import SocketIO
import time
import json
import csv
import math
import os
import threading
import keyboard

# Flask & SocketIO setup
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

@app.route("/")
def index():
    return render_template("index.html")

# OPC UA Configuration
ENDPOINT = "opc.tcp://localhost:53530/OPCUA/SimulationServer"
MAX_RETRIES = 20
RETRY_DELAY = 3 # s
MIN_SCANRATE = 100 # ms
MAX_SCANRATE = 10000 # ms
    
# Global flag
stop_monitoring = False
exit_program = False

# Global variables
sensors = []
alarm_settings = {}
buffers = {}
states = {}
alarm_history = {}
TIME_DELAY = 0
file_path = ""
DECIMALS =2
last_values = {}
prev_values = {}
trend_settings = {"rise_rate": 1.0, "fall_rate": -1.0}


        # === Utility functions ===

# Function to have the timestamp ISO 8601
def iso(ts: datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

# Convert to float when possible
def normalize_number(val):
    try:
        if isinstance(val, bool):
            return float(val)
        return float(val)
    except Exception:
        return None

# Give the good number of decimals for the temperature measures
def fmt_num(x):
    try:
        if isinstance(x, (int, float)) and math.isfinite(x):
            return f"{x:.{DECIMALS}f}"
        return str(x)
    except Exception:
        return str(x)

# Function to have the alarm history in a new JSON file
def write_alarm_history():
    global alarm_history, file_path
    try:
        with open(file_path, "w") as f:
            json.dump(alarm_history, f, indent=4)
    except Exception as e:
        print(f"iso(datetime.now(timezone.utc))Failed to write alarm history: {e}")


        # === Alarm detection ===

# Monitoring of the alarms (ALARM_ACTIVE and (ALARM_CLEAR)
def emit_event(event_type, sensor, level, value, threshold, now_ts, started_at=None):
    global alarm_history, alarm_settings
    PRIORITY = {"LL": 4, "HH": 3, "L": 2, "H": 1}
    payload = {
        "timestamp": iso(now_ts),
        "sensor": sensor["name"],
        "nodeId": sensor["nodeId"],
        "type": level,
        "priority": PRIORITY[level],
        "value": fmt_num(value),
        "threshold": threshold,
        "duration": None,
        "active": event_type == "ALARM_ACTIVE",
        "acknowledged": False
    }

    if event_type == "ALARM_CLEAR" and started_at is not None:
        duration_sec = max(0, (now_ts - started_at).total_seconds())
        payload["duration"] = round(duration_sec, 3)
        for alarm in reversed(alarm_history["alarms"]):
            if alarm["sensor"] == sensor["name"] and alarm["type"] == level and alarm["active"]:
                alarm["active"] = False
                alarm["duration"] = payload["duration"]
                break
        alarm_history["statistics"]["active_alarms"] = sum(1 for a in alarm_history["alarms"] if a["active"])
    else:
        alarm_history["alarms"].append(payload)
        alarm_history["statistics"]["total_alarms"] += 1
        alarm_history["statistics"]["active_alarms"] += 1
        alarm_history["statistics"]["by_type"][level] += 1

    print(f"\n[ALARM-{event_type}] {json.dumps(payload)}\n", flush=True)
    notification_node = alarm_settings.get("notificationNode")
    if notification_node:
       print(f"{iso(datetime.now(timezone.utc))} | Skipping write of alarm status to {notification_node} (read-only in Prosys Free).\n")
    write_alarm_history()

    try:
        socketio.emit("alarm", payload)
    except Exception as e:
        print(f"{iso(datetime.now(timezone.utc))} | Failed to emit alarm: {e}")

# Definition of the different alarm levels from the config file
def check_levels(sensor, value, now_ts):
    global states, TIME_DELAY
    name = sensor["name"]
    db = float(sensor.get("deadband", 0.0))
    alarms = sensor.get("alarms", {})

    th = {
        "HH": alarms.get("high_high"),
        "H":  alarms.get("high"),
        "L":  alarms.get("low"),
        "LL": alarms.get("low_low"),
    }

    # Which alarm is active?
    def process(level, is_high_side):
        st = states[name][level]
        thr = th[level]
        if thr is None:
            return

        if is_high_side:
            cond_active = (value is not None) and (value >= float(thr))
            cond_clear  = (value is not None) and (value <= float(thr) - db)
        else:
            cond_active = (value is not None) and (value <= float(thr))
            cond_clear  = (value is not None) and (value >= float(thr) + db)

        if st["active"]:
            if cond_clear:
                emit_event("ALARM_CLEAR", sensor, level, value, thr, now_ts, started_at=st["started_at"])
                st["active"] = False
                st["pending_since"] = None
                st["started_at"] = None
                return

        if cond_active:
            if st["pending_since"] is None:
                st["pending_since"] = now_ts
            if (now_ts - st["pending_since"]).total_seconds() >= TIME_DELAY:
                st["active"] = True
                st["started_at"] = now_ts
                emit_event("ALARM_ACTIVE", sensor, level, value, thr, now_ts)
        else:
            st["pending_since"] = None

    process("H", True)
    process("HH", True)
    process("L", False)
    process("LL", False)


        # === Bonus challenges ===

# Alarm acknowledgement (locally) - not functional with the Free version, only the logic is written
def acknowledge_alarm(alarm_index, client=None, comment="Acknowledge via client"):
    global alarm_history
    try:
        alarm = alarm_history["alarms"][alarm_index]
    except IndexError:
        print(f"{iso(datetime.now(timezone.utc))} | Invalid alarm index")
        return

    if alarm["acknowledged"]:
        print(f"{iso(datetime.now(timezone.utc))} | Alarm {alarm_index} already acknowledged.")
        return

    actual_index = alarm_index + 1
    nodeID = alarm["nodeId"]

    # OPC UA method call
    if client:
        try:
            condition_node = client.get_node(nodeID)
            acknowledge_method = condition_node.get_child("0:Acknowledge")

            event_id = ua.Variant(alarm["timestamp"].encode(), ua.VariantType.ByteString)
            comment_val = ua.Variant(comment, ua.VariantType.LocalizedText)

            result = condition_node.call_method(acknowledge_method, event_id, comment_val)
            print(f"{iso(datetime.now(timezone.utc))} | Acknowledge method result: {result}")

        except Exception as e:
            print(f"{iso(datetime.now(timezone.utc))} | Server acknowledgment not supported, marking locally. Reason: {e}")

    # Update local history regardless
    alarm["acknowledged"] = True
    write_alarm_history()
    print(f"{iso(datetime.now(timezone.utc))} | Alarm {actual_index} acknowledged (locally).")

#Trend detection
def check_trend(sensor, value, now_ts):
    global last_values, trend_settings, prev_values
    name = sensor["name"]

    # Skip non-numeric values
    if value is None or not isinstance(value, (int, float)):
        return

    if name in last_values:
        prev_val, prev_ts = prev_values[name]
        if prev_ts is not None:
            dt = (now_ts - prev_ts).total_seconds() 
            if dt > 0:
                rate = (value - prev_val) / dt
                if rate >= trend_settings["rise_rate"]:
                    print(f"{iso(datetime.now(timezone.utc))} | [TREND] {name}: Rapid rise detected (rate={rate:.2f} per sec)\n")
                elif rate <= trend_settings["fall_rate"]:
                    print(f"{iso(datetime.now(timezone.utc))} | [TREND] {name}: Rapid fall detected (rate={rate:.2f} per sec)\n")

    # store current value for next calculation
    last_values[name] = (value, now_ts)

# Export alarm history to CSV format
def export_alarm_history_csv():
    global alarm_history, file_path
    if not alarm_history.get("alarms"):
        print("No alarm history to export.\n")
        return

    # CSV file path - same as json
    csv_path = os.path.splitext(file_path)[0] + ".csv"

    try:
        with open(csv_path, mode='w', newline='') as csvfile:
            fieldnames = ["timestamp", "sensor", "nodeId", "type", "priority", "value", "threshold", "duration", "active", "acknowledged"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for alarm in alarm_history["alarms"]:
                writer.writerow(alarm)

        print(f"Alarm history exported to CSV: {csv_path}")
    except Exception as e:
        print(f"Failed to export CSV: {e}")
        

        # === Subscription handler ===

# Handle data change notifications from server
class SubHandler:
    def datachange_notification(self, node, val, data):
        global stop_monitoring, buffers
        if stop_monitoring:
            return

        sensor = next((s for s in sensors if s["nodeId"] == node.nodeid.to_string()), None)
        if not sensor:
            return

        src_ts = getattr(getattr(data, "monitored_item", None), "Value", None)
        src_ts = getattr(src_ts, "SourceTimestamp", None)
        now_ts = src_ts if isinstance(src_ts, datetime) else datetime.now(timezone.utc)

        num = normalize_number(val)
        if num is not None:
            buffers[sensor["name"]].append(num)
        else:
            print(f"{iso(datetime.now(timezone.utc))} | [WARNING] Invalid data type received for {sensor['name']}: {val} ({type(val).__name__})")
            return
        
        numeric_values = list(buffers[sensor["name"]])
        if numeric_values:
            min_val = min(numeric_values)
            max_val = max(numeric_values)
            avg_val = mean(numeric_values)
            print(
                f"{iso(datetime.now(timezone.utc))} | {sensor['name']} = {fmt_num(val)} {sensor.get('unit','')} | "
                f"Min: {fmt_num(min_val)}, Max: {fmt_num(max_val)}, Avg: {fmt_num(avg_val)} "
                f"(buffer {len(numeric_values)}/{buffers[sensor['name']].maxlen})",
                flush=True
            )
            last_val, last_ts = last_values.get(sensor["name"], (None, None))
            prev_values[sensor["name"]] = (last_val, last_ts)
            if num is not None:
                last_values[sensor["name"]] = (num, now_ts)

            try:
                socketio.emit("update",{s:v[0] for s,v in last_values.items()})
            except Exception as e:
                print(f"{iso(datetime.now(timezone.utc))} | Failed live emit: {e}.\n")
                
            if num is not None:
                check_trend(sensor, num, now_ts)
                check_levels(sensor, num, now_ts)
        else:
            print(f"{iso(now_ts)} | {sensor['name']} = {val} {sensor.get('unit','')}", flush=True)


        # === Connect to OPC UA server ===

# Connect to OPC UA with a retry logic
def connect_to_opcua():
    client = Client(ENDPOINT)
    print(f"{iso(datetime.now(timezone.utc))} | Anonymous connection enabled.")
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            client.connect()
            print(f"{iso(datetime.now(timezone.utc))} | Successfully connected to {ENDPOINT}.")
            return client
        except Exception as e:
            print(f"{iso(datetime.now(timezone.utc))} | Connection failed (attempt {attempt}/{MAX_RETRIES}): {e}")
            time.sleep(RETRY_DELAY)
    print(f"{iso(datetime.now(timezone.utc))} | Unable to connect after multiple attempts.")
    return None

# Reconection to OPC UA
def reconnect(client):
    print(f"{iso(datetime.now(timezone.utc))} | Attempting reconnect.")
    try:
        client.disconnect()
    except:
        pass
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            new_client = Client(ENDPOINT)
            new_client.connect()
            print(f"{iso(datetime.now(timezone.utc))} | Reconnected to {ENDPOINT} (attempt {attempt}).\n")
            return new_client
        except Exception as e:
            print(f"{iso(datetime.now(timezone.utc))} | Reconnect failed (attempt {attempt}/{MAX_RETRIES}): {e}\n")
            time.sleep(RETRY_DELAY)
    print(f"{iso(datetime.now(timezone.utc))} | Reconnect failed after max retries.\n")
    return None


        # === Load configuration JSON ===

# Load the configuration file when 2 is entered in the menu
def load_config_json():
    global sensors, alarm_settings, TIME_DELAY, buffers, states, alarm_history, trend_settings
    path = "./config.json"  # fixed path

    try:
        with open(path, "r") as f:
            try:
                config = json.load(f)
            except json.JSONDecodeError as jde:
                print(f"{iso(datetime.now(timezone.utc))} | Malformed JSON in configuration file '{path}: {jde}")
                return
            
        sensors = config["sensors"]
        if not sensors:
            print(f"{iso(datetime.now(timezone.utc))} | No sensors found in configuration file '{path}'.")
            return

        alarm_settings = config.get("alarmSettings", {})
        TIME_DELAY = int(alarm_settings.get("timeDelay", 0))
        trend_cfg = config.get("trendSettings", {})
        trend_settings["rise_rate"] = float(trend_cfg.get("riseRate", trend_settings["rise_rate"]))
        trend_settings["fall_rate"] = float(trend_cfg.get("fallRate", trend_settings["fall_rate"]))
        
        # Clamp scanRate and print warnings
        for sensor in sensors:
            default_rate = sensor.get("scanRate", MIN_SCANRATE)
            final_rate = default_rate
            if final_rate > MAX_SCANRATE:
                print(f"\nWarning: {sensor['name']} requested scan rate {final_rate}ms exceeds MAX_SCANRATE ({MAX_SCANRATE}ms). Clamping to maximum.\n")
            if final_rate < MIN_SCANRATE:
                print(f"\nWarning: {sensor['name']} requested scan rate {final_rate}ms is below MIN_SCANRATE ({MIN_SCANRATE}ms). Clamping to minimum.\n")
            sensor["scanRate"] = max(MIN_SCANRATE, min(final_rate, MAX_SCANRATE))
            print(f"Sensor: {sensor['name']}, NodeId: {sensor['nodeId']}, ScanRate: {sensor['scanRate']}ms")

        # Initialize buffers and states
        buffers.clear()
        states.clear()
        for sensor in sensors:
            samples = math.ceil(5 * 60 * 1000 / sensor.get("scanRate", MIN_SCANRATE))
            buffers[sensor["name"]] = deque(maxlen=samples)
        levels = ("HH", "H", "L", "LL")
        states.update({s["name"]: {lvl: {"active": False, "pending_since": None, "started_at": None} for lvl in levels} for s in sensors})

        # Initialize alarm history
        alarm_history.clear()
        alarm_history.update({
            "alarms": [],
            "statistics": {"total_alarms": 0, "active_alarms": 0, "by_type": {"HH":0,"H":0,"L":0,"LL":0}}
        })

        print(f"{iso(datetime.now(timezone.utc))} | Configuration loaded from {path}")

    except FileNotFoundError:
        print(f"{iso(datetime.now(timezone.utc))} | Configuration file '{path}' not found.")

    except Exception as e:
        print(f"{iso(datetime.now(timezone.utc))} | Failed to load configuration: {e}")


        # === Run simulation ===

# Run the simulation when 1 is entered in the menu 
def run_simulation():
    global stop_monitoring, file_path

    if not sensors:
        print(f"{iso(datetime.now(timezone.utc))} | No configuration loaded. Loading default config.json.")
        load_config_json()

    stop_monitoring = False
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.expanduser(f"~/Downloads/alarm_history_{timestamp_str}.json")

    client = connect_to_opcua()
    if not client:
        return

    def print_initial_values(client):
        for sensor in sensors:
            try:
                node = client.get_node(sensor["nodeId"])
                val = node.get_value()
                num = normalize_number(val)
                buffers[sensor['name']].append(num if num is not None else val)
                numeric_values = [x for x in buffers[sensor['name']] if isinstance(x,(int,float)) and math.isfinite(x)]
                if numeric_values:
                    min_val, max_val, avg_val = min(numeric_values), max(numeric_values), mean(numeric_values)
                else:
                    min_val = max_val = avg_val = val
                print(
                    f"{iso(datetime.now(timezone.utc))} | {sensor['name']} = {fmt_num(val)} {sensor.get('unit','')} | "
                    f"Min: {fmt_num(min_val)}, Max: {fmt_num(max_val)}, Avg: {fmt_num(avg_val)} "
                    f"(buffer {len(numeric_values)}/{buffers[sensor['name']].maxlen})",
                    flush=True
                )
            except ua.UaStatusCodeError as e:
                print(f"{iso(datetime.now(timezone.utc))} | [PERMISSION ERROR] Cannot access node {sensor['nodeId']} ({sensor['name']}): {e}")
            except Exception as e:
                print(f"{iso(datetime.now(timezone.utc))} | Failed to read initial value for {sensor['name']}: {e}")


    try:
        handler = SubHandler()
        subscriptions = []

        # Create initial subscriptions
        for sensor in sensors:
            try:
                sub = client.create_subscription(sensor["scanRate"], handler)
                node = client.get_node(sensor["nodeId"])
                handle = sub.subscribe_data_change(node)
                subscriptions.append((sub, handle))
                print(f"{iso(datetime.now(timezone.utc))} | Subscribed to {sensor['name']} with scanRate={sensor['scanRate']}ms.")
            except ua.UaStatusCodeError as e:
                print(f"{iso(datetime.now(timezone.utc))} | [PERMISSION ERROR] Cannot subscribe to node {sensor['nodeId']} ({sensor['name']}): {e}")
            except Exception as e:
                print(f"{iso(datetime.now(timezone.utc))} | Failed to subscribe to {sensor['name']}: {e}")

        print_initial_values(client)

        print(f"{iso(datetime.now(timezone.utc))} | Monitoring sensors. Press 'q' + ENTER anytime to stop.\n If 'ServiceFault from server received while waiting for publish response' appears and the server is down, press ENTER to reconnect.\n")

        last_reconnect = 0

        while not stop_monitoring:
            try:
                if input().strip().lower() == "q" :
                #if keyboard.is_pressed("q"):
                    stop_monitoring = True
                    break

                now = time.time()
                if now - last_reconnect < 2:
                    time.sleep(0.2)
                    continue

                # Ping server to detect connection loss
                try:
                    client.get_node("i=1008").get_value()  
                except ua.UaStatusCodeError as e:
                    print(f"{iso(datetime.now(timezone.utc))} | [PERMISSION ERROR] Cannot read heartbeat node i=1008: {e}")
                except Exception:
                    print(f"{iso(datetime.now(timezone.utc))} | Connection lost. Attempting reconnect.\n")
                    new_client = reconnect(client)
                    if not new_client:
                        print(f"{iso(datetime.now(timezone.utc))} | Unable to reconnect. Stopping monitoring.\n")
                        stop_monitoring = True
                        break
                    client = new_client

                    # Re-subscribe after reconnect
                    subscriptions.clear()
                    for sensor in sensors:
                        sub = client.create_subscription(sensor["scanRate"], handler)
                        node = client.get_node(sensor["nodeId"])
                        handle = sub.subscribe_data_change(node)
                        subscriptions.append((sub, handle))
                    print(f"{iso(datetime.now(timezone.utc))} | Subscriptions restored after reconnect.\n")

                    # Print initial values again
                    print_initial_values(client)

            except KeyboardInterrupt:
                stop_monitoring = True

    finally:
        try:
            client.disconnect()
        except:
            pass
        print(f"{iso(datetime.now(timezone.utc))} | Disconnected from OPC UA server.")
        write_alarm_history()
        print(f"{iso(datetime.now(timezone.utc))} | Alarm history saved to {file_path}.")


        # === Main menu ===

# Whole menu
def menu():
    global exit_program, DECIMALS
    while not exit_program:
        print("\n=== OPC UA MENU ===")
        print("[1] Run simulation")
        print("[2] Load config.json")
        print(f"[3] Set decimal precision (currently {DECIMALS})")
        print("[4] Acknowledge alarm")
        print("[5] Export alarm history to CSV")
        print("[0] Exit program")
        choice = input("Choice: ").strip()

        try:
            choice_int = int(choice)
        except ValueError:
            choice_int = -1  # invalid

        if choice_int == 1:
            run_simulation()

        elif choice_int == 2:
            load_config_json()

        elif choice_int == 3:
            try:
                new_dec = int(input("Enter number of decimals (e.g. 2):").strip())
                if new_dec >= 0:
                    DECIMALS = new_dec
                    print(f"Decimal precision set to {DECIMALS}.")
                else:
                    print("Please enter a non-negative integer.")
            except ValueError:
                print("Invalid number.")

        elif choice_int == 4:
            if not alarm_history.get("alarms"):
                print("No alarms to acknowledge.")
            else:
                for idx, alarm in enumerate(alarm_history["alarms"], start=1):
                    status = "ACK" if alarm["acknowledged"] else "UNACK"
                    print(f"[{idx}] {alarm['timestamp']} | {alarm['sensor']} | {alarm['type']} | Active={alarm['active']} | {status}")
                print("[0] Do nothing")
                    
                try:
                    ack_idx = int(input("\nEnter alarm index to acknowledge: ").strip())
                    if ack_idx == 0:
                        print("Canceled acknowledgment.")
                    else:
                        actual_index = ack_idx - 1
                        # Attempt real method call
                        client = connect_to_opcua()  
                        acknowledge_alarm(actual_index, client)
                        if client:
                            client.disconnect()
                except ValueError:
                    print("Invalid input.")

        elif choice_int == 5:
            export_alarm_history_csv()

        elif choice_int == 0:
            print("Exiting program.")
            exit_program = True

        else:
            print("Invalid choice.")

# Main code
if __name__ == "__main__":
    load_config_json()
    threading.Thread(target=lambda: socketio.run(app, host="127.0.0.1", port=5000), daemon=True).start()
    menu()
