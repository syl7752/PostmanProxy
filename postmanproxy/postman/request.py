import utils
import time
import uuid
import logging
from werkzeug import http
from werkzeug.formparser import parse_form_data
from werkzeug.wrappers import Request
from cStringIO import StringIO

class Request:
	def __init__(self, collectionId):
		self.id = str(uuid.uuid4())
		self.collectionId = collectionId
		self.url = ""
		self.name = ""
		self.description = ""
		self.method = ""
		self.headers = []
		self.data = []
		self.dataMode = "raw"
		self.responses = []
		self.version = 2
		self.timestamp = int(round(time.time()))
		self.tests = ""

	def get_json(self):
		r = {
			'id': self.id,
			'collectionId': self.collectionId,
			'url': self.url,
			'name': self.name,
			'description': self.description,
			'method': self.method,
			'headers': self.headers,
			'data': self.data,
			'dataMode': self.dataMode,
			'responses': self.responses,
			'version': self.version,
			'timestamp': self.timestamp,
			'tests': self.tests
		}

		return r

	def get_formdata_body(self, data, header, method):
		# http://werkzeug.pocoo.org/docs/http/
		environ = {
			'wsgi.input': StringIO(data),
			'CONTENT_LENGTH': str(len(data)),
			'CONTENT_TYPE': header,
			'REQUEST_METHOD': method
		}

		stream, form, files = parse_form_data(environ)

		d = []
		for k, v in form.iteritems():
			o = {
				'key': k,
				'value': v,
				'type': 'text'
			}

			d.append(o)

		return d

	def get_urlencoded_body(self, data, header, method):
		# http://werkzeug.pocoo.org/docs/quickstart/#wsgi-environment
		environ = {
			'wsgi.input': StringIO(data),
			'CONTENT_LENGTH': str(len(data)),
			'CONTENT_TYPE': header,
			'REQUEST_METHOD': method
		}

		stream, form, files = parse_form_data(environ)

		d = []
		for k, v in form.iteritems():
			o = {
				'key': k,
				'value': v,
				'type': 'text'
			}

			d.append(o)

		return d

	def get_name(self, proxy_request):
		path = proxy_request.request.path
		name = path[:30]
		return name

	def get_url(self, proxy_request):
		if proxy_request.request.port == 443:
			url = 'https://' + proxy_request.request.host + proxy_request.request.path
		elif proxy_request.request.port == 80:
			url = 'http://' + proxy_request.request.host + proxy_request.request.path
		else:
			url = 'http://' + proxy_request.request.host + ":" + str(proxy_request.request.port) + proxy_request.request.path

		return url

	def get_data_mode(self, proxy_request):
		if "content-type" in proxy_request.request.headers:
			content_type = proxy_request.request.headers.get("content-type")
			print "content_type ------= "+content_type

			if content_type.find("x-www-form-urlencoded") > 0:
				return "urlencoded"
			elif content_type.find("form-data") > 0:
				return "params"
			else:
				return "raw"
		else:
			return "raw"

	def method_has_body(self, method):
		methods_with_body = ["POST", "PUT", "PATCH", "DELETE", "LINK", "UNLINK"]

		if method in methods_with_body:
			return True
		else:
			return False


	def get_headers(self, headers):
		head_string = ""
		for k, v in headers.iteritems():
			head_string += k + ": " + v + "\n"

		return head_string

	def init_from_proxy(self, proxy_request):
		self.name = self.get_name(proxy_request)
		self.url = self.get_url(proxy_request)
		print "url = "+self.url
		self.method = proxy_request.request.method
		self.headersKvPairs = proxy_request.request.headers
		self.headers = self.get_headers(proxy_request.request.headers)

		try:
			if self.method_has_body(self.method):
				self.dataMode = self.get_data_mode(proxy_request)
				print "Data mode is %s" % (self.dataMode)
				content = proxy_request.request.content
				

				if "content-type" in proxy_request.request.headers:
					#h = proxy_request.request.headers["content-type"][0]
					h = proxy_request.request.headers.get("content-type")

					if self.dataMode == "urlencoded":
						self.data = self.get_urlencoded_body(content, h, self.method)
					elif self.dataMode == "params":
						self.data = self.get_formdata_body(content, h, self.method)
					else:
						self.data = content
				else:
					self.data = content
			else:
				pass
		except Exception as ex:
			logging.exception("init_from_proxy: Something awful happened!")
	
	def add_tests(self,test_code):
		self.tests+=test_code
		
	def get_tests(self):
		return self.tests
