# -*- coding: utf-8 -*-
import logging
import os
import time
from os.path import join
from threading import Thread, Lock
from select import select
from Queue import Queue, Empty

import openerp
import openerp.addons.hw_proxy.controllers.main as hw_proxy
from openerp import http
from openerp.http import request
from openerp.tools.translate import _

from collections import namedtuple
from scale.reports import \
        ReportFactory, STATUSES, ZERO_WEIGHT, STABLE_WEIGHT, DATA_REPORT

ScaleReading = namedtuple("ScaleReading", ["weight", "unit"])

_logger = logging.getLogger(__name__)

VENDOR_ID = 0x0922
PRODUCT_ID = 0x8003
DATA_MODE_GRAMS = 2
DATA_MODE_OUNCES = 11

try:
    import usb.core as usbcore;
    import usb.util
except ImportError:
    _logger.error('Odoo module hw_scale_usb depends on the usb.core and usb.util modules')
    usbcore = False


class UsbScale(Thread):

    def __init__(self):
        Thread.__init__(self)
        self.lock = Lock()
        self.scalelock = Lock()
        self.status = {'status':'connecting', 'messages':[]}
        self.weight = 0
        self.weight_info = 'ok'
        self.device = None

    def lockedstart(self):
        with self.lock:
            if not self.isAlive():
                _logger.info("Starting thread.")
                self.daemon = True
                self.start()

    def set_status(self, status, message = None):
        if status == self.status['status']:
            if message is not None and message != self.status['messages'][-1]:
                self.status['messages'].append(message)

                if status == 'error' and message:
                    _logger.error('Scale Error: '+message)
                elif status == 'disconnected' and message:
                    _logger.warning('Disconnected Scale: '+message)
        else:
            self.status['status'] = status
            if message:
                self.status['messages'] = [message]
            else:
                self.status['messages'] = []

            if status == 'error' and message:
                _logger.error('Scale Error: '+message)
            elif status == 'disconnected' and message:
                _logger.warning('Disconnected Scale: %s', message)

    def get_device(self):
        try:
            self.device = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)

            interface = 0

            if self.device is None:
              return self.device

            if self.device.is_kernel_driver_active(interface) is True:
              self.device.detach_kernel_driver(interface)
              self.device.set_configuration()
              usbcore.util.claim_interface(self.device, interface)

            self.set_status('connected','Connected to '+ 'Device name here')
            return self.device
        except Exception as e:
            self.set_status('error',str(e))
            return None

    def get_weight(self):
      self.lockedstart()
      return self.weight

    def get_weight_info(self):
        self.lockedstart()
        return self.weight_info

    def get_status(self):
        self.lockedstart()
        return self.status

    def set_zero(self):
        with self.scalelock:
            if self.device:
                try:
                  print('Not implemented')
                except Exception as e:
                    self.set_status('error',str(e))
                    self.device = None

    def set_tare(self):
        with self.scalelock:
            if self.device:
                try:
                  print('Not implemented')
                except Exception as e:
                    self.set_status('error',str(e))
                    self.device = None

    def clear_tare(self):
        with self.scalelock:
            if self.device:
                try:
                  print('Not implemented')
                except Exception as e:
                    self.set_status('error',str(e))
                    self.device = None

    def weigh(self, endpoint=None, max_attempts=10):
        """Reads from the scale until a stable weight is found"""
        weighed = False
        attempts = 0

        while not weighed and attempts < max_attempts:
            attempts += 1
            report = self.read(endpoint=endpoint)

            if not report:
                raise ConnectionError("Scale not found!")

            weighed = (report.type == DATA_REPORT and (
                report.status == STATUSES[STABLE_WEIGHT]
                or report.status == STATUSES[ZERO_WEIGHT]
            ))

        if not weighed:
            report = None

        return report

    def read(self, endpoint=None, max_attempts=10):
        """Takes a reading from the scale and returns a named tuple"""
        if not self.device:
            return False

        data = None
        error = None
        attempts = 0

        if not endpoint:
            endpoint = self.device[0][(0,0)][0]

        # Weighing data consists of a six-element array.
        # In between reads, it returns a two-element array to
        # demonstrate readiness. We can ignore those.
        while not data and attempts < max_attempts:
            attempts += 1
            try:
                data = self.device.read(
                    endpoint.bEndpointAddress,
                    endpoint.wMaxPacketSize
                )
            except Exception as e:
                error = e

        if error and not data:
            raise error

        return ReportFactory.build(data)

    def run(self):
        self.device = None
        while True:
            if self.device:
                self.weight = self.weigh()
                time.sleep(0.3)
            else:
                with self.scalelock:
                    self.device = self.get_device()
                if not self.device:
                    time.sleep(5)

scale_thread = None

if usbcore:
    scale_thread = UsbScale()
    hw_proxy.drivers['scale'] = scale_thread

class ScaleDriver(hw_proxy.Proxy):
    @http.route('/hw_proxy/scale_read/', type='json', auth='none', cors='*')
    def scale_read(self):
        if scale_thread:
            weight = scale_thread.get_weight()
            return {'weight': weight.weight, 'unit': weight.unit, 'info': scale_thread.get_weight_info()}
        return None

    @http.route('/hw_proxy/scale_zero/', type='json', auth='none', cors='*')
    def scale_zero(self):
        if scale_thread:
            scale_thread.set_zero()
        return True

    @http.route('/hw_proxy/scale_tare/', type='json', auth='none', cors='*')
    def scale_tare(self):
        if scale_thread:
            scale_thread.set_tare()
        return True

    @http.route('/hw_proxy/scale_clear_tare/', type='json', auth='none', cors='*')
    def scale_clear_tare(self):
        if scale_thread:
            scale_thread.clear_tare()
        return True

