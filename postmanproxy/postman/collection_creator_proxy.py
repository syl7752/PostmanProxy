from libmproxy import controller, proxy
from request import Request
from Collection import Collection
import copy
import os
import socket
import json
import logging
import StringIO
import gzip
import types
from construct.core import Switch

class CollectionCreatorProxy(controller.Master):
	def __init__(self, server, collection, rules, tcp_connection=True, tcp_host="10.0.200.161", tcp_port=5005, filter_url=""):
		self.restricted_headers = [
		    'accept-charset',
		    'accept-encoding',
		    'access-control-request-headers',
		    'access-control-request-method',
		    'connection',
		    'content-length',
		    'cookie',
		    'cookie2',
		    'content-transfer-encoding',
		    'date',
		    'expect',
		    'host',
		    'keep-alive',
		    'origin',
		    'referer',
		    'te',
		    'trailer',
		    'transfer-encoding',
		    'upgrade',
		    'user-agent',
		    'via'
		    ]

		self.collection = collection
		self.rules = rules
		self.host = rules['host']
		self.methods = self.get_methods(rules['methods'])
		self.tcp_connection = tcp_connection
		self.tcp_host = tcp_host
		self.tcp_port = tcp_port
		self.filter_url = filter_url
		self.collect = []
		# self.status_codes = self.get_status_codes(rules['status_codes'])

		controller.Master.__init__(self, server)

	def remove_restricted_headers(self, request):
		restricted_headers = self.restricted_headers
		headers = copy.deepcopy(request.headersKvPairs)

		for k, v in headers.iteritems():
			key = k.lower()
			if key in restricted_headers:
				del headers[key]

		print "remove_restricted_headers:", headers
		request.headers = request.get_headers(headers)

	def send_to_postman(self, request):
		try:
			TCP_IP = self.tcp_host
			TCP_PORT = self.tcp_port
			BUFFER_SIZE = 4092 * 100
			MESSAGE = json.dumps(request.get_json(), ensure_ascii=False)

			print "send message", MESSAGE

			s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			s.connect((TCP_IP, TCP_PORT))
			s.send(MESSAGE)
			data = s.recv(BUFFER_SIZE)
			s.close()

			print "received data:", data
		except Exception as ex:
			logging.exception("send_to_postman: something awful happened!")


	def get_methods(self, methodString):
		if methodString == '':
			return []

		m = methodString.split(',')
		methods = []
		for method in m:
			method = method.strip()
			method = method.upper()
			methods.append(method)

		return methods

	def get_status_codes(self, statusCodeString):
		c = statusCodeString.split(',')
		status_codes = []
		for status_code in c:
			status_code = status_code.strip()

			if status_code != "":
				status_codes.append(int(status_code))

		return status_codes

	def run(self):
		try:
			return controller.Master.run(self)
		except KeyboardInterrupt:
			self.shutdown()

	def handle_request(self, msg):
		if self.tcp_connection:
			# self.send_to_postman(request)
			print "Sent to Postman"
		msg.reply()

	def handle_response(self, msg):
		request = Request(self.collection.id)
		print request
		request.init_from_proxy(msg)
			
		if  self.filter_url != "" and request.url.find(self.filter_url) < 0:
			print "url dosn't contain " + self.filter_url + " ,ignore request"
			msg.reply()
			return

		print request.headers
		allowed_host = True
		allowed_method = True
		allowed_status_code = True

		if not self.host == '':
			if self.host == msg.host:
				allowed_host = True
			else:
				allowed_host = False

		if len(self.methods) > 0:
			if msg.method in self.methods:
				allowed_method = True
			else:
				allowed_method = False
						
			

		if allowed_method and allowed_host and allowed_status_code:
			print self.rules
			if not self.rules['restricted_headers']:
				self.remove_restricted_headers(request)
		
		encoding = msg.response.headers.get("Content-Encoding")
		if encoding:
			print "encoding = " + encoding
		if encoding in ('gzip', 'x-gzip', 'deflate'):
			buf = StringIO.StringIO(msg.response.content)
			gzip_f = gzip.GzipFile(fileobj=buf)
			content = gzip_f.read()
		else:
			content = msg.response.content
		print "request url = " + msg.request.url
		print "get response --------- " + content
		header = "var jsonData = JSON.parse(responseBody);\n function assertHasData(data,key){\n    var myDate = new Date();\n    var mytime = myDate.toLocaleString() + '.' + myDate.getMilliseconds() + '   ';\n    tests[mytime + 'response has ' + key] = key in data;\n}\n"
		del self.collect[:]
		self.collect = []
	
		try:
			s = json.loads(content)
			self.collect.append(header)
			self.read(s, "")
			for ele in self.collect:
				# print "key = " + key+" value = "+str(s[key])
				request.add_tests(ele)
				print ele
			# self.collection.set_request(request)
			self.collection.add_request(request)
		except ValueError:
			print "response content isn't json"
		msg.reply()
		
	def read(self, obj, key):
		for k in obj.keys():
			v = obj[k]
			if isinstance(v, dict):
				if key == '':
					self.read(v, "['"+k+"']")
				else:
					self.read(v,key+"['"+k+"']")
			elif isinstance(v, list):
				if key == '':
					self.readList(v, "['"+k+"']")
				else:
					self.readList(v,key+"['"+k+"']")
			else:
				if key == '':
					self.collect.append(self.parse_to_test(key, k, v))
				else:
					# self.collect.append({str(key) + "." + k:v})
					self.collect.append(self.parse_to_test(str(key), k, v))
					
	def readList(self, obj, key):
		for index, item in enumerate(obj):
			for k in item:
				v = item[k]
				if isinstance(v, dict):
					self.read(v, key + "[" + str(index) + "]")
				elif isinstance(v, list):
					self.readList(v, key + "[" + str(index) + "]['"+k+"']")
				else:
					# self.collect.append({key + "[" + str(index) + "]" + "." + k:v})
					self.collect.append(self.parse_to_test(key + "[" + str(index) + "]", k, v))
					
	def parse_to_test(self, p, k, v):
		test_code = ""
		if isinstance(v, unicode):
			test_code += '\nassertHasData(jsonData' + p + ',"' + k + '");\n'
			test_code += 'tests["jsonData' + p + '[\'' + k + '\'] = "+ Object.prototype.toString.call(jsonData' + p + '[\'' + k + '\']).toLowerCase()] = Object.prototype.toString.call(jsonData' + p + '[\'' + k + '\']).toLowerCase()  == "[object string]";\n'
			test_code += 'tests["jsonData' + p + '[\'' + k + '\'] = ' + v + '"] = jsonData' + p + '[\'' + k + '\']  ==  "' + v + '";\n'
		elif type(v) is types.IntType:
			
			test_code += '\nassertHasData(jsonData' + p + ',"' + k + '");\n'
			test_code += 'tests["jsonData' + p + '[\'' + k + '\'] = "+ Object.prototype.toString.call(jsonData' + p + '[\'' + k + '\']).toLowerCase()] = Object.prototype.toString.call(jsonData' + p + '[\'' + k + '\']).toLowerCase()  == "[object number]";\n'
			test_code += 'tests["jsonData' + p + '[\'' + k + '\'] = ' + str(v) + '"] = jsonData' + p + '[\'' + k + '\']  === ' + str(v) + ';\n'
		elif type(v) is types.BooleanType:
			
			test_code += '\nassertHasData(jsonData' + p + ',"' + k + '");\n'
			test_code += 'tests["jsonData' + p + '[\'' + k + '\'] = "+ Object.prototype.toString.call(jsonData' + p + '[\'' + k + '\']).toLowerCase()] = Object.prototype.toString.call(jsonData' + p + '[\'' + k + '\']).toLowerCase()  == "[object boolean]";\n'
			test_code += 'tests["jsonData' + p + '[\'' + k + '\'] = ' + str(v).lower() + '"] = jsonData' + p + '[\'' + k + '\']  === ' + str(v).lower() + ';\n'
		elif type(v) is types.ObjectType:
			
			test_code += '\nassertHasData(jsonData' + p + ',"' + k + '");\n'
			test_code += 'tests["jsonData' + p + '[\'' + k + '\'] = "+ Object.prototype.toString.call(jsonData' + p + '[\'' + k + '\']).toLowerCase()] = Object.prototype.toString.call(jsonData' + p + '[\'' + k + '\']).toLowerCase()   == "[object object]";\n'
		return test_code
			
