# -*- coding: utf-8 -*-
import logging

from scale.scale import Scale

import openerp
import openerp.addons.hw_proxy.controllers.main as hw_proxy
from openerp import http
from openerp.http import request
from openerp.tools.translate import _

from threading import Thread, Lock


_logger = logging.getLogger(__name__)


class ScaleThread(Thread):

  def __init__(self):
    Thread.__init__(self)
    self.lock = Lock()
    self.scalelock = Lock()
    self.__scale = None

  def lockedstart(self):
    with self.lock:
      if not self.is_alive():
        self.daemon = True
        self.start()

  def weigh(self):
    self.lockedstart()
    with self.scalelock:
      return self.scale.weigh()

  def get_status(self):
    self.lockedstart()
    with self.scalelock:
      if self.scale:
        return self.scale.get_status()
      else:
        return { 'status': 'connecting', 'messages': [] }

  def run(self):
    self.__scale = None

    while True:
      if not self.scale:
        with self.scalelock:
          self.__scale = Scale(manufacturer='0x0922', device='0x8003')
      else:
        if self.scale.connect():
          self.weigh()
          time.sleep(0.3)
        else:
          time.sleep(5)

  @property
  def scale(self):
    return self.__scale

usb_scale = ScaleThread()
hw_proxy.drivers['scale'] = usb_scale

class ScaleDriver(hw_proxy.Proxy):
    @http.route('/hw_proxy/scale_read/', type='json', auth='none', cors='*')
    def scale_read(self):
        if usb_scale:
          reading = usb_scale.weigh()
          return { 'weight': reading.weight, 'unit': reading.unit, 'info': reading.status }
        return None

    @http.route('/hw_proxy/scale_zero/', type='json', auth='none', cors='*')
    def scale_zero(self):
        return True

    @http.route('/hw_proxy/scale_tare/', type='json', auth='none', cors='*')
    def scale_tare(self):
        return True

    @http.route('/hw_proxy/scale_clear_tare/', type='json', auth='none', cors='*')
    def scale_clear_tare(self):
        return True

