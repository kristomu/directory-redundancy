# -TODO- BUGS! Find out what's going on.

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

# Suggestion for speedup:
#	1. Make child list a dict that can be queried by name
#	2. Breadth first variant: get 100 hashes at once, then fill in
#		the nodes we know on all of them in one go

# And it's probably not a good idea to use du for the size matching, at least
# not if we're going to determine uniqueness by size matching, since different
# file systems may be more or less efficient in determining file size. Ideally
# we should have two file sizes - apparent and real - and apparent is used for
# uniqueness whereas real is used for sorting. But I think we can trust hash
# alone for the time being...

from filetree import *
from attribute import *
from collections import defaultdict
import sys, time, math, os

# OS parsing stuff
# https://www.safaribooksonline.com/library/view/python-cookbook/0596001673/ch04s16.html
def splitall(path):
    allparts = []
    while 1:
        parts = os.path.split(path)
        if parts[0] == path:  # sentinel for absolute paths
            allparts.insert(0, parts[0])
            break
        elif parts[1] == path: # sentinel for relative paths
            allparts.insert(0, parts[1])
            break
        else:
            path = parts[0]
            allparts.insert(0, parts[1])
    return allparts

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


def append_path(root_node, path_list, file_hash, file_size, 
	same_attribute_dict):

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

		# Create a new node. If it's the last, give it file_hash, file_size
		# attributes.
		newchild = FSNode(cur_node)
		if counter == pathlen:
			newchild.set_value(Attribute(next_item, file_hash, file_size))
		else:
			newchild.set_value(Attribute(next_item, "", -1))

		cur_node.add_child(newchild)
		cur_node = newchild

		# Insert the new node into the by-attribute dictionary. The
		# point of this dictionary is to quickly find all nodes that
		# have the same attributes as a given node.
		same_attribute_dict[cur_node.get_value()].add(cur_node)
	return

#---#
def update_contained(node, attributes_dict, verbose=False):
	# A node is contained in another if:
	#		Its attributes are the same as the other's
	#		All its children are contained in direct children of the
	#		other node.

	# This suggests the following algorithm:
	#	If we know what nodes contain this one, we're done; return.
	#	Otherwise, call self on all children.
	#	Then take the intersection of the parents of those children's
	#		contained-in sets and the nodes that have the same
	#		attributes as us.
	#	The resulting set is the set of nodes that contain us.

	# If there are no children, then the result is just the direct
	# equivalence set.

	if verbose:
		print "My node is ", get_full_path(node)

	if node.knows_contained_in():
		return

	if verbose:
		print "Passed first"

	contained_in = attributes_dict[node.get_value()].copy()

	if verbose:
		print "Potentially contained in"
		print [get_full_path(x) for x in contained_in]
		print "Recursing to children..."

	for child in node.get_children():
		update_contained(child, attributes_dict)

		parents_of_contained_in = set(
			[x.get_parent() for x in child.get_contained_in()])

		contained_in &= parents_of_contained_in

	# We're not interested in ourselves.
	contained_in -= set([node])

	if verbose:
		print "Final decision:", get_full_path(node), "contained in"
		print [get_full_path(x) for x in contained_in]

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
	weakly_contained_in = None

	for child in node.get_children():
		# Why does this make a difference??? Doesn't any longer.
		update_contained(child, attributes_dict)

		parents_of_contained_in = set(
			[x.get_parent() for x in child.get_contained_in()])

		if weakly_contained_in == None:
			weakly_contained_in = parents_of_contained_in
		else:
			weakly_contained_in &= parents_of_contained_in

	# If we're not contained in anything, recurse on our children.
	# If we are contained in something, there's little point because
	# that would show that all our children are contained in its children,
	# so skip.

	# TODO at some later point: say A is contained in B.
	# A/C is contained in E/C but E/C also contains some stuff that's not
	# in B. We might want to know this. But to avoid "A is contained in B,
	# A/C is contained in B/C" spam, we have to note what nodes we're not
	# interested in as we recurse down.
	# The simplest way of doing so would be to, when we see that A is 
	# contained in B, stop printing any A/* in B/*. Something like, when
	# we encounter say A/C, we check a "don't show" dict for A/ and A/C.
	# Any entries that partially match B/C are omitted in printout.

	if weakly_contained_in == None or len(weakly_contained_in) == 0:
		for child in node.get_children():
			find_weakly_contained_nodes(child, attributes_dict,
				weakly_contained_dict)
	else:
		weakly_contained_dict[node] = weakly_contained_in

	#print get_full_path(node), weakly_contained_in

# outputs human readable size

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

				remark = "EXACT COPY"
			else:
				remark = ""

			print "\t%s\t(%s, %d items)\t%s"% (get_full_path(
				containing_node), 
				get_hr_size(cumulative_size_data[containing_node][0],
					blocksize),
				cumulative_size_data[containing_node][1], remark)
		print

# Debugging:

def dfs_debug(node, depth, attributes_dict):
	print ("\t" * depth),
	print node.get_value().get_name(), "\t(", node.get_value().\
		get_hash()[:10],")  ", len(attributes_dict[node.get_value()])

def print_debug(root_node, attributes_dict):
	root_node.dfs(lambda node, depth: dfs_debug(node, depth, 
		attributes_dict))
	print [(x.get_name(), x.get_hash()) for x in attributes_dict.keys()]

#----#

# If we have a bunch of files with the same ID in one directory and nowhere
# else, then since we're not interested in "X is contained in X", then they're
# effectively uniques and we can discard all of them.

def remove_nodes_w_identical_parent(attributes_dict):
	investigated = 0
	pruned = 0

	begin = time.time()

	for attr in attributes_dict.keys():
		investigated += 1
		parents = set([x.get_parent() for x in attributes_dict[attr]])
		if len(parents) == 1:
			pruned += 1
			attributes_dict[attr] = set()

		if len(parents) == 2:
			pruned += 1
			by_parent = defaultdict(list)
			parcount = 0
			for node in attributes_dict[attr]:
				by_parent[node.get_parent()].append(node)

			listpar = list(parents)
			lesser = by_parent[listpar[0]]
			greater = by_parent[listpar[1]]

			if len(lesser) > len(greater):
				lesser, greater = greater, lesser

			# Cut size
			greater = greater[:len(lesser)]

			# And dump back
			attributes_dict[attr] = set(greater + lesser)

	print "Remove_identical: Investigated %d and pruned %d in %.3f s" % \
		(investigated,pruned, time.time()-begin)

# Possible extension: If there are two parents, then prune the greater to the 
# lesser's size. The only possibility is that the lesser is contained in the 
# greater. If we get compound node support, we could collapse the lesser into 
# a single node for all of those files.

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

blocksize = 1	# du -B 1. Ordinary du would have 1024 here

# Generator later? Hm, would be a rather benign IoC

for infile_fn in infiles:
	lines_processed = 0
	period = 0
	for line in open(infile_fn, "rU"):
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

			app_file_size, real_file_size, file_hash, filename = line.split(None, 3)
			# TODO: Use apparent file size for contains detection and
			# real (fs) file size for the printout.
			file_size = app_file_size
			filename = filename.rstrip('\r\n')
			file_size = int(file_size)
		except ValueError:
			continue

		# We now have a path and file. Go down this path, creating new 
		# nodes as we go.
		
		# Append the current node
		path_list = splitall(filename)
		append_path(root, path_list, file_hash, file_size, same_attribute)
		
		# We could probably optimize better as well by using hashing or by
		# storing the last path so we jump directly to the leafmost node
		# both have in common. Later.

#print_debug(root, same_attribute)

cumulative_sizes = {}
weakly_contained = {}

begin = time.time()

print "Starting update..."
remove_nodes_w_identical_parent(same_attribute)
update_contained(root, same_attribute)
duration = time.time()-begin
print "Updating contained took %.3f secs" % duration

#print_debug(root, same_attribute)
#print 1/0

find_cumulative_sizes_counts(root, cumulative_sizes)
print "Starting fwc..."
begin = time.time()
find_weakly_contained_nodes(root, same_attribute, weakly_contained)
duration = time.time()-begin
print "Finding weakly contained took %.3f secs" % duration

print_contained_nodes(cumulative_sizes, weakly_contained, 10, blocksize)
