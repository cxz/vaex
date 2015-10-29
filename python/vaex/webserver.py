from __future__ import absolute_import
__author__ = 'maartenbreddels'

import tornado.ioloop
import tornado.web
import tornado.httpserver
import threading
from . import logging
import vaex as vx
import json
import inspect

logger = logging.getLogger("vaex.webserver")

def task_invoke(subspace, method_name, request):
	method = getattr(subspace, method_name)
	args, varargs, kwargs, defaults = inspect.getargspec(method)
	#print inspect.getargspec(method)
	#args_required = args[:len(args)-len(defaults)]
	kwargs = {}
	for arg in args:
		if arg in request.arguments:
			#print arg, repr(request.arguments[arg][0])
			kwargs[arg] = json.loads(request.arguments[arg][0])
	values = method(**kwargs)
	return values

class ListHandler(tornado.web.RequestHandler):
	def initialize(self, datasets):
		self.datasets = datasets
		self.datasets_map = dict([(ds.name,ds) for ds in self.datasets])

	def get(self):
        #self.write("Hello, world")
		#print self.request.path
		parts = [part for part in self.request.path.split("/") if part]
		logger.debug("request: %r" % parts)
		print parts
		#print parts
		if parts[0] == "datasets":
			if len(parts) == 1:
				response = dict(datasets=[{"name":ds.name, "full_length":len(ds), "column_names":ds.get_column_names()} for ds in self.datasets])
				self.write(response)
			else:
				dataset_name = parts[1]
				if dataset_name not in self.datasets_map:
					self.error("dataset does not exist: %r, possible options: %r" % (dataset_name, self.datasets_map.keys()))
				else:
					if len(parts) > 2:
						method_name = parts[2]
						logger.debug("method: %r args: %r" % (method_name, self.request.arguments))
						if "expressions" in self.request.arguments:
							expressions = json.loads(self.request.arguments["expressions"][0])
						else:
							expressions = None
						subspace = self.datasets_map[dataset_name](*expressions)
						if method_name in ["minmax", "var", "mean", "sum", "limits_sigma"]:
							#print "expressions", expressions
							values = task_invoke(subspace, method_name, self.request)
							#print values, expressions
							self.write({"result": values.tolist()})
						if method_name == "histogram":
							grid = task_invoke(subspace, method_name, self.request)
							self.set_header("Content-Type", "application/octet-stream")
							self.write(grid.tostring())

	def error(self, msg):
		self.write({"error": msg})



class QueueHandler(tornado.web.RequestHandler):
	def initialize(self, datasets):
		self.datasets = datasets
		self.datasets_map = dict([(ds.name,ds) for ds in self.datasets])

	def get(self):
        #self.write("Hello, world")
		self.write(dict(datasets=[{"name":ds.name, "length":len(ds)} for ds in self.datasets]))



class WebServer(threading.Thread):
	def __init__(self, address="localhost", port=9000, datasets=[]):
		threading.Thread.__init__(self)
		self.address = address
		self.port = port
		self.started = threading.Event()
		self.options = dict(datasets=datasets)

		self.application = tornado.web.Application([
			(r"/queue", QueueHandler, self.options),
			(r"/.*", ListHandler, self.options),
		])

	def serve(self):
		self.mainloop()

	def serve_threaded(self):
		self.start()
		self.started.wait()
		# this will make the main thread use this ioloop as current
		self.ioloop.make_current()

	def run(self):
		self.mainloop()

	def mainloop(self):
		logger.info("serving at http://%s:%d" % (self.address, self.port))
		self.ioloop = tornado.ioloop.IOLoop.current()
		# listen doesn't return a server object, which we need to close
		#self.application.listen(self.port, address=self.address)
		from tornado.httpserver import HTTPServer
		self.server = HTTPServer(self.application)
		self.server.listen(self.port, self.address)
		self.ioloop.add_callback(self.started.set)
		self.ioloop.start()

	def stop_serving(self):
		self.server.stop()
		self.ioloop.stop()

if __name__ == "__main__":
	#logger.setLevel(logging.logging.DEBUG)
	import vaex
	vaex.set_log_level_debug()
	import sys
	filenames = sys.argv[1:]
	if filenames:
		datasets = [vx.open(filename) for filename in filenames]
	else:
		datasets = [vx.example()]
	server = WebServer(datasets=datasets, address="0.0.0.0")
	server.serve()

	#3_threaded()
	#import time
	#time.sleep(10)
	#server.stop_serving()