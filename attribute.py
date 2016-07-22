# Attribute (value) for the tree nodes
# This will contain the following:
#	- File/directory name
#	- Hash
#	- File size

# QND indeed, more like a struct
# If we're making this hashable, make sure to make it immutable too!

# If we ever clean up nameless and make it work, the attribute could
# be redone by having a "nameless" property that removes name from cmp
# and hash considerations. Other things that could be done: implement
# both real size and apparent size.

class Attribute:

	def __cmp__(self, other):
		if cmp(self._size, other.get_size()) != 0:
			return cmp(self._size, other.get_size())

		if cmp(self._hash, other.get_hash()) != 0:
			return cmp(self._hash, other.get_hash())

		return cmp(self._name, other.get_name())

	def non_name_comp(self, other):
		if cmp(self._size, other.get_size()) != 0:
			return cmp(self._size, other.get_size())
		
		return cmp(self._size, other.get_size())

	def __eq__(self, other):
		return cmp(self, other) == 0

	def __init__(self, name_in, hash_in, size_in):
		self._name, self._hash, self._size = name_in, hash_in, size_in

		self._ourhash = hash(self._size) ^ hash(self._hash) ^ \
			hash(self._name)

	def __hash__(self):
		return self._ourhash

	def get_name(self):		return self._name
	def get_hash(self):		return self._hash
	def get_size(self):		return self._size
	def get_hash_and_size(self):
		# HACK HACK HACK
		# Since self.size == 0 is so common, give name as well in that case.
		if self._size == 0:
			return(self._name, self._hash, self._size)
		return (self._hash, self._size)
