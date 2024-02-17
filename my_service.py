#!/usr/bin/env python3

import logging
import signal
import sys
import threading
import time
from logging.config import dictConfig
from typing import Optional

import paho.mqtt.client as mqtt
import typer
from typing_extensions import Annotated

__version__ = "0.1.0"

# logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-6s %(message)s')

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s %(levelname)-6s %(message)s"
        },
        "simple": {
            "format": "%(levelname)-6s %(message)s",
        }
    },
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": "simple",
        }
    },
    "loggers": {"": {"handlers": ["stdout"], "level": "DEBUG"}},
}

dictConfig(LOGGING)


def version_callback(value: bool):
    if value:
        print(f"My Service Start Version: {__version__}")
        raise typer.Exit()


class MqttClient:  # MC
    def __init__(self,
                 mqtt_host: str,
                 mqtt_port: int,
                 mqtt_user: str,
                 mqtt_password: str,
                 discovery_topic_prefix: str,
                 topic_prefix: str,
                 update_interval: int):

        self.mqtt_host = mqtt_host
        self.mqtt_port = mqtt_port
        self.mqtt_user = mqtt_user
        self.mqtt_password = mqtt_password

        # ensure there is no trailing slash on discovery_topic_prefix
        if discovery_topic_prefix.endswith('/'):
            self.discovery_topic_prefix = discovery_topic_prefix[:-1]
        else:
            self.discovery_topic_prefix = discovery_topic_prefix

        # ensure there is no trailing slash on topic_prefix
        if topic_prefix.endswith('/'):
            self.topic_prefix = topic_prefix[:-1]
        else:
            self.topic_prefix = topic_prefix

        self.update_interval = update_interval

        # register signal handler
        signal.signal(signal.SIGINT, self.signal_handler)

        # MQTT Client
        self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)

        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect

        self.client.username_pw_set(self.mqtt_user, self.mqtt_password)
        self.client.will_set(f'{self.topic_prefix}/status', payload='offline', qos=0, retain=True)

        # custom attributes
        self.counter = 0

    def on_connect(self, client, userdata, flags, rc, properties=None):
        logging.debug('--> on_connect')
        logging.debug(f'all: {client} - {userdata} - {flags} - {rc} - {properties}')
        if rc != 0:
            logging.error(f'Connection failed with reason code: {rc}')
            sys.exit(1)  # exit this thread
        else:
            logging.info(f'Connection successful with reason code: {rc}')

            logging.debug(f'Initial publishing of status')
            self.client.publish(f'{self.topic_prefix}/status', payload='online', qos=0, retain=True)

            logging.debug(f'Initial publishing of discovery')
            self.publish_discovery()

    def on_disconnect(self, client, userdata, rc=0):
        logging.debug(f'--> on_disconnected - reason code: {rc}')
        client.loop_stop()  # ToDo(frennkie): is this needed?

    def publish_discovery(self):
        """Publish discovery data - stub"""
        logging.debug('--> publish_discovery')

    def regular_update(self):
        """Regular update"""
        logging.info('--> regular_update')

        self.counter += 1
        self.client.publish(f'{self.topic_prefix}/status', payload=f'update:{self.counter}', qos=0, retain=True)

    def remove_discovery(self):
        """Remove discovery data - stub"""
        logging.debug('--> remove_discovery')

    def run(self):
        # print key configuration settings
        logging.info(f'### SETTINGS: Start  #################################')
        logging.info(f'Connection:              {self.mqtt_user}@{self.mqtt_host}:{self.mqtt_port}')
        logging.info(f'Interval (s):            {self.update_interval}')
        logging.info(f'Discovery topic prefix:  {self.discovery_topic_prefix}')
        logging.info(f'Topic prefix:            {self.topic_prefix}')
        logging.info(f'### SETTINGS: End    #################################')

        self.client.connect(self.mqtt_host, self.mqtt_port, 60)

        # start MQTT loop
        self.client.loop_start()

        # do something before loop
        logging.debug('before loop')

        while True:
            if threading.active_count() == 1:
                logging.error(f'Only one thread running, should be at least two -> exiting.')
                sys.exit(1)

            # do something in loop before sleep
            logging.debug('in loop: before sleep')
            self.regular_update()

            # sleep for a while
            time.sleep(self.update_interval)

            # do something in loop after sleep
            logging.debug('in loop: after sleep')

    def signal_handler(self, sig, frame):
        logging.debug('received SIGINT')

        self.client.publish(f'{self.topic_prefix}/status', payload='goodbye', qos=0, retain=True)

        self.client.disconnect()

        logging.info('--> clean exit')
        sys.exit(0)


def main(
        mqtt_host: Annotated[
            str, typer.Option("--mqtt-host", "-H",
                              envvar="MQTT_HOST", help="MQTT host")
        ] = "homeassistant.local",

        mqtt_port: Annotated[
            int, typer.Option("--mqtt-port", "-P",
                              envvar="MQTT_PORT", help="MQTT port")
        ] = 1883,

        mqtt_user: Annotated[
            str, typer.Option("--mqtt-user", "-u",
                              envvar="MQTT_USER", help="MQTT user")
        ] = 'mqttuser',

        mqtt_password: Annotated[
            str, typer.Option("--mqtt-password", "-p",
                              envvar="MQTT_PASSWORD", help="MQTT password")
        ] = 'changeme',

        discovery_topic_prefix: Annotated[str, typer.Option(
            "--discovery-topic-prefix", "-d",
            envvar="DISCOVERY_TOPIC_PREFIX",
            help="Discovery topic prefix"
        )] = 'homeassistant/sensor/foobar',

        topic_prefix: Annotated[
            str, typer.Option("--topic-prefix", "-t",
                              envvar="TOPIC_PREFIX", help="Topic prefix")
        ] = 'home/nodes/sensor/foobar',

        update_interval: Annotated[
            int, typer.Option("--update-interval", "-i",
                              envvar="UPDATE_INTERVAL",
                              help="Update interval in seconds.")
        ] = 300,

        debug: Annotated[
            bool, typer.Option("--debug",
                               envvar="DEBUG", help="Enable debug mode")
        ] = False,

        version: Annotated[
            Optional[bool], typer.Option("--version", callback=version_callback,
                                         help="Print version info.", is_eager=True)
        ] = None
):
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.INFO)

    mc = MqttClient(
        mqtt_host=mqtt_host,
        mqtt_port=mqtt_port,
        mqtt_user=mqtt_user,
        mqtt_password=mqtt_password,
        discovery_topic_prefix=discovery_topic_prefix,
        topic_prefix=topic_prefix,
        update_interval=update_interval,
    )

    mc.run()


if __name__ == "__main__":
    typer.run(main)
