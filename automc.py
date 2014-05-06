
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

class Channel():
	def __init__(self, title, w, matches):
		self.title = title
		self.w = w
		self.matches = set(matches.split(","))

	def __repr__(self):
		return self.title

class Shot():
	def __init__(self, preset, title):
		self.preset = preset
		self.title = title

	def __repr__(self):
		return self.title


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

aPLVOX = Channel("aPLVOX", 1.2, "PLVOX")
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



# example active audio duration and set
SET = [
	[2, "KEY"],
	[2, "KEY,KEYVOX"],
	[4, "KEY,PLVOX"],
	[2, "KEY,EGT1"],
	[2, "KEY,EGT1,DRUMS"],
	[4, "KEY,EGT1,DRUMS,WLVOX1,WLVOX2"],
	[4, "KEY,EGT1,DRUMS,MIDI,WLVOX1,WLVOX2"],
	[4, "KEY,EGT1,DRUMS,MIDI,WLVOX1,WLVOX2,BGV1,BGV2,BGV3"],
	[6, "KEY,EGT1,DRUMS,MIDI,WLVOX1,WLVOX2,BGV1,BGV2,BGV3,PLVOX"],
	[2, "EGT1,DRUMS,BASS,PLVOX"],
	[2, "EGT1,DRUMS,BASS,WLVOX1,BGV1"],
	[2, "EGT1,DRUMS,BASS,PLVOX"],
	[2, "EGT1,DRUMS,BASS,BGV1,BGV2"],
	[4, "KEY,DRUMS,BASS,MIDI,WLVOX1"],
	[4, "KEY,DRUMS,MIDI"],
	[4, "MIDI"],
	[4, "MIDI,KEY,KEYVOX"],
	[8, "KEY,KEYVOX"],
	[4, "KEY,PLVOX"],
]


# keep chewing items off set
while len(SET) > 0:

	# okay, time to transition! what's active?
	dur, chans = SET[0]
	chans = set(chans.split(","))
	print "active chans", chans,

	# map active channels onto audio
	for a in AUDIO:
		a.active = len(a.matches & chans) > 0

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

	#print
	total = 0
	for k, v in res.iteritems():
		total += v

	shots = sorted(res.iteritems(), key=operator.itemgetter(1), reverse=True)
	for k, v in shots:
		v /= total
		#print "\t%s\t%f" % (k, v)

	pick = random.random() * total
	for k, v in res.iteritems():
		pick -= v
		if pick <= 0:
			print "\tPICK SHOT", k,
			cur = k
			break

	# camera lingers 10-30 sec
	# 60 sec => 20 sec
	top = min(float(len(chans))/6,1)
	top = int(60-(40*top))
	step = random.randint(10,top)
	print "and holding for", step, "sec"
	SET[0][0] -= (float(step)/60)
	if SET[0][0] <= 0: del SET[0]
	if len(SET) == 0: break


# TODO: keep a thread that watches RMS levels
# keep an exponential decay and "active" when still beyond threshold

# InCtlA 1\n
# Preset 1\n
