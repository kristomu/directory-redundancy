# Check Redundancy: finds redundant directories in a directory structure
# given by a hash (md5sum etc) output file.

import md5, sys
from collections import defaultdict

# If args < 1, print usage
# Usage: [script name] sumandsizelist.txt
# where sumandsizelist is... etc etc

if len(sys.argv) < 2:
	print "Usage:", sys.argv[0], "sumandsizelist.txt"
	print "\twhere sumandsizelist.txt is a file list in sum and size format."
	print
	print "\tE.g.", sys.argv[0], "test.txt"
	sys.exit(-1)

infile_fn = sys.argv[1]

# if args > 1, take the file as input and print 'using file xyz as input'

#infile_fn = "test.txt"
#infile_fn = "/home/km/optdisksums.txt"

print "Using", infile_fn,"as input."

def sxor(s1,s2):    
    #https://stackoverflow.com/questions/2612720/how-to-do-bitwise-exclusive-or-of-two-strings-in-python
    return ''.join(chr(ord(a) ^ ord(b)) for a,b in zip(s1,s2))

def get_combined_hash(old_hash, new_filename, new_hash):
	new_hash = md5.new(new_filename + new_hash)
	if old_hash == None:
		return new_hash.digest()
	else:
		return (sxor(new_hash.digest(), old_hash))

tree_hash_dict = {}
tree_count_dict = defaultdict(int)

for line in open(infile_fn, "r"):
	# Split by space
	try:
		#filesize, file_hash, filename = line.split(None, 2)
		app_file_size, real_file_size, file_hash, filename = line.split(None, 3)
		filesize = int(real_file_size)
	except ValueError:
		continue
		# print line
		# print "###", filesize, "###", file_hash, "###", filename
		# print line.split(' ', 2)
		# print 1/0
	for pos in xrange(len(filename)):
		if filename[pos] == "/":
			tree_to_add_to = filename[:pos+1]
			filename_within_tree = filename[pos+1:]

			if tree_to_add_to in tree_hash_dict:
				old_hash = tree_hash_dict[tree_to_add_to]
			else:
				old_hash = None

			tree_hash_dict[tree_to_add_to] = get_combined_hash(old_hash,
				filename_within_tree, file_hash)
			try:
				tree_count_dict[tree_to_add_to] += int(filesize) #1
			except ValueError:
				tree_count_dict[tree_to_add_to] += 1

			#print filename[:pos+1], filename[pos+1:]

# Reverse the tree hashes to find collisions.

reverse_tree_hash = defaultdict(list)

for path in tree_hash_dict:
	reverse_tree_hash[tree_hash_dict[path]].append(path)

# Do some pruning to fix the following problem:
#	- If we find out that x/ and y/ match, we're not really interested in that
#		x/a and y/a, x/b and y/b, etc all match.

# The pruning works like this:
#	1. Dump all the matching hashes and their counts into a list.
#	2. Sort list by counts, descending
#	3. Go down the list. For each entry:
#		3.1. If all directories have different prefixes that have been seen
#			 before, skip.
#		3.2. Otherwise:
#			3.2.1. List the count and contents.
#			3.2.2. Add everything but the first listed directory to our dict
#					of things we've seen before.

# [*]	Why not "if only one"? Because say /a/ matches /b/, and furthermore /c/x
# 		matches /a/x, but /c/x matches nothing else. Then we'd still like to know
#		about it because /c/x is novel.

found_collisions = []
already_seen = {}

# 1.
for hashes in reverse_tree_hash:
	if len(reverse_tree_hash[hashes]) > 1:
		count = tree_count_dict[reverse_tree_hash[hashes][0]]
		found_collisions.append((count, sorted(reverse_tree_hash[hashes])))

# 2.
# First sort by length of longest directory (shortest first), then by count.
found_collisions.sort(key=lambda x: max(map(len, x[1])))
found_collisions.sort(key=lambda x: x[0], reverse=True)

# 3.

def where_seen_before(seen_before_dict, directory):
	for char_pos in xrange(len(directory)):
		if directory[-char_pos-1] == '/':
			if directory[:-char_pos] in seen_before_dict:
				return seen_before_dict[directory[:-char_pos]]
	return None

def has_seen_all_before(seen_before_dict, list_of_dirs):
	seen_before_indices = {}

	for directory in list_of_dirs:
		seen_before_idx = where_seen_before(seen_before_dict, directory)
		if seen_before_idx != None:
			seen_before_indices[seen_before_idx] = True
	
	return len(seen_before_indices) == len(list_of_dirs)

seen_idx = 0

for collision in found_collisions:
	if not has_seen_all_before(already_seen, collision[1]):
		print collision
		for directory in collision[1]:
			already_seen[directory] = seen_idx
			seen_idx += 1
