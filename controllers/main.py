# -*- coding: utf-8 -*-
import logging
import traceback

import openerp
import openerp.addons.hw_proxy.controllers.main as hw_proxy
from openerp import http
from openerp.http import request
from openerp.tools.translate import _

try:
  from .. scale import *
  from .. scale.scale import Scale
except ImportError:
  scalepos = scale = None

from threading import Thread, Lock

try:
  import usb.core
except ImportError:
  usb = None

_logger = logging.getLogger(__name__)

class ScaleDriver(Thread):

  def __init__(self):

    Thread.__init__(self)

    self.lock = Lock()
    self.tare = 0
    self.lastreading = None
    self.status = { 'status' : 'connecting', 'messages' : [] }

  def connected_usb_devices(self):
    connected = []

    class FindUsbClass(object):
      def __init__(self, usb_class):
        self._class = usb_class

      def __call(self, device):
        if device.bDeviceClass == self._class:
          return True

        for cfg in devices:
          inft = usb.util.find_descriptor(cfg, bInterfaceClass=self._class)

          if intf is not None:
            return True

        return False

    scales = usb.core.find(find_all=True, custom_match=FindUsbClass(3))

    if not scales:
      scales = usb.core.find(find_all=True, idVendor=0x0922)

    for scale in scales:
      connected.append({
        'vendor' : scale.idVendor,
        'product' : scale.idProduct,
        'name' : "%s %s" % usb.util.get_string(scale, 256, scale.iManufacturer) + " " +usb.util.get_string(scale, 256, scale.iProduct)
        })

    return connected

  def lockedstart(self):
    _logger.error("Starting thread with lockedstart()")
    with self.lock:
      if not self.is_alive():
        self.daemon = True
        self.start()

  def get_scale(self):
    scales = self.connected_usb_devices()
    if len(scales) > 0:
      self.set_status('connected', 'Connected to ' + scales[0]['name'])
      return Scale(None, scales[0]['vendor'], scales[0]['product'])
    else:
      self.set_status('disconnected', 'Scale not found')
      return None

  def get_status(self):
    return self.status

  def set_tare(self):
    if self.lastreading is not None:
      self.tare = self.lastreading.weight

  def clear_tare(self):
    self.tare = 0

  def get_weight(self):
    return self.lastreading

  def set_status(self, status, message = None):
    _logger.info(status+ ' : ' + (message or 'no message'))
    if status == self.status['status']:
      if message != None and (len(self.status['messages']) == 0 or message != self.status['messages'][-1]):
          self.status['messages'].append(message)
    else:
      self.status['status'] = status
      if message:
        self.status['messages'] = [message]
      else:
        self.status['messages'] = []

    if status == 'error' and message:
      _logger.error('Scale Error: ' + message)
    elif status == 'disconnected' and message:
      _logger.warning('Scale Device Disconnected: ' + message)

  def run(self):

    scalepos = None

    if not scale: #scale refers to the module here
      _logger.error('Scale not initialized, please verify system dependencies.')
      return

    while True:

      try:
        error = True

        scalepos = self.get_scale()

        if scalepos == None:
            error = False
            time.sleep(5)
            continue
        else:
          scalepos.connect()

        self.lastreading = scalepos.weigh()

        time.sleep(0.5)

        error = False

      except Exception as e:
        self.set_status('error', str(e))
        errmsg = str(e) + '\n' + '-'*60 + '\n' + traceback.format_exc() + '-'*60 + '\n'
        _logger.error(errmsg)
      finally:
        if scalepos:
          scalepos.disconnect()

driver = ScaleDriver()
driver.lockedstart()
hw_proxy.drivers['scale'] = driver

class ScaleProxy(hw_proxy.Proxy):
    @http.route('/hw_proxy/scale_read/', type='json', auth='none', cors='*')
    def scale_read(self):
        if driver:
          reading = driver.get_weight()
          return { 'weight': reading.weight - driver.tare, 'unit': reading.unit, 'info': reading.status }
        return None

    @http.route('/hw_proxy/scale_zero/', type='json', auth='none', cors='*')
    def scale_zero(self):
        return True

    @http.route('/hw_proxy/scale_tare/', type='json', auth='none', cors='*')
    def scale_tare(self):
      if driver:
        driver.set_tare()
        return True

    @http.route('/hw_proxy/scale_clear_tare/', type='json', auth='none', cors='*')
    def scale_clear_tare(self):
      if driver:
        driver.clear_tare()
        return True

