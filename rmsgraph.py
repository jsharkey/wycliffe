
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

import sys, struct, re, threading, time
import socket
import urwid
import collections
import binascii
import urllib2
import numpy
import dbus
import telnetlib
import paramiko
import errno
import math

# apt-get install python-numpy python-serial
# apt-get install libqt4-dev
# apt-get install python-dbus
# apt-get install python-paramiko
# apt-get install python-dev python-pip
# pip install urwid


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


# camera presets
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
vPULPIT = Shot(13, "vPULPIT")

# audio clusters
aPLVOX = Channel("aPLVOX", 1.2, "PLVOX,PLVOC")
aWLVOX = Channel("aWLVOX", 0.8, "WLVOX1,WLVOX2")
aBGV = Channel("aBGV", 0.8, "BGV1,BGV2,BGV3")
aKEYVOX = Channel("aKEYVOX", 0.6, "KEYVOX")
aMIDIVOX = Channel("aMIDIVOX", 0.6, "MIDIVOX")
aWLINST = Channel("aWLINST", 0.5, "EGT1,EGT2,AGT1,AGT2")
aKEY = Channel("aKEY", 0.5, "KEYL,KEYR,KEY")
aMIDI = Channel("aMIDI", 0.5, "MIDIL,MIDIR,MIDI")
aDRUMS = Channel("aDRUMS", 0.5, "DRUMS,KICK,SNAREBOT,SNARETOP,OHL,OHR")
aBASS = Channel("aBASS", 0.5, "BASS")

AUDIO = [aPLVOX,aWLVOX,aBGV,aKEYVOX,aMIDIVOX,aWLINST,aKEY,aMIDI,aDRUMS,aBASS]

# mapping from audio cluster to list of camera presets covering them
CONFIG = {
	aPLVOX: [vPL,vR,vCR],
	aWLVOX: [vWL,vC,vCR,vCL,],
	aBGV: [vBG,vR,vCR,],
	aKEYVOX: [vKEYS,vL,vCL,],
	aMIDIVOX: [vMIDI,vCR,],

	aWLINST: [vWL,vC,vCR,vCL,],
	aKEY: [vKEYS,vL,vCL,],
	aMIDI: [vMIDI,vCR,],
	aDRUMS: [vDRUMS,vCL,],
	aBASS: [vL,vCL,],
}

for c, v in CONFIG.iteritems():
	while None in v:
		v.remove(None)

def exit_on_q(key):
    if key in ('q', 'Q'):
        raise urwid.ExitMainLoop()

palette = [
    ('banner', 'black', 'light gray'),
    ('streak', 'black', 'dark red'),
    ('raw', 'black', 'dark green'),
    ('inactive', 'black', 'dark blue'),
    ('active', 'black', 'dark red'),
]

rows = []
channel_ui = []

ui_summary = urwid.Text(('label', u"[camera summary]"), align='left')
ui_cam = urwid.BigText('[]', urwid.font.HalfBlock5x4Font())
ui_log = urwid.Text(('label', u"[log]"), align='left')


wrapped_ui_cam = urwid.Padding(ui_cam, width='clip')
rows.append(urwid.Columns([ui_summary, ('weight', 0.3, wrapped_ui_cam)], dividechars=1))


class VisualChannel():
	def __init__(self, i):
		self.label = urwid.Text(('label', u"CH%d" % (i)), align='right')
		self.raw = urwid.ProgressBar('', 'raw', 0, 255)
		self.level = urwid.ProgressBar('', 'inactive', 0, 255)
		#self.level_color = urwid.AttrMap(self.level, 'active')
		self.row = urwid.Columns([	('weight', 0.1, self.label),
									('weight', 0.5, self.raw),
									('weight', 0.1, self.label),
									('weight', 0.5, self.level)], dividechars=1)

for i in range(1,128):
	ch = VisualChannel(i)
	channel_ui.append(ch)
	if 0 < i <= 8 or 16 < i <= 24 or 32 < i <= 40 or 48 < i <= 56:
		rows.append(ch.row)

rows.append(ui_log)

page = urwid.ListBox(urwid.SimpleFocusListWalker(rows))
loop = urwid.MainLoop(page, palette, unhandled_input=exit_on_q)


LOG_SIZE = 16
log_buffer = collections.deque(maxlen=LOG_SIZE)

def log(msg):
	global log_buffer
	log_buffer.append("[%s] %s" % (time.strftime("%I:%M:%S %p", time.localtime()), msg))
	ui_log.set_text("\n".join(log_buffer))

for i in range(0,LOG_SIZE):
	log('.')


force_next = threading.Event()

DANTE = "10.35.0.2"
CTL_PORT = 8800
INFO_PORT = 4440
RMS_PORT = 8751

LOCAL_IDENT = "001c25bf39850000"
#LOCAL_IDENT = "CAFECAFECAFE0000"
LOCAL_IP = "10.35.0.6"

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
#data = "271201bf000920100001201e00010001010c00020002011100030003011a00040004012300050005012700060006012b00070007013000080008013500090011013c000a00120141000b00130146000c0014014d000d00150152000e00160159000f0017015e00100018016300110021016800120022016e00130023017400140024017a00150025018400160026018c00170027019100180028019800190031019d001a003201a2001b003301a7001c003401ae001d003701b5001e003801ba003a000e016801ab014f01ae0000000100000000003b000e016801b1014f01b40000000100000000003c000e016801b7014f01ba0000000100000000003d000e016801bd014f01c0000000014b49434b00534e415245544f5000534e41524542544d004f484c004f485200544f4d3100544f4d320044434c49434b0041475431004547543100574c564f5831004147543200574c564f583200424756310042475632004247563300504c564f43004d4944494c004d49444952004d494449434c49434b004d494449564f580042415353004b4559564f58004b45594c004b4559520045475432004d494449324c004d494449325200464f484c00464f485200".decode("hex")
data = "271201cb000920100001202000010001010c00020002011100030003011a00040004012300050005012700060006012b00070007013000080008013500090011013c000a00120141000b00130146000c0014014d000d00150152000e00160159000f0017015e00100018016300110021016800120022016e00130023017400140024017a00150025018400160026018c00170027019100180028019800190031019d001a003201a2001b003301a7001c003401ae001d003701b5001e003801ba001f003601bf0020003501c60000000100000000003b000e016801b1014f01b40000000100000000003c000e016801b7014f01ba0000000100000000003d000e016801bd014f01c0000000014b49434b00534e415245544f5000534e41524542544d004f484c004f485200544f4d3100544f4d320044434c49434b0041475431004547543100574c564f5831004147543200574c564f583200424756310042475632004247563300504c564f43004d4944494c004d49444952004d494449434c49434b004d494449564f580042415353004b4559564f58004b45594c004b4559520045475432004d494449324c004d494449325200464f484c00464f48520050554c50495400494d414300".decode("hex")

p = InfoPacket.incoming(data)
total, ret = struct.unpack("!BB", p.data[0:2])
channels = {}
channels_rev = {}

for n in range(ret):
	ptr = 2+(n*6)
	n, target, label_ptr = struct.unpack("!3H", p.data[ptr:ptr+6])
	label_ptr -= 10
	label = p.data[label_ptr:p.data.index("\0", label_ptr)]
	target -= 1
	channels[target] = label
	channels_rev[label] = target
	channel_ui[target].label.set_text(label)




# parse rms
rms_data = "ffff009b3ca00000001dc10412e20000417564696e617465024040bfc9c4b8bcbcb8a9bfc9c4b8bcbcb8a9a7a88bac88afb1afa7a88bac88afb1afb0cccbcdb29ca6c0b0cccbcdb29ca6c0c4b1cccafefee3e2c4b1cccafefee3e2fefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefe".decode("hex")


csock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
csock.bind(('', CTL_PORT))

rsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
rsock.bind(('', RMS_PORT))
#rsock.setsockopt(SOL_SOCKET, SO_RCVBUF, 1)
#rsock.setsockopt(SOL_SOCKET, SO_TIMESTAMP, 1)


def init_rms():
	global csock
	
	log("init_rms()")
	
	# request rms stream
	p = InfoPacket.outgoing(0x1200, 0xeeee, 0x3010, 0x0000)
	p.append_hex("0000")
	p.append_hex(LOCAL_IDENT)
	p.append_hex("0004 0018 0001 0022 000a")
	p.append_raw("DN965x-0412e2\0admii-PC\0")
	p.append_hex("00 0001 0026 0001")
	p.append_raw(struct.pack("!H", RMS_PORT))
	p.append_hex("0001 0000")
	p.append_raw(socket.inet_pton(socket.AF_INET, LOCAL_IP))
	p.append_raw(struct.pack("!H", RMS_PORT))
	p.append_hex("0000")

	csock.sendto(p.pack(), (DANTE, CTL_PORT))


MFI_PASS = open("../mfi.pwd").read().strip()

def kick_dante():
	# first poke our heads around to inspect
	
	ssh = paramiko.SSHClient()
	ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
	ssh.connect('10.35.0.7', username='admin', password=MFI_PASS, timeout=20)
	
	stdin, stdout, stderr = ssh.exec_command("cat /proc/power/active_pwr1")
	pwr = float(stdout.read().strip())
	log("kick_dante() found active_pwr1 at %f" % pwr)
	
	if pwr < 1 or pwr > 14:
		log("kick_dante() cycling power!")
		ssh.exec_command("echo 0 > /proc/power/relay1")
		time.sleep(1)
		ssh.exec_command("echo 1 > /proc/power/relay1")
		time.sleep(60)
	
	ssh.close()



ACTIVE_THRESH = {
	'KICK': 0.5,
	'OHR': 0.5, 'OHL': 0.5,
	#'TOM1': 0.2, 'TOM2': 0.2,
	'SNARETOP': 0.5, 'SNAREBOT': 0.5,

	'AGT1': 0.55, 'AGT2': 0.55,
	'EGT1': 0.55, 'EGT2': 0.55,
	'BASS': 0.55,
	'KEYL': 0.55, 'KEYR': 0.55,
	'MIDIL': 0.55, 'MIDIR': 0.55,

	'BGV1': 0.05,
	'BGV2': 0.05,
	'BGV3': 0.05,
	'PLVOC': 0.05,
	'WLVOX1': 0.05,
	'WLVOX2': 0.05,
	'KEYVOX': 0.05,
	'MIDIVOX': 0.05,

	'IMAC': 0.45,
	'PULPIT': 0.45,
}

# mic-based channels that need filtering
# will be normalized against first channel
FILTER_CHANS = ["FOHL",
	"BGV1","BGV2","BGV3","PLVOC","WLVOX1","WLVOX2","KEYVOX","MIDIVOX",
	#"KICK","SNARETOP","SNAREBTM","OHL","OHR",#"PULPIT"
	#"AGT1","AGT2","EGT1","EGT2","BASS",
	#"MIDIL","MIDIR","KEYL","KEYR","MIDI2L","MIDI2R",
]
PREEMPT = ["PLVOC","PULPIT","IMAC"]
NORM_CHANS = FILTER_CHANS[1:]
FILTER_HISTORY = 100

last_rms = None
last_init = None
rms_history = collections.deque(maxlen=FILTER_HISTORY)
res_decay = collections.defaultdict(lambda: 0)
active_chans = set()

class RmsThread(threading.Thread):
	def __init__(self):
		threading.Thread.__init__(self)
		self.daemon = True
		
	def run(self):
		global last_rms, last_init, rms_history, active_chans, force_next
		
		dead_count = 0
		
		while True:
			try:
				# periodically re-init to avoid lag
				if last_init is None or time.time() - last_init > 30:
					init_rms()
					last_init = time.time()
				
				if dead_count > 60*10:
					log("RMS appears dead for %d samples; kicking" % dead_count)
					dead_count = 0
					kick_dante()
				
				# read everything pending
				collected = 0
				start = time.time()
				while time.time() - start < 0.2:
					rsock.setblocking(0)
					try:
						data, addr = rsock.recvfrom(1024)
					except socket.error as e:
						if e.errno == errno.EWOULDBLOCK:
							time.sleep(0.1)
							continue
						else:
							raise
						
					p = InfoPacket.incoming(data)
					collected += 1
					
					#p = InfoPacket.incoming(rms_data)
					#time.sleep(1)

					with open("dump.raw", "a") as f:
						f.write("==")
						f.write(p.data)
						f.write("==\n")
					
					rms = struct.unpack("!128B", p.data[14+3:])
					rms = [254-val for val in rms]
					
					if sum(rms) == 0:
						dead_count += 1
					else:
						dead_count = 0
					
					# TODO: remove testing data
					#rms = [random.randint(0,254) for val in rms]
					#rms = [32 for val in rms]
					
					if last_rms is None:
						last_rms = rms
						continue
					
					# filter transient spikes/drops
					# they happen frequently enough, and mess with stddev
					#for i in range(64):
					#	if rms[i] < (last_rms[i] - 60):
					#		rms[i] = last_rms[i]
					
					# accumulate rms history
					rms_history.append(rms)
				
				if collected != 10:
					pass
					#log("Collected %d samples, total history %d" % (collected, len(rms_history)))
				if collected == 0:
					dead_count += 10
					continue
				
				# calculate stddev for each filter channel
				# other channels just passthrough from copy
				res = rms[:]
				for ch_label in FILTER_CHANS:
					ch_index = channels_rev[ch_label]
					recent = [ rec[ch_index] for rec in rms_history ]
					res[ch_index] = numpy.std(recent)
					
				# and normalize against first channel
				key_index = channels_rev[FILTER_CHANS[0]]
				for ch_label in NORM_CHANS:
					ch_index = channels_rev[ch_label]
					res[ch_index] -= res[key_index]
					res[ch_index] *= 4
				
				for i in range(len(res)):
					ch = i
					if ch in channels:
						val = res[i]
						ui = channel_ui[i]

						if math.isnan(val): continue
						
						# jump quickly, but decay slowly
						if val > res_decay[i]:
							res_decay[i] = (res_decay[i] * 0.1) + (val * 0.9)
						else:
							res_decay[i] = (res_decay[i] * 0.9) + (val * 0.1)
						
						val = res_decay[i]

						ui.raw.set_completion(rms[i])
						ui.level.set_completion(val)
						label = channels[i]
						
						active = False
						if label in ACTIVE_THRESH:
							active = (float(val) / 255 > ACTIVE_THRESH[label])
							
						if active:
							ui.level.complete = 'active'
							if label not in active_chans and label in PREEMPT:
								# important channel coming alive; wake up camera!
								force_next.set()
							
							active_chans.add(label)
						else:
							ui.level.complete = 'inactive'
							if label in active_chans:
								active_chans.remove(label)
								
				camera_score()

			except:
				log("RmsThread error: %s" % str(sys.exc_info()))


cur = None
cur_cam = 1

first_run = True


bus = dbus.SessionBus()

atem = bus.get_object('com.blackmagicdesign.QAtemConnection', '/QAtemConnection')
atem = dbus.Interface(atem, dbus_interface='com.blackmagicdesign.QAtemConnection')

ENABLE_SERIAL = False
ENABLE_TELNET = True

def camera_move(cam, preset):
	global first_run, atem
	
	log("camera_move() input %s, preset %s" % (str(cam), str(preset)))
	
	if ENABLE_SERIAL and preset is not None:
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
	
	if ENABLE_TELNET and preset is not None:
		tel = telnetlib.Telnet()
		tel.open('10.35.0.3', 10001)
		tel.write("\r\n")
		tel.read_until(">")
		tel.write("InCtlA %d\r\n" % (cam))
		tel.read_until(">")
		tel.write("Preset %d\r\n" % (preset))
		tel.read_until(">")
		tel.close()

	if cam == 1: other_cam = 2
	elif cam == 2: other_cam = 1
	else: other_cam = cam
	#other_cam = cam

	if first_run:
		atem.disconnectFromSwitcher()
		atem.connectToSwitcher("10.35.36.5")
		time.sleep(1)
		atem.changeProgramInput(cam)
		time.sleep(1)
		atem.changePreviewInput(other_cam)
		first_run = False
	else:
		atem.changePreviewInput(other_cam)
	
	# wait for camera to settle, then ask atem to switch
	time.sleep(6)
	
	# pull trigger
	atem.doAuto()


stale = 0
scores = {}

def camera_score():
	global scores, stale

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

def camera_next(loop=None, user_data=None):
	global cur_cam, cur, scores
		
	next = None
	pick = random.random()

	for k, v in scores.iteritems():
		# always pick at least one preset
		if next is None:
			next = k
		pick -= v
		# but it's lame to pick same preset twice in row
		if k == cur:
			continue
		if pick <= 0:
			next = k
			break

	# camera lingers 10-30 sec
	# 60 sec => 20 sec
	top = min(float(len(active_chans))/6,1)
	top = int(60-(40*top))
	step = random.randint(10,top)

	# if stream is active, lock to logo
	if "IMAC" in active_chans:
		next = None
		step = 15
		
	# if pulpit, we lock to specific camera preset
	# we want to end up on rear preset, but we might take a detour before landing
	if "PULPIT" in active_chans:
		next = vPULPIT
		step = 15

	if next is None:
		# nothing active, switch to graphic
		ui_cam.set_text("LOGO")
		camera_move(12, None)
	else:
		# we have active channels, switch it up!
		do_switch = True
		
		# if we're on rear pulpit, sit tight
		if next == vPULPIT and cur_cam == 1:
			do_switch = False

		cur = next
		if do_switch:
			cur_cam = (cur_cam + 1) % 2
			camera_move(cur_cam + 1, cur.preset)

		ui_cam.set_text("%d-%s" % (cur_cam, cur))
	
	return step


class CamThread(threading.Thread):
	def __init__(self):
		threading.Thread.__init__(self)
		self.daemon = True
		
	def run(self):
		global force_next
		while True:
			try:
				linger = camera_next()
				
				log("CamThread lingering for %d seconds" % (linger))
				if force_next.wait(linger):
					log("CamThread linger was preempted!")
				force_next.clear()
				
			except:
				log("CamThread error: %s" % str(sys.exc_info()))



rms = RmsThread()
rms.start()

cam = CamThread()
cam.start()

if True:
	def refresh(loop=None, user_data=None):
		loop.set_alarm_in(0.05, refresh)

	refresh(loop, None)
	loop.run()

	atem.disconnectFromSwitcher()

	exit(0)

else:
	time.sleep(20)
