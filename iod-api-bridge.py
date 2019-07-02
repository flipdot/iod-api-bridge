#!/usr/bin/env python3
import paho.mqtt.client as mqtt
import json
import requests
import sys
import yaml
from requests import RequestException

API_HOST = "api.flipdot.org"
API_PREFIX = "sensors"
MQTT_TOPIC_ERRORS = "errors"

config = yaml.load(open("config.yaml", "r"))
session = None

def find_sensor_by_topic(topic):
    sensors = config["sensors"]
    sensor_found = None
    for sensor in sensors.items():
        sensor_topic = sensor[1]["topic"]
        if sensor_topic == topic:
            sensor_found = sensor
            break
    if sensor_found:
        return sensor_found


def config_lookup(value, sensor_const, sensor_mqtt, mqtt_msg):
    ret = None
    if value in sensor_mqtt:
        ret = mqtt_msg[sensor_mqtt[value]]
    else:
        ret = sensor_const[value]
    return ret


def on_connect(client, userdata, flags, result):
    try:
        sensors = config["sensors"]
    except KeyError:
        print("'sensors' not defined in 'config.yaml'.")
        sys.exit(1)

    for sensor in sensors.values():
        topic = sensor["topic"]
        client.subscribe(topic)


def get(url):
    global session
    if not session:
        session = requests.Session()
    return session.get(url)


def on_message(client, userdata, message):
    topic = message.topic
    sensor = find_sensor_by_topic(topic)
    sensor_const = sensor[1]["const"]
    sensor_mqtt = sensor[1]["mqtt"]
    web_url = ""

    try:
        mqtt_msg = yaml.load(message.payload)

        web_category = config_lookup("category",
                                     sensor_const, sensor_mqtt, mqtt_msg)
        web_location = config_lookup("location",
                                     sensor_const, sensor_mqtt, mqtt_msg)
        web_value = config_lookup("value",
                                  sensor_const, sensor_mqtt, mqtt_msg)
        web_unit = config_lookup("unit",
                                 sensor_const, sensor_mqtt, mqtt_msg)
        web_name = config_lookup("name",
                                 sensor_const, sensor_mqtt, mqtt_msg)

        web_name_prefix = config_lookup("name_prefix",
                                        sensor_const, sensor_mqtt, mqtt_msg)
        web_value_prefix = config_lookup("value_prefix",
                                         sensor_const, sensor_mqtt, mqtt_msg)

        if web_name_prefix:
            web_name = f"{web_name_prefix}{web_name}"
        if web_value_prefix:
            web_value = f"{web_value_prefix}{web_value}"

        # API_HOST/category/location/value[/unit[/name]]
        web_url = "https://{}/{}/{}/{}/{}/{}/{}".format(
            API_HOST,
            API_PREFIX,
            web_category,
            web_location,
            web_value,
            web_unit,
            web_name,
        )

    except KeyError as e:
        error_json = {
            "origin": "iod-api-bridge",
            "message": "Unknown topic/attribute {}".format(e),
        }
        client.publish(MQTT_TOPIC_ERRORS, json.dumps(error_json))

    try:
        if not web_url:
            raise RequestException("No URL defined.")
        get(web_url)
    except RequestException as e:
        error_json = {
            "origin": "iod-api-bridge",
            "message": "Error with GET request: {}".format(e),
        }
        client.publish(MQTT_TOPIC_ERRORS, json.dumps(error_json))


client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect(config["mqtt_host"])
client.loop_forever()
