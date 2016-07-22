# There's probably a more proper generator way of doing this
# but eh.

class FSNode:

	def __init__(self, parent_in = None):
		# Self.children will be a dict (to make lookups by name fast) but
		# starts off as None to save memory (since most nodes will be leaf
		# nodes)
		self.children = None
		self.value = None

		# Which nodes are we contained in?
		self.contained_in = set()

		# Do we know what nodes we are contained in?
		# Needed because set() might mean "contained in nothing".
		self.does_know_contained_in = False 

		self.parent = parent_in

	def has_child(potential_child):
		return potential_child in self.children

	def add_child(self, child):
		if (child == self):
			raise Exception("Cycles are not allowed; can't add oneself",
				"as child")

		if self.children == None:
			self.children = {}

		self.children[child.get_value().get_name()] = child

	def get_children(self):
		if self.children == None:
			return []

		return self.children.itervalues() 	# danger! can write to this

	def get_child_by_name(self, name):
		if self.children != None and name in self.children:
			return self.children[name]
		else:
			return None

	def get_parent(self): return self.parent

	# Is this any different than just making the vars global?
	def set_value(self, value_in):	self.value = value_in
	def get_value(self):			return self.value

	def knows_contained_in(self):
		return self.does_know_contained_in

	def set_contained_in(self, in_what):
		self.contained_in.update(in_what)
		self.does_know_contained_in = True

	def get_contained_in(self):
		return self.contained_in

	def dfs(self, function, depth=0):	# depth-first traversal
		function(self, depth)
		for child in self.get_children():
			child.dfs(function, depth+1)