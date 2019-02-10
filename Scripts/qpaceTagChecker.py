#!/usr/bin/env python3
# qpaceTagChecker.py by Eric Prather, edits by Jonathan Kessluk
# 2-7-2019, Rev. 1
# Q-Pace project, Center for Microgravity Research
# University of Central Florida
#
# The TagChecker class is to be implemented and used for XTEA encrypted packets. A packet is corrupted
# Or invalid and should be dropped if the tag is not valid. See Pi documentation for more information.

import random
import os.path

class TagChecker:
	"""
    TagChecker supplies tags (unique 2 character strings) from a hardcoded set, with a few certain restrictions.
    """
	##CONSTANTS
	MINIMUM_TAGS = 4; #The minimum number of tags which can be in the master list
	LOCK_CALLS = 3; #The amount of inputs or outputs to this class required before a tag is freed for re-use. Should be shorter than MINIMUM_TAGS
	TAG_DELIMINATOR = b'/' #The character to split tags by when reading from a file
	DEFAULT_FILEPATH = "/home/pi/valid_tags.secret" #The filename the tags are expected to be found in if a specific one is not provided
	DEFAULT_FILEPATH = "/mnt/c/users/jonat/desktop/cmr/pi/Scripts/valid_tags.secret"


	##METHODS
	def __init__(self):
		"""Starting out with no tags in use"""
		##PROPERTIES
		self.tags = [] #File tag values will be placed here
		self.used = [] #Keeps track of which tags have been used

		#initTags()
		random.seed()

	def initTags(self, filename = DEFAULT_FILEPATH):
		"""Reads tags from a file, as indicated by filename, for use in this class.
		Throws an error if the filename does not have a sufficient number of tags"""
		tf = ""
		if TagChecker.LOCK_CALLS >= TagChecker.MINIMUM_TAGS:
			raise ValueError('LOCK_CALLS cannot be greater than MINIMUM_TAGS.')
		if not os.path.isfile(filename):
			raise FileNotFoundError("No tag file found at " + filename)
		with open(filename,'rb') as tagSource:
			tf = tagSource.read()
		potentialTags = tf.split(TagChecker.TAG_DELIMINATOR)
		for t in potentialTags:
			if TagChecker._isFormattedTag(t):
				self.tags.append(t)
		if len(self.tags) < TagChecker.MINIMUM_TAGS:
			raise RuntimeError('File did not have at least ' + str(TagChecker.MINIMUM_TAGS) + ' tags: '  + filename)
		self.tags = tuple(self.tags)

	def getTag(self):
		"""Gets a tag from the hardcoded tuple which has not been utilized recently"""
		options = self._validTags()
		selected = random.choice(options)
		self._pushUsed(selected)
		return tuple(selected)

	def isValidTag(self, toCheck):
		"""Checks to see if a tag is formatted correctly, and if it is, marks it as used."""
		options = self._validTags()
		if toCheck in options:
			self._pushUsed(toCheck)
			return True
		return False

	def _validTags(self):
		"""Returns a list of all of the valid (Currenetly unused) tags"""
		options = []
		if self.tags:
			for t in self.tags:
				if t not in self.used:
					options.append(t)
					return options
		else:
			return []

	def _isFormattedTag(toCheck):
		"""Checks to see if a string is 2 characters long"""
		return len(toCheck) == 2

	def _pushUsed(self, newTag):
		"""Adds a tag to the list of used tags, pushing them off of the end if there are more than LOCK_CALLS tags in recent memory"""
		#I know this isn't an actual queue but shh

		#Dequeue until of appropriate size
		while len(self.used) >= TagChecker.LOCK_CALLS:
			for i in range(len(self.used) - 1):
				self.used[i] = self.used[i+1]
			del self.used[len(self.used)-1]

		#Enqueue
		self.used.append(newTag)