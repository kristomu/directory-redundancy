# WARNING: UNMAINTAINED. Needs cleanup at some point
# This sis like srec, but it doesn't take names into account; so if
# all files in X are contained in Y, but the corresponding files in Y have
# different names, this will catch it and srec won't.
#---------------------------------------------------

# Implement a new tree-based approach for finding out which directories are
# redundant.

# A directory X is redundant if there's some other directory Y that 
# contains X.

# Subtree Y contains subtree X if:
#	Y's root node has equal attributes to X's root node.
#	All of the children of Y are contained in first level children of X.

# (Clearly X always contains X, but we're not interested in that.)

# We want something weaker for the printout, call it weakly contained.
#	Y weakly contains X if
#	All of the children of Y are contained in first level children of X.
# (So that if all files in A are also in B, B weakly contains A even though
#  the name B is not the same as the name A.)

# Too bad Python doesn't support tail call optimization.

# ---

# Clearly nameless is not going to work as is. We're going to have to
# combine weakly and strongly contained, I think. 
# We can try some pruning first, though.

# General idea: if we remove a lot of small files, then we'll get false
# positives (X is contained in Y when it isn't) but no false negatives
# (X is not contained in Y when it is). 

# First order speedup would be to use pointers instead of copies, but this
# will require some diligence. E.g. if X has no children, X's contained-in
# is a list of all the others, so it can just be a pointer to the dict.
# If X *has* children, then we need a new structure (i.e. a copy). We can
# similarly augment the assignment dict with a list of the parents. Oh, this
# is going to be ugly. Of course, that does mean that we'll have to handle
# "X is contained in X" implicitly.

# Another structure might help.
#	Let directories have one child that represents the files therein, say
#		as a counting dict of hashes.
#	Then find which contain the files directly by taking the file nodes
#	that contain, say, the first file, and subtracting their counting dicts
#	from ours. It'll be pretty obvious which can contain us that way.
#		Elaborate on this when I'm not as sleepy.
#		https://docs.python.org/2/library/collections.html#collections.Counter

# Preprocessing step 2 idea: find all unique files and collapse them into an
# ancestor directory "unique" node.
# Similarly, if B appears everywhere A does, collapse A and B into an 
# artificial [A,B] node.
#	Take the list of all files with the same ID, sort by parent, and replace
#	blocks with a single node. Have to take into account partial matches too..

from filetree import *
from attribute import *
from collections import defaultdict
import sys, time, math

# TODO: hash_in -> target_hash, size_in -> target_size
def append_path(root_node, path_list, hash_in, size_in, same_attribute_dict):

	# Descend down the nodes given by the item names (directory or file
	# names), creating new nodes for each file/directory not yet recorded.
	# The final node gets the hash and size data that were input.

	pathlen = len(path_list)
	counter = 0
	cur_node = root_node

	for next_item in path_list:
		counter = counter + 1

		# If the pathname is ".", that's just the root. Skip.
		if next_item == ".":
			continue

		# If the node has a child with the item name in question,
		# descend there.
		matching_child = cur_node.get_child_by_name(next_item)
		if matching_child != None:
			cur_node = matching_child
			continue

		# Create a new node. If it's the last, give it hash_in, size_in
		# attributes.
		newchild = FSNode(cur_node)
		if counter == pathlen:
			newchild.set_value(Attribute(next_item, hash_in, size_in))
		else:
			newchild.set_value(Attribute(next_item, "", -1))

		cur_node.add_child(newchild)
		cur_node = newchild

		# Insert the new node into the by-attribute dictionary. The
		# point of this dictionary is to quickly find all nodes that
		# have the same attributes as a given node.
		same_attribute_dict[cur_node.get_value().get_hash_size()].add(cur_node)
	return

# functions for printing out the pathname from a node

def get_reverse_full_path_list(node, output):
	output.append(node.get_value().get_name())

	if node.get_parent() != None:
		get_reverse_full_path_list(node.get_parent(), output)

def get_full_path(node):
	reverse_path = []
	get_reverse_full_path_list(node, reverse_path)
	reverse_path.reverse()
	return "/".join(reverse_path)

def dfs_debug_contain_reach(node, depth):
	if not node.knows_contained_in():
		print "WTH? This node hasn't been reached:", get_full_path(node)

#---#

def is_parent_admitted(node, prosp_parent):
	# We're given a prospective parent and a node.
	# A parent is admitted if each child of the node we're checking against
	# is contained in different children of the parent, i.e. that it's
	# possible to set up a bijection.
	
	# This is a bit tricky. The idea is to add in the first node we haven't
	# already seen if there is one. If there isn't any, we're done; that
	# parent isn't suited.
	# Proof that we can just pick the first unseen containing node instead
	# of having to pick a particular node ... is left to the reader :p

	containing_nodes = set()
	# HACK HACK HACK
	def x():
		for poss_container in child.get_contained_in():
			if poss_container.get_parent() == prosp_parent and \
			poss_container not in containing_nodes:
				containing_nodes.add(poss_container)
				return True
		return False

	for child in node.get_children():
		if not x():
			return False

	return True # Pigeonhole

#---#
#counter_hack: list containing [counter, cycle]. When cycle is 1000 or whatnot
#we print current name and counter.

# ADDENDUM 2016: It seems pretty clear what's slowing this down. If we're
# nameless, then every directory matches every other directory. That then
# implies that we have to check every directory against every other, and n^2
# is far from cheap. Some serious pruning will be required.

# Here are some ideas:
#	- If we're more leafwards than the other entrant, we can't contain it.
#	- If we have more files than the other entrant, it can't contain us.

# But really, it has to be done bottom-up.

def update_contained(node, attributes_dict, counter_hack):
	# A node is contained in another if:
	#		Its attributes are the same as the other's
	#		All its children are contained in distinct direct children of 
	#		the	other node.

	# This suggests the following algorithm (which is a bit uglier when
	# 	we're nameless):

	#	If we know what nodes contain this one, we're done; return.
	#	Otherwise, call self on all children.
	#	Take the intersection of the parents of those children's
	#		contained-in sets and the nodes that have the same
	#		attributes as us.
	#	Check how many different children of each prospective parent
	#		contain our children. Admit only those that have unique children
	#		for all our children.
	#	The resulting set of admitted parents is the set of nodes that contain
	# 		us.

	counter_hack[0] += 1
	counter_hack[1] += 1

	if counter_hack[1] == 100:
		counter_hack[1] = 0
		if time.time() - counter_hack[2] > 2:
			counter_hack[2] = time.time()
			print "PROGRESS: Nodes processed: %d name: %s\n" % (counter_hack[0], get_full_path(node))
			#sys.stderr.flush()

	# If there are no children, then the result is just the direct
	# equivalence set.

    # Possible speed hack: keep record of how many links from a leaf we are.
    # There's no point in comparing against something that is closer to a leaf
    # than we are because it can't possibly contain us.

	if node.knows_contained_in():
		return

	prospective_parents = None

	for child in node.get_children():
		update_contained(child, attributes_dict, counter_hack)

		parents_of_contained_in = set(
			[x.get_parent() for x in child.get_contained_in()])

		if prospective_parents == None:
			prospective_parents = attributes_dict[node.get_value().\
				get_hash_size()] & parents_of_contained_in
		else:
			prospective_parents &= parents_of_contained_in

	# Determine how many of the prospective parent's children are
	# containing children of our own.
	contained_in = set()

	if prospective_parents == None:
		prospective_parents = attributes_dict[node.get_value().get_hash_size()]

	for prosp_parent in prospective_parents:
			# We're not interested if its parent is our parent, because 
			# it then allows an item to be contained in itself. E.g.
			# D/a 001		contained in D/b
			# D/b 001		contained in D/a
			# This doesn't happen if we have names, because there can 
			# only be one file with the same name in a directory.
		if prosp_parent.get_parent() != node.get_parent() and \
			is_parent_admitted(node, prosp_parent):
			contained_in.add(prosp_parent)

	#contained_in = prospective_parents

	if len(prospective_parents) == len(contained_in):
		node.set_contained_in(prospective_parents)
	else:
		node.set_contained_in(contained_in)

# Functions for getting cumulative file size and size of subtree
# Alters size_map to contain mappings from nodes to 
# (cumulative file size, size of subtree) pairs. This will be used for
# sorting.
def find_cumulative_sizes_counts(node, size_map):

	# Filter out the -1 of directories
	our_filesize = max(0, node.get_value().get_size())
	cumul_filesize = our_filesize
	cumul_node_count = 1

	for child in node.get_children():
		find_cumulative_sizes_counts(child, size_map)
		cumul_filesize += size_map[child][0]
		cumul_node_count += size_map[child][1]

	size_map[node] = (cumul_filesize, cumul_node_count)

# determine rootmost weakly contained nodes and dump them to a dict.
# The dict maps from the contained node to all its containing nodes.

def find_weakly_contained_nodes(node, attributes_dict, 
	weakly_contained_dict):
	# If all children are contained in direct children of X
	# then we are weakly contained in X.

	# Cut and paste code is evil but eh...
	p_weakly_contained_in = None
	weakly_contained_in = set()

	for child in node.get_children():
		# Why does this make a difference??? Doesn't any longer.
		#update_contained(child, attributes_dict)

		parents_of_contained_in = set(
			[x.get_parent() for x in child.get_contained_in()])

		if p_weakly_contained_in == None:
			p_weakly_contained_in = parents_of_contained_in
		else:
			p_weakly_contained_in &= parents_of_contained_in


	if p_weakly_contained_in != None:
		for prosp_parent in p_weakly_contained_in:
			if is_parent_admitted(node, prosp_parent):
				weakly_contained_in.add(prosp_parent)
			#else:
			#	print "not ok"

	# If we're not contained in anything, recurse on our children.
	# If we are contained in something, there's little point because
	# that would show that all our children are contained in its children,
	# so skip.

	# TODO at some later point: say A is contained in B.
	# A/C is contained in E/C but E/C also contains some stuff that's not
	# in B. We might want to know this. But to avoid "A is contained in B,
	# A/C is contained in B/C" spam, we have to note what nodes we're not
	# interested in as we recurse down.

	if weakly_contained_in == None or len(weakly_contained_in) == 0:
		for child in node.get_children():
			find_weakly_contained_nodes(child, attributes_dict,
				weakly_contained_dict)
	else:
		weakly_contained_dict[node] = weakly_contained_in

def get_hr_size(numblocks, blocksize):
	numbytes = numblocks * blocksize
	prefix = ["bytes", "KB", "MB", "GB", "TB"]

	if numbytes == 0:
		return "0 bytes"

	# Now get the proper prefix by logarithm magic.
	prefix_number = int(math.floor(math.log(numbytes)/math.log(1024)))

	return "%.2f %s" % (float(numbytes)/1024**prefix_number, 
		prefix[prefix_number])

def print_contained_nodes(cumulative_size_data, weakly_contained_dict,
	lower_filesize_bound, blocksize):
	# Go through the contained nodes in descending (size, #items) order.
	# For each of these, print what they're contained in, also sorted in
	# descending (size, #items) order.
	# Doesn't print contained nodes with file sizes less than 
	# lower_filesize_bound.

	cumul_size_key = lambda node: cumulative_size_data[node]

	for contained_node in sorted(weakly_contained_dict.keys(),
		key = cumul_size_key, reverse=True):

		if cumulative_size_data[contained_node][0] < lower_filesize_bound:
			continue

		print "%s/* (%s, %d items) is contained in:" % (
			get_full_path(contained_node), 
			get_hr_size(cumulative_size_data[contained_node][0], blocksize),
			cumulative_size_data[contained_node][1])

		for containing_node in sorted(weakly_contained_dict[contained_node],
			key = cumul_size_key, reverse=True):

			if cumulative_size_data[containing_node] == \
				cumulative_size_data[contained_node]:

				remark = "EXACT"
			else:
				remark = ""

			print "\t%s\t(%s, %d items)\t%s"% (get_full_path(
				containing_node), 
				get_hr_size(cumulative_size_data[containing_node][0],
					blocksize),
				cumulative_size_data[containing_node][1], remark)
		print
# debug

def dfs_debug(node, depth, attributes_dict):
	print ("\t" * depth),
	print node.get_value().get_name(), "\t(", node.get_value().\
		get_hash()[:10],")  ",  \
		len(attributes_dict[node.get_value().get_hash_size()])

def print_debug(root_node, attributes_dict):
	root_node.dfs(lambda node, depth: dfs_debug(node, depth, 
		attributes_dict))
	# should be 9 in length.
	print [x for x in attributes_dict.keys()]

#----#

# Hackish stuff for nameless, proof of concept.

# If any group of identical nodes have all the same parent, then remove them
# all since we're not interested in "X contained in X". A less hackish 
# approach would be to collapse them to node groups; that'll be later.

# Thought for later also: if there are 2 parents, how do we group? The
# parent with fewer nodes get everyone grouped into one meta-file, and the
# parent with more nodes get as many as those grouped into an equivalent
# meta file. How about 3 parents, 4, etc? Something with GCD?

# Recursively: the largest needs to have a block that's large enough to match
# the next to largest ... the next to smallest needs to have a block that's
# large enough to match the smallest.
# So the smallest takes a bite out of the next smallest. The remaining blocks
# in the next smallest can be grouped into one. Say the smallest is 2 files
# and the next smallest is 5. So the next smallest now has one block of 2 and
# one of 3. The next next smallest needs to have one block of 2 and one of 3
# and then whatever remains can be grouped into a single block, and so on.
# Superincreasing knapsack in reverse? Sort of.

def remove_nodes_w_identical_parent(attributes_dict):
	investigated = 0
	pruned = 0

	for attr in attributes_dict.keys():
		investigated += 1
		parents = set([x.get_parent() for x in attributes_dict[attr]])
		if len(parents) == 1:
			pruned += 1
			attributes_dict[attr] = set()

	print "Remove_identical: Investigated",investigated,"and pruned",\
		pruned

# Other idea:
# If A and B appears together everywhere (i.e. attributes_dict[a].parents == 
# attributes_dict[b].parents) then {A,B} can be collapsed into an artificial
# multinode, and this can be applied again and again. (It is in essence a 
# memoization of set comparisons.)
# How to do this:
# Hash every node set (somehow. FNV? Murmurhash?). Check the node sets that 
# hash to the same value against each other.

if len(sys.argv) < 2:
	print "Usage:", sys.argv[0], "sumandsizelist.txt"
	print "\twhere sumandsizelist.txt is a file list in sum and size format."
	print
	print "\tE.g.", sys.argv[0], "test.txt"
	sys.exit(-1)

infile_fn = sys.argv[1]
infiles = [infile_fn]	# TODO: Support more files?

root = FSNode(None)
root.set_value(Attribute(".", "", -1))
same_attribute = defaultdict(set)

# Generator later? Hm, a rather benign IoC

for infile_fn in infiles:
	lines_processed = 0
	period = 0
	for line in open(infile_fn, "rU"): # handle both DOS and Unix newlines
		if period == 10000:
			sys.stderr.write("%d      \n" % lines_processed)
		        sys.stderr.flush()
			period = 0
		period += 1
		lines_processed += 1

		# Split by space
		try:
			# If the string begins in #, it's a comment, ignore
			if line[0] == '#':
				continue
			# TODO/BLUESKY: Determine format here (size, hash, file or just
			# hash, file?)

			#file_size = 1 # HACK HACK
			file_size, file_hash, filename = line.split(None, 2)
			filename = filename.strip('\r\n')
			file_size = int(file_size)
			#print filename,"hello",filename[-1],"there"
			#file_size, file_hash, filename = line.split(None, 2)
			#file_size = 1
			#file_hash, filename = line.split(None, 2)
			#file_hash = file_hash[:5]
			#print line
			#print filename
		except ValueError:
			continue

		# We now have a path and file. Go down this path, creating new 
		# nodes as we go.
		# TODO: Handle "\/" properly.

		# Append the current node
		path_list = filename.split('/')
		append_path(root, path_list, file_hash, file_size, same_attribute)
		#print "---"
		#for (item_name, node) in zip(path_list, node_path_taken):
		#	print item_name, node.get_value().get_name()
		#print "---"

		#old_node_path_taken = node_path_taken
		#old_path_list = path_list

		# We could probably optimize better as well by using hashing or by
		# storing the last path so we jump directly to the leafmost node
		# both have in common. Later.

		# It's really slow as is.

#print_debug(root, same_attribute)

cumulative_sizes = {}
weakly_contained = {}

remove_nodes_w_identical_parent(same_attribute)

begin = time.time()
#print_debug(root, same_attribute)
print "Starting update..."
update_contained(root, same_attribute, [0, 0, 0])
duration = time.time()-begin
print "Updating contained took %f secs" % duration

#root.dfs(dfs_debug_contain_reach)
#print 1/0

find_cumulative_sizes_counts(root, cumulative_sizes)
print "Starting fwc..."
begin = time.time()
find_weakly_contained_nodes(root, same_attribute, weakly_contained)
duration = time.time()-begin
print "Finding weakly contained took %f secs" % duration

#for i in cumulative_sizes.keys():
#	print get_full_path(i), cumulative_sizes[i]
#print_debug(root, same_attribute)
print_contained_nodes(cumulative_sizes, weakly_contained, 0, 1024)
#print_weakly_contained_nodes(root, same_attribute)
