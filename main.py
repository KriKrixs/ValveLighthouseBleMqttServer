#!/usr/bin/env python3

import asyncio
import json
import sys
import re
import os
import time
from bleak import BleakClient
import paho.mqtt.client as mqtt

__PWR_SERVICE = "00001523-1212-efde-1523-785feabcd124"
__PWR_CHARACTERISTIC = "00001525-1212-efde-1523-785feabcd124"
__PWR_ON = bytearray([0x01])
__PWR_STANDBY = bytearray([0x00])

# Define the MQTT server address
broker_address = "192.168.14.12"

command = ""
lh_macs = []  # hard code mac addresses here if you want, otherwise specify in command line

print(" ")
print("=== LightHouse V2 Manager ===")
print(" ")

cmdName = os.path.basename(sys.argv[0])
cmdPath = os.path.abspath(sys.argv[0]).replace(cmdName, "")
cmdStr = (cmdPath + cmdName).replace(os.getcwd(), ".")
if cmdStr.find(".py") > 0:
    cmdStr = '"' + sys.executable + '" "' + cmdStr + '"'


async def run(loop, lh_macs, mqttClient):
    if command in ["ON", "OFF"]:
        print(">> MODE: switch LightHouse " + command.upper())
        lh_macs.extend(sys.argv[2:])
        for mac in list(lh_macs):
            if re.match("[0-9a-fA-F]{2}(:[0-9a-fA-F]{2}){5}", mac):
                continue
            print("   * Invalid MAC address format: " + mac)
            lh_macs.remove(mac)
        if len(lh_macs) == 0:
            print(" ")
            print(">> ERROR: no (valid) LightHouse MAC addresses given.")
            print(" ")
            sys.exit()
        for mac in lh_macs:
            print("   * " + mac)
        print(" ")
        for mac in lh_macs:
            if command == "ON":
                print(">> Trying to connect to BLE MAC '" + mac + "'...")
                try:
                    client = BleakClient(mac, loop=loop)
                    await client.connect()
                    print(">> '" + mac + "' connected...")
                    print("   Powering ON...")
                    for i in range(3):
                        await client.write_gatt_char(__PWR_CHARACTERISTIC, __PWR_ON)
                        time.sleep(0.5)
                        power_state = await client.read_gatt_char(__PWR_CHARACTERISTIC)
                        if power_state == __PWR_STANDBY:
                            print("   retrying....")
                        else:
                            break
                    await client.disconnect()
                    print(">> disconnected. ")
                    print("   LightHouse has been turned on.")
                    mqttClient.publish("valvelighthouseblemqtt/state", json.dumps({"mac": mac, "state": "ON"}))
                except Exception as e:
                    print(">> ERROR: " + str(e))
                print(" ")
            else:
                print(">> Trying to connect to BLE MAC '" + mac + "'...")
                try:
                    client = BleakClient(mac, loop=loop)
                    await client.connect()
                    print(">> '" + mac + "' connected...")
                    print("   Putting in STANDBY...")
                    for i in range(3):
                        await client.write_gatt_char(__PWR_CHARACTERISTIC, __PWR_STANDBY)
                        time.sleep(0.5)
                        power_state = await client.read_gatt_char(__PWR_CHARACTERISTIC)
                        if power_state == __PWR_ON:
                            print("   retrying....")
                        else:
                            break
                    await client.disconnect()
                    print(">> disconnected. ")
                    print("   LightHouse has been put in standby.")
                    mqttClient.publish("valvelighthouseblemqtt/state", json.dumps({"mac": mac, "state": "OFF"}))
                except Exception as e:
                    print(">> ERROR: " + str(e))
                print(" ")


def on_connect(mqttClient, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT Server")
        mqttClient.subscribe("valvelighthouseblemqtt/command")  # Subscribe to the topic


def on_message(client, userdata, msg):
    message = json.loads(msg.payload)

    if "mac" not in message or "command" not in message:
        print("Bad message structure")
        return

    global command
    command = message["command"]

    global lh_macs
    lh_macs = [message["mac"]]

    loop = asyncio.get_event_loop()
    loop.run_until_complete(run(loop, lh_macs, mqttClient))


# Create an MQTT client instance
mqttClient = mqtt.Client()

# Set callback functions
mqttClient.on_connect = on_connect
mqttClient.on_message = on_message

# Connect to the MQTT server
mqttClient.connect(broker_address)

# Start the network loop in a blocking way
mqttClient.loop_forever()