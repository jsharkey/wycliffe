
#
# wycliffe -- Clean room implementation of Dante protocol
#
# Copyright (C) 2014 Jeff Sharkey, http://jsharkey.org/
# All Rights Reserved.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import random, collections, operator

import serial


class Channel():
	def __init__(self, title, w, matches):
		self.title = title
		self.w = w
		self.matches = set(matches.split(","))
		self.active = False

	def __repr__(self):
		return self.title

class Shot():
	def __init__(self, preset, title):
		self.preset = preset
		self.title = title

	def __repr__(self):
		return self.title

"""
vKEYS = Shot(1, "vKEYS")
vDRUMS = Shot(2, "vDRUMS")
vWL = Shot(3, "vWL")
vPL = Shot(4, "vPL")
vMIDI = Shot(5, "vMIDI")
vBG = Shot(6, "vBG")
vC = Shot(7, "vC")
vCL = Shot(8, "vCL")
vCR = Shot(9, "vCR")
vL = Shot(10, "vL")
vR = Shot(11, "vR")
vFULL = Shot(12, "vFULL")
"""

vKEYS = Shot(1, "vKEYS")
vDRUMS = Shot(2, "vDRUMS")
vWL = Shot(3, "vWL")
vMIDI = Shot(4, "vMIDI")
vBG = Shot(5, "vBG")
vPL = Shot(6, "vPL")
vR = Shot(7, "vR")
vL = Shot(8, "vL")
vFULL = Shot(9, "vFULL")
vC = Shot(10, "vC")
vCR = Shot(11, "vCR")
vCL = Shot(12, "vCL")


aPLVOX = Channel("aPLVOX", 1.2, "PLVOX,PLVOC")
aWLVOX = Channel("aWLVOX", 0.8, "WLVOX1,WLVOX2")
aBGV = Channel("aBGV", 0.8, "BGV1,BGV2,BGV3")
aKEYVOX = Channel("aKEYVOX", 0.6, "KEYVOX")
aMIDIVOX = Channel("aMIDIVOX", 0.6, "MIDIVOX")
aWLINST = Channel("aWLINST", 0.5, "EGT1,AGT1")
aKEY = Channel("aKEY", 0.5, "KEYL,KEYR,KEY")
aMIDI = Channel("aMIDI", 0.5, "MIDIL,MIDIR,MIDI")
aDRUMS = Channel("aDRUMS", 0.5, "DRUMS,KICK,SNARE,OHL,OHR")
aBASS = Channel("aBASS", 0.5, "BASS")

AUDIO = [aPLVOX,aWLVOX,aBGV,aKEYVOX,aMIDIVOX,aWLINST,aKEY,aMIDI,aDRUMS,aBASS]

CONFIG = {
	aPLVOX: [vPL,vR,vCR],
	aWLVOX: [vWL,vC,vCR,vCL,vFULL],
	aBGV: [vBG,vR,vCR,vFULL],
	aKEYVOX: [vKEYS,vL,vCL,vFULL],
	aMIDIVOX: [vMIDI,vCR,vFULL],

	aWLINST: [vWL,vC,vCR,vCL,vFULL],
	aKEY: [vKEYS,vL,vCL,vFULL],
	aMIDI: [vMIDI,vCR,vFULL],
	aDRUMS: [vDRUMS,vCL,vFULL],
	aBASS: [vL,vCL,vFULL],
}

for c, v in CONFIG.iteritems():
	while None in v:
		v.remove(None)



# apt-get install python-dev python-pip
# pip install urwid

import sys, struct, re, threading, time
import socket
from socket import *
import urwid

def exit_on_q(key):
    if key in ('q', 'Q'):
        raise urwid.ExitMainLoop()

palette = [
    ('banner', 'black', 'light gray'),
    ('streak', 'black', 'dark red'),
    ('inactive', 'black', 'dark blue'),
	('active', 'black', 'dark red'),
    ]


rows = []
channel_ui = []

ui_summary = urwid.Text(('label', u"[camera summary]"), align='left')
ui_cam = urwid.BigText('[]', urwid.font.HalfBlock5x4Font())

#rows.append(ui_summary)
#rows.append()

wrapped_ui_cam = urwid.Padding(ui_cam, width='clip')
rows.append(urwid.Columns([ui_summary, ('weight', 0.3, wrapped_ui_cam)], dividechars=1))


class VisualChannel():
	def __init__(self, i):
		self.label = urwid.Text(('label', u"CH%d" % (i)), align='right')
		self.level = urwid.ProgressBar('', 'inactive', 0, 255)
		#self.level_color = urwid.AttrMap(self.level, 'active')
		self.row = urwid.Columns([('weight', 0.2, self.label), self.level], dividechars=1)

for i in range(1,128):
	ch = VisualChannel(i)
	channel_ui.append(ch)
	rows.append(ch.row)

page = urwid.ListBox(urwid.SimpleFocusListWalker(rows))


# spwan thread to watch for updates

#exit(0)

DANTE = "10.35.37.22"
CTL_PORT = 8800
INFO_PORT = 4440
RMS_PORT = 8751

LOCAL_IDENT = "001c25bf39850000"
#LOCAL_IDENT = "CAFECAFECAFE0000"
LOCAL_IP = "10.35.20.20"

class InfoPacket():
	# t3=0000 send
	# t3=0001 recv
	
	def __init__(self, t1, length, cookie, t2, t3, data):
		self.t1 = t1
		self.length = length
		self.cookie = cookie
		self.t2 = t2
		self.t3 = t3
		self.data = data
	
	@classmethod
	def outgoing(cls, t1, cookie, t2, t3):
		return cls(t1=t1, length=10, cookie=cookie, t2=t2, t3=t3, data=[])
		
	@classmethod
	def incoming(cls, data):
		t1, length, cookie, t2, t3 = struct.unpack("!5H", data[0:10])
		return cls(t1=t1, length=length, cookie=cookie, t2=t2, t3=t3, data=data[10:])
	
	def append_hex(self, data):
		self.append_raw(data.replace(" ", "").decode("hex"))
	
	def append_raw(self, data):
		self.data.append(data)
		self.length += len(data)
	
	def pack(self):
		out = struct.pack("!5H", self.t1, self.length, self.cookie, self.t2, self.t3)
		for d in self.data:
			out += d
		return out




# request tx channel details
#p = InfoPacket.outgoing(0x2712, 0xeeee, 0x2010, 0x0000)
#p.append_hex("0001 0001 0080")


# parse tx channel details
data = "271201bf000920100001201e00010001010c00020002011100030003011a00040004012300050005012700060006012b00070007013000080008013500090011013c000a00120141000b00130146000c0014014d000d00150152000e00160159000f0017015e00100018016300110021016800120022016e00130023017400140024017a00150025018400160026018c00170027019100180028019800190031019d001a003201a2001b003301a7001c003401ae001d003701b5001e003801ba003a000e016801ab014f01ae0000000100000000003b000e016801b1014f01b40000000100000000003c000e016801b7014f01ba0000000100000000003d000e016801bd014f01c0000000014b49434b00534e415245544f5000534e41524542544d004f484c004f485200544f4d3100544f4d320044434c49434b0041475431004547543100574c564f5831004147543200574c564f583200424756310042475632004247563300504c564f43004d4944494c004d49444952004d494449434c49434b004d494449564f580042415353004b4559564f58004b45594c004b4559520045475432004d494449324c004d494449325200464f484c00464f485200".decode("hex")

p = InfoPacket.incoming(data)
total, ret = struct.unpack("!BB", p.data[0:2])
channels = {}

for n in range(ret):
	ptr = 2+(n*6)
	n, target, label_ptr = struct.unpack("!3H", p.data[ptr:ptr+6])
	label_ptr -= 10
	label = p.data[label_ptr:p.data.index("\0", label_ptr)]
	channels[target] = label
	channel_ui[target-1].label.set_text(label)
	#print target, label




# parse rms
rms_data = "ffff009b3ca00000001dc10412e20000417564696e617465024040bfc9c4b8bcbcb8a9bfc9c4b8bcbcb8a9a7a88bac88afb1afa7a88bac88afb1afb0cccbcdb29ca6c0b0cccbcdb29ca6c0c4b1cccafefee3e2c4b1cccafefee3e2fefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefe".decode("hex")


csock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP)
csock.bind(('', CTL_PORT))

rsock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP)
rsock.bind(('', RMS_PORT))


# request rms stream
p = InfoPacket.outgoing(0x1200, 0xeeee, 0x3010, 0x0000)
p.append_hex("0000")
p.append_hex(LOCAL_IDENT)
p.append_hex("0004 0018 0001 0022 000a")
p.append_raw("DN965x-0412e2\0admii-PC\0")
p.append_hex("00 0001 0026 0001")
p.append_raw(struct.pack("!H", RMS_PORT))
p.append_hex("0001 0000")
p.append_raw(inet_pton(AF_INET, LOCAL_IP))
p.append_raw(struct.pack("!H", RMS_PORT))
p.append_hex("0000")

csock.sendto(p.pack(), (DANTE, CTL_PORT))


import collections

recent = collections.defaultdict(lambda: float(128))

ACTIVE_THRESH = {
	'KICK': 0.6,
	'OHR': 0.6, 'OHL': 0.6,
	'TOM1': 0.6, 'TOM2': 0.6,
	'SNARETOP': 0.7, 'SNAREBOT': 0.7,

	'AGT1': 0.5, 'AGT2': 0.5,
	'EGT1': 0.5,
	'BASS': 0.6,
	'KEYL': 0.5, 'KEYR': 0.5,
	'MIDIL': 0.5, 'MIDIR': 0.5,

	'BGV1': 0.65,
	'BGV2': 0.65,
	'BGV3': 0.65,
	
	'PLVOC': 0.8,
	'WLVOX1': 0.7,
	'WLVOX2': 0.7,
	'KEYVOX': 0.7,
	'MIDIVOX': 0.7,
}

active_chans = set()

import binascii

class RmsThread(threading.Thread):
	def __init__(self):
		threading.Thread.__init__(self)
		self.daemon = True
		
	def run(self):
		while True:
			data, addr = rsock.recvfrom(1024)
			p = InfoPacket.incoming(data)
			
			#p = InfoPacket.incoming(rms_data)
			#time.sleep(1)

			with open("dump.raw", "a") as f:
				f.write("==")
				f.write(p.data)
				f.write("==\n")
			
			rms = struct.unpack("!128B", p.data[14+3:])

			for i in range(len(rms)):
				ch = i+1
				if ch in channels:
					#print ch, channels[ch], rms[i]
					val = 255-rms[i]
					if val > recent[i]:
						recent[i] = (recent[i] * 0.8) + (val * 0.2)
					else:
						recent[i] = (recent[i] * 0.99) + (val * 0.01)

					ui = channel_ui[i]

					#recent[i] = random.randint(0,254)
					ui.level.set_completion(recent[i])
					title = channels[i+1]

					active = False
					if title in ACTIVE_THRESH:
						active = (float(recent[i]) / 255 > ACTIVE_THRESH[title])
						
					active = True
					if active:
						ui.level.complete = 'active'
						active_chans.add(title)
					else:
						ui.level.complete = 'inactive'
						if title in active_chans:
							active_chans.remove(title)
							
			camera_score()


cur = None
cur_cam = 1

import urllib2



ATEM_HOST = '10.35.36.5'
ATEM_PORT = 9910

def rand(max):
	return int(random.uniform(0,max))

class AtemThread(threading.Thread):
	def __init__(self):
		threading.Thread.__init__(self)
		self.daemon = True
				
	def send_hello(self):
		uid   = (((rand(254) + 1) << 8) + rand(254) + 1) & 0x7FFF
		data  = struct.pack("!HHHH", 0x0100, 0x0000, 0x0000, 0x0000)
		hello = struct.pack("!BBHHHHH", 0x10, 0x14, uid, 0, 0, 0x0000, 0) + data
		self.sock.send(hello)
		return uid
		
	def send_pkt(self, cmd, cout, un1, un2, cin, payload):
		ln = 12 + len(payload)
		cmd += ((ln >> 8) & 0x07)
		pkt = struct.pack("!BBHHHHH", cmd, ln, self.uid, cout, un1, un2, cin) + payload
		#if not ln==12:
		#    print "Send:", hexlify(pkt)
		#    print_pkt(cmd, ln, uid, cout, un1, un2, cin, payload)
		self.sock.send(pkt)

	def recv_pkt(self, data):
		pkt = data
		cmd, len, uid, cnt_out, unkn1, unkn2, cnt_in = struct.unpack("!BBHHHHH", data[0:12])
		payload = data[12:]
		#(port, ipaddr) = sockaddr_in($sock->peername)
		len = ((cmd & 0x07) << 8) + len
		cmd = cmd & 0xF8
		return (cmd, len, uid, cnt_out, unkn1, unkn2, cnt_in, payload)

	def run(self):
		self.sock = socket(AF_INET, SOCK_DGRAM)
		self.sock.connect((ATEM_HOST, ATEM_PORT))
		self.sock.setblocking(False)

		self.uid = self.send_hello()
		self.cnt_in = 0
		self.mycnt = 0

		hello_finished = False
		
		self.outgoing = []
	
		while True:
			if len(self.outgoing) > 0:
				time.sleep(0.5)
				atem.send_pkt(0x88, atem.cnt_in, 0, 0, atem.mycnt, self.outgoing.pop(0))

			try:
				data = self.sock.recv(1024*10)
			except:
				time.sleep(0.02)
				continue

			args = self.recv_pkt(data)
			cmd, ln, self.uid, cnt_out, unkn1, unkn2, self.cnt_in, payload = args
			if cmd & 0x10:
				self.send_pkt(0x80, 0, 0, 0x0050, 0, '')
				continue
			elif cmd & 0x08:
				if self.cnt_in == 0x04 and not hello_finished:
					hello_finished = True
					self.mycnt+=1
					print "Hellofinish"
				if hello_finished:
					self.send_pkt(0x80, self.cnt_in, 0, 0, 0, '')
					self.send_pkt(0x08, 0, 0, 0, self.mycnt, '')
					self.mycnt+=1

			if (self.mycnt == 0 and hello_finished):
				cmd = 0x80
				



atem = AtemThread()
atem.start()





first_run = True

def camera_move(cam, preset):
	global first_run
	#return

	ser = serial.Serial('/dev/ttyUSB0')
	ser.write("\r\n")
	ser.readline()
	
	ser.write("InCtlA %d\r\n" % (cam))
	ser.flush()
	ser.readline()

	ser.write("Preset %d\r\n" % (preset))
	ser.flush()
	ser.readline()
	
	ser.close()
	

	if cam == 1: other_cam = 2
	else: other_cam = 1

	#if first_run:
	#	atem.outgoing.append(struct.pack("!HHHHHH", 0x000c, 0x0000, 0x4350, 0x7649, 0x0000, other_cam))
	#	atem.outgoing.append(struct.pack("!HHHHHH", 0x000c, 0x0000, 0x4350, 0x6749, 0x0000, cam))

	# wait 5 seconds to settle, then ask atem to switch
	time.sleep(6)

	# pull trigger
	#atem.cnt_in = 0
	#atem.mycnt = 0
	atem.outgoing.append(struct.pack("!HHHHHH", 0x000c, 0x0000, 0x4441, 0x7574, 0x00cf, 0xb900))
	
	

stale = 0
scores = {}

def camera_score():
	global scores, stale

	stale += 1
	if stale < 1: return
	else: stale = 0
	
	# okay, time to transition! what's active?
	msg = "active chans %s\n" % (active_chans)

	# map active channels onto audio
	for a in AUDIO:
		a.active = len(a.matches & active_chans) > 0

	# score up active audio
	res = collections.defaultdict(int)
	for a in AUDIO:
		if a.active:
			shots = CONFIG[a]
			for s in range(len(shots)):
				if s == 0:
					sweight = 2
				else:
					sweight = 1-(float(s)/len(shots))
				cweight = a.w * sweight
				s = shots[s]
				res[s] += cweight

	total = 0
	for k, v in res.iteritems():
		total += v

	res2 = sorted(res.iteritems(), key=operator.itemgetter(1), reverse=True)
	summary = []
	for k, v in res2:
		res[k] /= total
		summary.append("%s %f" % (k.__repr__().rjust(20), res[k]))

	while len(summary) < 8: summary.append("")
	msg += "\n".join(summary[:8])

	ui_summary.set_text(msg)
	scores = res


cur = None

def camera_loop():
	global cur_cam, cur, scores
		
	next = None
	pick = random.random()

	#ui_cam.set_text("%d" % (len(scores)))

	for k, v in scores.iteritems():
		pick -= v
		if pick <= 0:
			next = k
			break

	if next is None:
		next = vFULL

	if True or next != cur:
		cur = next
		cur_cam = (cur_cam + 1) % 2
		ui_cam.set_text("%d-%s" % (cur_cam, cur))
		camera_move(cur_cam + 1, cur.preset)

	# camera lingers 10-30 sec
	# 60 sec => 20 sec
	top = min(float(len(active_chans))/6,1)
	top = int(60-(40*top))
	step = random.randint(10,top)
	step = 10

	time.sleep(step)


class CamThread(threading.Thread):
	def __init__(self):
		threading.Thread.__init__(self)
		self.daemon = True
		
	def run(self):
		try:
			while True:
				camera_loop()
		except:
			print >> sys.stderr, sys.exc_info()



rms = RmsThread()
rms.start()

cam = CamThread()
cam.start()

if True:

	def refresh(loop=None, user_data=None):
		loop.set_alarm_in(0.01, refresh)

	loop = urwid.MainLoop(page, palette, unhandled_input=exit_on_q)
	refresh(loop, None)
	loop.run()

	exit(0)

else:
	time.sleep(20)
