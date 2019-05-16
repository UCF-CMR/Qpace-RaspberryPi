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
	DEFAULT_FILEPATH = "/valid_tags.secret" #The filename the tags are expected to be found in if a specific one is not provided


	##METHODS
	def __init__(self):
		"""
		Constructor for TagChecker()

		Parameters: None

		Returns: None

		Raises: None

		"""
		##PROPERTIES
		self.tags = [] #File tag values will be placed here
		self.used = [] #Keeps track of which tags have been used
		self.used_Sent = [] #Keeps Track of which tag has been sent

		#initTags()
		random.seed()

	def initTags(self, filename = DEFAULT_FILEPATH):
		"""
		Reads tags from a file, as indicated by filename, for use in this class.
		Throws an error if the filename does not have a sufficient number of tags

		Parameters:
		filename - optional - implemented for configurable tag location.

		Returns: None

		Raises:
		ValueError - if LOCK_CALLS is >= MINIMUM_TAGS
		FileNotFoundError - if the file of tags cannot be found.
		RuntimeError - if the file does not have the minimum amount of tags.

		"""
		print("Inside initTags")
		tf = ""
		if TagChecker.LOCK_CALLS >= TagChecker.MINIMUM_TAGS:
			raise ValueError('LOCK_CALLS cannot be greater than MINIMUM_TAGS.')
		if not os.path.isfile(filename):
			raise FileNotFoundError("No tag file found at " + filename)
		with open(filename,'rb') as tagSource:
			tf = tagSource.read()
		potentialTags = tf.split(TagChecker.TAG_DELIMINATOR)
		for t in potentialTags:
			print("Trying to add potential Tag...", t)
			if TagChecker._isFormattedTag(t):
				self.tags.append(t)
		if len(self.tags) < TagChecker.MINIMUM_TAGS:
			raise RuntimeError('File did not have at least ' + str(TagChecker.MINIMUM_TAGS) + ' tags: '  + filename)

	def getTag(self):
		"""
		Gets a valid tag randomly from the list of valid tags.

		Parameters: None

		Returns: 2-byte valid tag

		Raises: None

		"""
		#logger.logInfo("ENTER GETTAG")
		options = self._validTags(1)  #Sending to Ground List
		selected = random.choice(options)
		self._pushUsed(selected, 1)  #Sending to Ground List
		#logger.logInfo("EXIT GETTAG")
		return selected

	#Enter 0 for list of items sent to station
	#Enter 1 For list of items sent to ground
	def isValidTag(self, toCheck):
		"""
		Checks if a tag is valid

		Parameters:
		toCheck - the 2-byte tag to check.

		Returns: True if valid, false otherwise

		Raises: None

		"""
		#logger.logInfo("ENTER isValidTag")
		options = self._validTags(0)  #Tags Sent From Ground to Pi
		print("The tag in this packet is ", toCheck)
		if toCheck in options:
			self._pushUsed(toCheck, 0)  # Tags Sent From Ground to Pi
			#logger.logInfo("Exit isValidTag True")
			return True
		#logger.logInfo("Exit False isValidTag")
		return False

	#Enter 0 for list of items sent to station
	#Enter 1 For list of items sent to ground
	def _validTags(self, NumberList):
		"""
		Put togehter a list of all valid tags

		Parameters: None

		Returns: a list of valid tags

		Raises: None

		"""

		options = []
		if self.tags:
			for t in self.tags:
				if t not in (self.used_Sent if NumberList else self.used):
					options.append(t)
			return options
		else:
			return []

	def _isFormattedTag(toCheck):
		"""
		Check if a tag is formatted correctly.
		May become more complex in the future.

		Parameters:
		toCheck - the data to check if it's a valid tag

		Returns: True or false depending on if the tag meets all the conditions

		Raises: None

		"""
		return len(toCheck) == 2

	#Enter 0 for list of items sent to station
	#Enter 1 For list of items sent to ground
	def _pushUsed(self, newTag, NumberList):
		"""
		Push used tags onto the list. If the size of the list becomes greater than LOCK_CALLS
		then pop off the least recently used tags.

		Parameters: newTag - the tag to push onto the list

		Returns: None

		Raises: None

		"""
		#logger.logInfo("entered: pushedUsed")
		ListToCheck = self.used_Sent if NumberList else self.used  #Pointer assignment
		NameOfList = " SENT TO GROUND" if NumberList else "RECEIVED FROM GROUND"
		#logger.logResults("BEFORE WE PUSH FOR LIST: {0}\nContents: {1}\n".format(NameOfList, ListToCheck))
		#Dequeue until of appropriate size
		while len(ListToCheck) >= TagChecker.LOCK_CALLS:
			for i in range(len(ListToCheck) - 1):
				ListToCheck[i] = ListToCheck[i+1]
			del ListToCheck[len(ListToCheck)-1]

		#Enqueue
		ListToCheck.append(newTag)
		#logger.logResults("AFTER WE PUSH FOR LIST: {0}\nContents: {1}\n".format(NameOfList, ListToCheck))
		#logger.logInfo("exited: pushedUsed")
