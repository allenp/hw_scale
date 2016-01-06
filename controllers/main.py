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
    self.__lastreading = None

  def lockedstart(self):
    with self.lock:
      if not self.is_alive():
        if not self.isDaemon():
          self.daemon = True
          self.start()

  def get_weight():
    self.lockedstart()
    return self.__lastreading

  def read_weight():
    with self.scalelock:
      self.__lastreading = self.scale.weigh()

  def get_status(self):
    self.lockedstart()
    if self.scale:
      return self.scale.get_status()
    else:
      return { 'status': 'connecting', 'messages': [] }

  def run(self):
    self.__scale = None
    while True:
      if self.scale:
        if self.scale.connect():
          self.read_weight()
          time.sleep(0.3)
        else:
          time.sleep(5)
      else:
        with self.scalelock:
          self.__scale = Scale(manufacturer='0x0922', device='0x8003')

  @property
  def scale(self):
    return self.__scale

driver = ScaleThread()
hw_proxy.drivers['scale'] = driver

class ScaleDriver(hw_proxy.Proxy):
    @http.route('/hw_proxy/scale_read/', type='json', auth='none', cors='*')
    def scale_read(self):
      reading = self.get_weight()
      if reading:
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

